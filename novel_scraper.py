"""
Novel Scraper - Downloads novels from multiple sources
Supports: novelbin.me, freewebnovel.com, wuxiaspot.com
Usage: python novel_scraper.py <novel_url>
"""

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

from bs4 import BeautifulSoup
import time
import os
import sys
import urllib.request
import re
from urllib.parse import urljoin, urlparse

# Create a cloudscraper instance to bypass Cloudflare protection
_scraper = None

def get_scraper():
    """Get or create a cloudscraper instance."""
    global _scraper
    if _scraper is None and CLOUDSCRAPER_AVAILABLE:
        _scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=10
        )
    return _scraper


def get_soup(url, retries=3):
    """Fetch URL and return BeautifulSoup object."""
    # Try cloudscraper first if available
    if CLOUDSCRAPER_AVAILABLE:
        scraper = get_scraper()
        for i in range(retries):
            try:
                if i > 0:
                    time.sleep(3 * i)
                res = scraper.get(url, timeout=30)
                res.raise_for_status()
                return BeautifulSoup(res.text, "html.parser")
            except Exception as e:
                print(f"  [Cloudscraper Retry {i+1}] {e}")

    # Fallback: Try with urllib
    for i in range(retries):
        try:
            if i > 0:
                time.sleep(3 * i)
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')
                return BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"  [urllib Retry {i+1}] {e}")

    return None


def detect_site(url):
    """Detect which site the URL belongs to."""
    if "freewebnovel.com" in url:
        return "freewebnovel"
    elif "wuxiaspot.com" in url:
        return "wuxiaspot"
    elif "novelbin.me" in url or "novelbin.com" in url:
        return "novelbin"
    else:
        return "unknown"


