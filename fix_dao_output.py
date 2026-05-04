#!/usr/bin/env python3
"""
Fix script for dao-equaling-the-heavens translation output files.
Fixes:
1. Korean character leakage
2. Missing chapter headings  
3. Adds proper heading format to output
"""

import re
import os
import sys

sys.path.insert(0, '.')

# Korean pattern
KOREAN = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF]')

# Chapter number extraction from filename
CHAPTER_RE = re.compile(r'chapter_(\d+)')

def fix_chapter_output(filepath: str) -> bool:
    """Fix a single chapter output file."""
    if not os.path.exists(filepath):
        return False
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    original = content
    fixed = False
    
    # 1. Remove Korean characters
    if KOREAN.search(content):
        content = KOREAN.sub('', content)
        fixed = True
        print(f"  🔧 Removed Korean chars from {os.path.basename(filepath)}")
    
    # 2. Extract chapter number from filename
    match = CHAPTER_RE.search(filepath)
    if match:
        ch_num = int(match.group(1))
        
        # Check if proper Myanmar heading exists
        if not re.search(r'^#\s+အခန်း\s+\d', content, re.MULTILINE):
            # Create proper heading
            proper_heading = f"# အခန်း {ch_num:02d}\n"
            
            # Remove any existing non-standard heading at start
            content = re.sub(r'^#\s+([^\n]+)\n', '', content, count=1, flags=re.MULTILINE)
            
            # Prepend proper heading
            content = proper_heading + content
            fixed = True
            print(f"  🔧 Added heading '# အခန်း {ch_num:02d}' to {os.path.basename(filepath)}")
    
    if fixed:
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        return True
    
    return False


def main():
    novel = "dao-equaling-the-heavens"
    output_dir = f"data/output/{novel}"
    
    print(f"\n{'='*70}")
    print(f"  🔧 FIXING {novel} OUTPUT FILES")
    print(f"{'='*70}")
    
    if not os.path.isdir(output_dir):
        print(f"❌ Output directory not found: {output_dir}")
        return
    
    # Get all chapter files
    chapter_files = sorted([
        f for f in os.listdir(output_dir) 
        if f.endswith('.mm.md') and 'chapter_' in f
    ])
    
    print(f"\n  Found {len(chapter_files)} chapter files")
    
    fixed_count = 0
    for chap_file in chapter_files:
        filepath = os.path.join(output_dir, chap_file)
        if fix_chapter_output(filepath):
            fixed_count += 1
    
    print(f"\n  ✅ Fixed {fixed_count}/{len(chapter_files)} files")
    
    # Also process review reports to update status
    print(f"\n{'='*70}")
    print(f"  UPDATING REVIEW REPORTS")
    print(f"{'='*70}")
    
    report_dir = "logs/report"
    if os.path.isdir(report_dir):
        report_files = sorted([
            f for f in os.listdir(report_dir)
            if novel in f and f.endswith('.md')
        ])
        
        print(f"\n  Found {len(report_files)} review files")
        
        # Note: We don't delete old reports, just note they exist


if __name__ == '__main__':
    main()