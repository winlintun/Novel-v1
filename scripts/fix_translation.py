#!/usr/bin/env python3
"""
Fix Poor Translation - Post-processing script to fix common translation issues

This script fixes the problems described in need_to_fix.md:
1. Removes metadata text ("Chapter: ... TEXT TO TRANSLATE:")
2. Fixes unnatural dialogue
3. Shows emotions instead of describing them
4. Breaks long sentences
5. Ensures character name consistency

Usage:
    python scripts/fix_translation.py <input_file> [output_file]
    python scripts/fix_translation.py books/novel_name/chapters/file.md
"""

import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple


def load_glossary(novel_name: str) -> Dict[str, str]:
    """Load glossary for the novel."""
    glossary = {}
    
    # Try novel-specific glossary
    glossary_file = Path(f"glossaries/{novel_name}.json")
    if glossary_file.exists():
        try:
            with open(glossary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                glossary = data.get("names", {})
        except Exception as e:
            print(f"Warning: Could not load glossary: {e}")
    
    return glossary


def remove_metadata_text(text: str) -> str:
    """Remove 'Chapter: ... TEXT TO TRANSLATE:' metadata."""
    # Pattern: "Chapter: <name> TEXT TO TRANSLATE:"
    pattern = r'Chapter:\s*[^\n]+TEXT TO TRANSLATE:\s*'
    text = re.sub(pattern, '', text)
    
    # Also remove "စာမျက်နှာ: ... TEXT TO TRANSLATE:"
    pattern = r'စာမျက်နှာ:\s*[^\n]+TEXT TO TRANSLATE:\s*'
    text = re.sub(pattern, '', text)
    
    return text


def fix_english_phrases(text: str) -> str:
    """Fix common English phrases that weren't translated."""
    # Common English phrases and their Burmese translations
    replacements = {
        r'Chapter\s+\d+:\s*': '',  # Remove "Chapter X:" prefix
        r'Chapter\s+1\s+Gu\s+Wen': 'အခန်း ၁ - ဂူဝမ်',
        r'Sir,\s*a\s*good\s*harvest\s*is\s*useless\s*now': 'ဦးလေး၊ အခုတော့ သီးနှံကောင်းကောင်း မရတော့ဘူး',
        r'Even\s*if\s*the\s*fields\s*were\s*to\s*produce\s*gold': 'လယ်က ရွှထွက်ပါရစေ',
        r'it\s*wouldn\'t\s*be\s*enough\s*to\s*pay\s*the\s*taxes': 'အခွန်ဆပ်ဖို့ မလုံလောက်ဘူး',
        r'Marquis\s+Wen': 'ဝမ်တိုင်',
        r'Ninth\s+Prince': 'နဝမမင်းသား',
        r'Bianjing': 'ဘိန်းကျိင်',
        r'Daqian': 'ချီအန်း',
        r'Dragon\s+Bridge': 'လွန်ချျန်းတံတား',
        r'Vermilion\s+Bird\s+Gate': 'ဇူချိုးတံခါး',
        r'Changle\s+Square': 'ချားလိတ်ရင်',
        r'Yangzhou': 'ယန်ကျိုး',
        r'Taverns\s+sold\s+sea\s+cucumbers[^\n]*': 'သောက်စရာခန်းများတွင် ပင်လယ်ခရုများ၊ ငါးဖ/templateများ၊ ဝက်ခြောက်များ ရောင်းချသည်',
        r'brothel[^\n]*': 'ဇိမ်ခံအခန်းများ',
        r'teaching\s+institute\s+girls': 'ပညာရေးကျောင်းသူများ',
        r'corner\s+geishas': 'အသီးသီးတေးဂီတသူများ',
        r'gambling\s+tables': 'လောင်းကစားစားပွဲများ',
        r'dice[^,]*': 'လက်ဝါးကပ်တိုင်',
        r'cockfights[^,]*': 'ကြက်တိုက်ပွဲများ',
        r'quail\s+fights[^,]*': 'ခိုးတိုက်ပွဲများ',
        r'skinny\s+horses': 'မြင်းကလေးများ',
        r'of\s+the': '',  # Remove "of the"
        r'Feudal': 'ရှေးရိုးစဉ်လာ',
        r'mesh': 'အားစ',
        r'\bmesh\b': 'အားစ',
        r'\bfish\s*maws\b': 'ငါးဖ/templateများ',
        r'\bsharks?\s*fins?\b': 'ဉခေါင်းများ',
        r"\b's\s+residence\b": '၏ နန်းတော်',
        r'\ba\s+thousand\s+years?\s+from\b': 'အဝေးမှ',
        r'\bbear\s*paws?\b': 'ဝက်ခြောက်များ',
        r'\bscallops?\b': 'ပင်လယ်ခရုများ',
        r'\bdear\s*tails?\b': 'သမင်ချိုများ',
        r'\bdear\s*tongues?\b': 'သမင်လိanguagesများ',
        r'\bbirds?\s*nest\b': 'ငှက်သိုက်များ',
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Fix any remaining English words mixed in Burmese
    # Pattern: Burmese character + English word + Burmese character
    text = re.sub(r'([\u1000-\u109F])\s*([a-zA-Z]+)\s*([\u1000-\u109F])', r'\1\3', text)
    
    return text


def fix_weird_repetitions(text: str) -> str:
    """Fix weird character repetitions."""
    # Fix repeated (၁) pattern
    text = re.sub(r'(?:\(၁\)\s*){3,}', '', text)
    
    # Fix repeated Myanmar syllables or words (4+ repetitions)
    # Catches patterns like ချိုချိုချိုချို...
    text = re.sub(r'([\u1000-\u109F]{1,8})\1{4,}', r'\1', text)
    
    # Fix long sequences of the same Myanmar character repeated
    text = re.sub(r'([\u1000-\u109F])\1{4,}', r'\1', text)
    
    # Fix long sequences of the same character (any script)
    text = re.sub(r'([^\s])\1{5,}', r'\1', text)
    
    # Remove stray punctuation like ")" and "-" that appear alone
    text = re.sub(r'\s+[\)\-\*]+\s+', ' ', text)
    text = re.sub(r'^[\)\-\*]+\s+', '', text, flags=re.MULTILINE)
    
    # Fix periods after Burmese text (use Burmese period instead)
    text = re.sub(r'([\u1000-\u109F])\.\s*"', r'\1။ "', text)
    
    return text


def fix_character_names(text: str, glossary: Dict[str, str]) -> str:
    """Ensure character names use glossary translations."""
    # Add common variations
    name_variations = {
        'Gu Wen': 'ဂူဝမ်',
        'GuWen': 'ဂူဝမ်',
        'GU WEN': 'ဂူဝမ်',
        'Marquis Wen': 'ဝမ်တိုင်',
        'Wen Marquis': 'ဝမ်တိုင်',
    }
    
    # Merge with glossary
    all_names = {**name_variations, **glossary}
    
    for english_name, burmese_name in all_names.items():
        # Replace whole word only
        pattern = r'\b' + re.escape(english_name) + r'\b'
        text = re.sub(pattern, burmese_name, text, flags=re.IGNORECASE)
    
    return text


def fix_dialogue_format(text: str) -> str:
    """Fix dialogue to sound more natural."""
    # Fix quoted dialogue format
    # Pattern: "text" လို့ ...
    text = re.sub(
        r'"([^"]+)"\s*လို့\s*([^။\n]+)',
        r'"\1" လို့ \2',
        text
    )
    
    # Fix overly formal dialogue endings
    formal_to_natural = {
        'မေးမြန်းလေသည်': 'မေးလိုက်တယ်',
        'ပြောဆိုလေသည်': 'ပြောလိုက်တယ်',
        'ဖြေကြားလေသည်': 'ဖြေလိုက်တယ်',
        'ဟုဆိုလေသည်': 'လို့ပြောလိုက်တယ်',
        'ဟုမေးလေသည်': 'လို့မေးလိုက်တယ်',
    }
    
    for formal, natural in formal_to_natural.items():
        text = text.replace(formal, natural)
    
    return text


def fix_emotion_descriptions(text: str) -> str:
    """Fix abstract emotion descriptions to show physical sensations."""
    # Dictionary of bad vs good emotion descriptions
    emotion_fixes = {
        'အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်': 'ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလိုပဲ',
        'အလွန်ပျော်ရွင်နေသည်': 'မျက်လုံးတွေ ပြုံးလိုက်တယ်',
        'အလွန်အံ့ဩနေသည်': 'မျက်လုံးတွေ ကြီးသွားတယ်၊ နှုတ်ခမ်းတွေ ဟ လိုက်မိတယ်',
        'အလွန်စိုးရိမ်နေသည်': 'လက်တွေ တုန်လာတယ်၊ ဘေးမှာ ရှိရာ အရာကို အမြဲ ကြည့်နေမိတယ်',
    }
    
    for bad, good in emotion_fixes.items():
        text = text.replace(bad, good)
    
    return text


def fix_long_sentences(text: str) -> str:
    """Break overly long sentences into shorter ones."""
    lines = text.split('\n')
    new_lines = []
    
    for line in lines:
        # If line has more than 150 characters and few periods, try to break it
        if len(line) > 150 and line.count('။') < 3:
            # Try to break at conjunctions or commas
            break_points = ['။ ', '၊ ', 'ပြီးတော့ ', 'ဒါပေမဲ့ ', 'အဲဒါကြောင့် ']
            
            # Find good break points
            segments = []
            current = line
            
            for point in break_points:
                if point in current and len(current) > 100:
                    parts = current.split(point, 1)
                    if len(parts) == 2 and len(parts[0]) > 30:
                        segments.append(parts[0] + point.strip())
                        current = parts[1]
            
            if segments:
                segments.append(current)
                new_lines.extend(segments)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    return '\n'.join(new_lines)


def fix_separator_lines(text: str) -> str:
    """Remove or fix separator lines like '---------------'."""
    # Remove lines of just dashes
    text = re.sub(r'\n[-=]{3,}\n', '\n', text)
    return text


def postprocess_translation(text: str, novel_name: str = "") -> str:
    """Run all fixes on the translation."""
    print("Applying translation fixes...")
    
    # Load glossary
    glossary = load_glossary(novel_name)
    print(f"  Loaded {len(glossary)} names from glossary")
    
    # Apply fixes in order
    original_len = len(text)
    
    text = remove_metadata_text(text)
    print("  ✓ Removed metadata text")
    
    text = fix_weird_repetitions(text)
    print("  ✓ Fixed weird repetitions")
    
    text = fix_english_phrases(text)
    print("  ✓ Fixed English phrases")
    
    text = fix_character_names(text, glossary)
    print("  ✓ Fixed character names")
    
    text = fix_dialogue_format(text)
    print("  ✓ Fixed dialogue format")
    
    text = fix_emotion_descriptions(text)
    print("  ✓ Fixed emotion descriptions")
    
    text = fix_separator_lines(text)
    print("  ✓ Fixed separator lines")
    
    text = fix_long_sentences(text)
    print("  ✓ Fixed long sentences")
    
    new_len = len(text)
    print(f"\nOriginal: {original_len} chars → Fixed: {new_len} chars")
    
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_translation.py <input_file> [output_file]")
        print("Example: python fix_translation.py books/novel/chapters/file.md")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    
    if not input_file.exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    # Determine output file
    if len(sys.argv) >= 3:
        output_file = Path(sys.argv[2])
    else:
        # Default: add _fixed suffix
        output_file = input_file.parent / (input_file.stem + "_fixed" + input_file.suffix)
    
    # Extract novel name from path (books/novel_name/chapters/...)
    novel_name = ""
    try:
        if 'books' in input_file.parts:
            books_idx = input_file.parts.index('books')
            if len(input_file.parts) > books_idx + 1:
                novel_name = input_file.parts[books_idx + 1]
    except (ValueError, IndexError):
        pass
    
    print(f"Processing: {input_file}")
    print(f"Novel: {novel_name or 'Unknown'}")
    print("=" * 60)
    
    # Read input
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Process
    fixed_content = postprocess_translation(content, novel_name)
    
    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"\n✓ Fixed translation saved to: {output_file}")


if __name__ == "__main__":
    main()
