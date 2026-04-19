#!/usr/bin/env python3
"""
Smart Auto-Chunker - Paragraph-boundary chunking with no overlap
"""

import re
from typing import List


def split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs by '\n\n'."""
    paragraphs = text.split('\n\n')
    # Clean and filter
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    return paragraphs


def find_sentence_boundaries(text: str) -> List[int]:
    """Find positions of sentence endings (。！？)."""
    pattern = r'[。！？]'
    return [m.end() for m in re.finditer(pattern, text)]


def split_large_paragraph(paragraph: str, max_chars: int) -> List[str]:
    """Split a large paragraph at sentence boundaries."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    
    chunks = []
    start = 0
    
    while start < len(paragraph):
        # Find the best end position
        end = min(start + max_chars, len(paragraph))
        
        if end < len(paragraph):
            # Look for sentence boundary before max_chars
            search_text = paragraph[start:end]
            boundaries = find_sentence_boundaries(search_text)
            
            if boundaries:
                # Use the last sentence boundary
                end = start + boundaries[-1]
            else:
                # No sentence boundary found, use max_chars
                pass
        
        chunk = paragraph[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end
    
    return chunks


def auto_chunk(text: str, max_chars: int = 1800) -> List[str]:
    """
    Smart paragraph-boundary chunking with no overlap.
    
    Rules:
    - Each chunk stays UNDER max_chars total
    - NEVER split mid-paragraph
    - NO overlap between chunks
    - Large paragraphs split at sentence endings only
    """
    paragraphs = split_into_paragraphs(text)
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for paragraph in paragraphs:
        para_size = len(paragraph)
        
        # If paragraph is too large, split it
        if para_size > max_chars:
            # Save current chunk if any
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Split large paragraph
            para_chunks = split_large_paragraph(paragraph, max_chars)
            chunks.extend(para_chunks)
            continue
        
        # Check if adding this paragraph would exceed limit
        projected_size = current_size + (2 if current_chunk else 0) + para_size
        
        if projected_size <= max_chars:
            # Add to current chunk
            current_chunk.append(paragraph)
            current_size = projected_size
        else:
            # Save current chunk and start new one
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk = [paragraph]
            current_size = para_size
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def print_chunk_analysis(chunks: List[str], paragraphs: List[str]):
    """Print chunk analysis report."""
    sizes = [len(c) for c in chunks]
    
    print("┌──────────────────────────────────┐")
    print("│ Chunk Analysis                   │")
    print(f"│ Total paragraphs : {len(paragraphs):<14} │")
    print(f"│ Total chunks     : {len(chunks):<14} │")
    print(f"│ Min chunk chars  : {min(sizes):<14} │")
    print(f"│ Max chunk chars  : {max(sizes):<14} │")
    print(f"│ Avg chunk chars  : {sum(sizes)//len(sizes):<14} │")
    print("└──────────────────────────────────┘")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python chunker.py <input_file> [max_chars]")
        sys.exit(1)
    
    max_chars = int(sys.argv[2]) if len(sys.argv) >= 3 else 1800
    
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        text = f.read()
    
    paragraphs = split_into_paragraphs(text)
    chunks = auto_chunk(text, max_chars)
    
    print_chunk_analysis(chunks, paragraphs)
    
    # Print chunks
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i}/{len(chunks)} ({len(chunk)} chars) ---")
        print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
