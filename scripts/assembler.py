#!/usr/bin/env python3
"""
Assembler - Merge chunks into final .md file
"""

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


def assemble(
    original_title: str,
    chapter_number: int,
    model_name: str,
    translated_content: str,
    output_path: str
):
    """
    Assemble translated chunks into final .md file.
    
    Args:
        original_title: Original Chinese chapter title
        chapter_number: Chapter number
        model_name: Name of translation model used
        translated_content: The translated text
        output_path: Where to save the final file
    """
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
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(filled)
    
    print(f"✓ Assembled: {output_file}")
    print(f"  Size: {len(filled):,} characters")


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
