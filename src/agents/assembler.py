#!/usr/bin/env python3
"""
Assembler - Merge chunks into final .md file
"""

import os
from datetime import datetime
from pathlib import Path


def load_template() -> str:
    """Load chapter template."""
    template_path = Path("templates/chapter_template.md")
    
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # Default template
    return """# {original_title} — မြန်မာဘာသာပြန်
**အခန်း**  : {chapter_number}
**မော်ဒယ်** : {model_name}
**ရက်စွဲ**  : {date}

---

{translated_content}

---
*ဤဘာသာပြန်ချက်ကို AI ဖြင့် ဘာသာပြန်ထားပါသည်။*
"""


import json

def update_metadata(book_id: str, chapter_number: int, chapter_title: str, chapter_file: str):
    """Update metadata.json for the book."""
    books_dir = Path("books")
    book_dir = books_dir / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_path = book_dir / "metadata.json"
    
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    else:
        metadata = {
            "id": book_id,
            "title": book_id,
            "author": "Unknown",
            "chapters": []
        }
    
    # Check if chapter already exists
    exists = False
    for i, ch in enumerate(metadata["chapters"]):
        if ch["number"] == chapter_number:
            metadata["chapters"][i] = {
                "number": chapter_number,
                "title": chapter_title,
                "file": chapter_file
            }
            exists = True
            break
    
    if not exists:
        metadata["chapters"].append({
            "number": chapter_number,
            "title": chapter_title,
            "file": chapter_file
        })
    
    # Sort chapters
    metadata["chapters"].sort(key=lambda x: x["number"])
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def assemble(
    original_title: str,
    chapter_number: int,
    model_name: str,
    translated_content: str,
    output_path: str,
    book_id: str = None
):
    """
    Assemble translated chunks into final .md file and update metadata.
    
    Args:
        original_title: Original Chinese chapter title
        chapter_number: Chapter number
        model_name: Name of translation model used
        translated_content: The translated text
        output_path: Where to save the final file
        book_id: ID of the book (optional)
    
    Raises:
        ValueError: If translated_content is empty or None
    """
    # Edge case: Validate translated content
    if translated_content is None:
        raise ValueError("Translated content cannot be None")
    
    if not translated_content.strip():
        raise ValueError("Translated content is empty - cannot assemble empty translation")
    
    # Warn if content seems too short (less than 50 chars might indicate a problem)
    if len(translated_content.strip()) < 50:
        print(f"⚠ Warning: Translated content is very short ({len(translated_content)} chars)")
    
    template = load_template()
    
    # Fill template
    filled = template.format(
        original_title=original_title,
        chapter_number=chapter_number,
        model_name=model_name,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        translated_content=translated_content
    )
    
    # Save
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Edge case: Check if directory is writable
    if not os.access(output_file.parent, os.W_OK):
        raise PermissionError(f"Cannot write to directory: {output_file.parent}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(filled)
    
    print(f"✓ Assembled: {output_file}")
    
    # Update metadata if book_id is provided
    if book_id:
        update_metadata(
            book_id=book_id,
            chapter_number=chapter_number,
            chapter_title=original_title,
            chapter_file=output_file.name
        )


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python assembler.py <checkpoint_dir> <output_file>")
        print("Example: python assembler.py working_data/checkpoints/chapter_001 translated_novels/chapter_001_myanmar.md")
        sys.exit(1)
    
    checkpoint_dir = Path(sys.argv[1])
    output_file = sys.argv[2]
    
    # Load all checkpoint chunks
    chunks = []
    for chunk_file in sorted(checkpoint_dir.glob("chunk_*.txt")):
        with open(chunk_file, 'r', encoding='utf-8') as f:
            chunks.append(f.read())
    
    content = '\n\n'.join(chunks)
    
    assemble(
        original_title=checkpoint_dir.name,
        chapter_number=1,
        model_name="unknown",
        translated_content=content,
        output_path=output_file
    )