def get_all_chapter_links(novel_url):
    """Get all chapter URLs from the novel's table of contents."""
    site = detect_site(novel_url)
    print(f"\n📖 Detected site: {site}")
    print(f"📖 Fetching chapter list from: {novel_url}")

    soup = get_soup(novel_url)

    if not soup:
        print("❌ Could not load novel page.")
        return [], site

    links = []

    if site == "freewebnovel":
        # FreeWebNovel: chapters are in format /novel/{name}/chapter-{num}
        # Extract novel name from URL
        parsed = urlparse(novel_url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'novel':
            novel_name = path_parts[1]
            # Find the latest chapter number from meta or page
            last_chapter_meta = soup.find('meta', property='og:novel:lastest_chapter_url')
            if last_chapter_meta:
                last_chapter_url = last_chapter_meta.get('content', '')
                # Extract chapter number
                match = re.search(r'chapter-(\d+)', last_chapter_url)
                if match:
                    last_chapter = int(match.group(1))
                    print(f"✅ Found {last_chapter} chapters.")
                    # Generate chapter URLs
                    base_url = f"{parsed.scheme}://{parsed.netloc}/novel/{novel_name}"
                    links = [f"{base_url}/chapter-{i}" for i in range(1, last_chapter + 1)]

    elif site == "wuxiaspot":
        # WuxiaSpot: Try to find chapter links on the page
        selectors = [
            "a[href*='/chapter/']",
            "a[href*='/read/']",
            ".chapter-list a",
            "#chapter-list a",
            "ul.chapters li a",
        ]
        for sel in selectors:
            tags = soup.select(sel)
            if tags:
                links = [urljoin(novel_url, a["href"]) for a in tags if a.get("href")]
                break

    elif site == "novelbin":
        # novelbin TOC page
        toc_url = novel_url.rstrip("/") + "/chapters"
        soup = get_soup(toc_url)

        if not soup:
            soup = get_soup(novel_url)

        selectors = [
            "ul.list-chapter li a",
            "ul#list-chapter li a",
            ".list-chapter a",
            "a[href*='/chapter-']",
        ]
        for sel in selectors:
            tags = soup.select(sel)
            if tags:
                links = [urljoin(novel_url, a["href"]) for a in tags if a.get("href")]
                break

    print(f"✅ Found {len(links)} chapters.")
    return links, site


def scrape_chapter(url, site):
    """Scrape text content from a single chapter page."""
    soup = get_soup(url)
    if not soup:
        return None, None

    title = ""
    content = ""

    if site == "freewebnovel":
        # Title: look for h4 inside article or h1
        for sel in ["#article h4", "h1", ".chapter-title", "h2"]:
            tag = soup.select_one(sel)
            if tag:
                title = tag.get_text(strip=True)
                break

        # Content: look for div#article or specific content divs
        for sel in ["#article", ".chapter-content", "#chapter-content", ".read-content"]:
            tag = soup.select_one(sel)
            if tag:
                # Remove ads and junk
                for junk in tag.select("script, style, ins, .ads, .ad-container, subtxt, .hidden"):
                    junk.decompose()
                # Get text from paragraphs
                paragraphs = tag.find_all("p")
                if paragraphs:
                    content = "\n\n".join(p.get_text(strip=True) for p in paragraphs)
                else:
                    content = tag.get_text("\n", strip=True)
                break

    elif site == "wuxiaspot":
        # Try common selectors
        for sel in ["h1", ".chapter-title", "h2", "h3"]:
            tag = soup.select_one(sel)
            if tag:
                title = tag.get_text(strip=True)
                break

        for sel in ["#chapter-content", ".chapter-content", ".read-content", "#content", "article"]:
            tag = soup.select_one(sel)
            if tag:
                for junk in tag.select("script, style, ins, .ads, .ad-container"):
                    junk.decompose()
                paragraphs = tag.find_all("p")
                if paragraphs:
                    content = "\n\n".join(p.get_text(strip=True) for p in paragraphs)
                else:
                    content = tag.get_text("\n", strip=True)
                break

    elif site == "novelbin":
        # Title
        for sel in ["h2 a.chr-title", "h2.chr-title", "h2", ".chr-title"]:
            tag = soup.select_one(sel)
            if tag:
                title = tag.get_text(strip=True)
                break

        # Content
        for sel in ["div#chr-content", "div.chr-content", "div#chapter-content", "div.chapter-content"]:
            tag = soup.select_one(sel)
            if tag:
                for junk in tag.select("script, style, ins, .ads, .ad-container"):
                    junk.decompose()
                content = tag.get_text("\n", strip=True)
                break

    return title, content


def download_novel(novel_url, output_folder="data_file"):
    os.makedirs(output_folder, exist_ok=True)

    # Get novel name from URL
    parsed = urlparse(novel_url)
    novel_slug = parsed.path.strip('/').split('/')[-1].replace('.html', '')
    output_path = os.path.join(output_folder, f"{novel_slug}.txt")

    chapter_links, site = get_all_chapter_links(novel_url)
    if not chapter_links:
        print("❌ No chapters found. Check the URL and try again.")
        print("\n⚠️  Cloudflare Protection or Unsupported Site!")
        print("-" * 60)
        print("Supported sites:")
        print("  - https://freewebnovel.com/novel/{novel-name}")
        print("  - https://novelbin.me/novel/{novel-name}")
        print("  - https://www.wuxiaspot.com/novel/{id}.html")
        print("-" * 60)
        print("\nAlternative solutions:")
        print("1. Use a browser extension like 'SingleFile' to save chapters manually")
        print("2. Try accessing from a different network/IP")
        print("3. Check if the novel is available on other sites")
        print("-" * 60)
        return

    # Limit chapters for testing (set to 0 or remove for all chapters)
    max_chapters = os.getenv("MAX_CHAPTERS", "0")
    try:
        max_chapters = int(max_chapters)
        if max_chapters > 0 and len(chapter_links) > max_chapters:
            print(f"   ⚠️  Limiting to first {max_chapters} chapters (set MAX_CHAPTERS=0 for all)")
            chapter_links = chapter_links[:max_chapters]
    except (ValueError, TypeError):
        pass

    print(f"\n⬇️  Downloading to: {output_path}")
    print(f"   Site: {site}")
    print(f"   Chapters: {len(chapter_links)}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        for i, url in enumerate(chapter_links, 1):
            print(f"  [{i}/{len(chapter_links)}] {url}")
            title, content = scrape_chapter(url, site)

            if content and len(content) > 100:  # Ensure content is substantial
                f.write(f"\n\n{'='*60}\n")
                f.write(f"{title}\n")
                f.write(f"{'='*60}\n\n")
                f.write(content)
                f.flush()
                print(f"     ✓ {len(content)} chars")
            else:
                print(f"     ⚠️  Empty or short chapter, skipping.")

            time.sleep(1.5)  # be polite, avoid getting blocked

    print(f"\n✅ Done! Saved to: {output_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("  Novel Downloader")
    print("  Supports: freewebnovel.com, novelbin.me, wuxiaspot.com")
    print("=" * 60)

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("\nNovel URL: ").strip()

    if not url.startswith("http"):
        print("❌ Invalid URL. Please provide a full URL starting with http:// or https://")
        sys.exit(1)

    download_novel(url)
