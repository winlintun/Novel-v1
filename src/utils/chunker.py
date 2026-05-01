#!/usr/bin/env python3
"""
Smart Paragraph Chunking for Variable-Length Novel Text.

Implements token-aware paragraph grouping per need_to_fix.md spec.
REPLACES any fixed-size character splitting. Overlap is always 0.

Rules:
- ONLY split at paragraph boundaries (\n\n)
- NEVER split inside a paragraph, no matter how long
- Oversized single paragraphs become their own chunk
- overlap_size is always 0. No exceptions.
"""

from typing import List


def smart_chunk(text: str, max_tokens: int = 1500) -> List[str]:
    """
    Split novel text into translation-safe chunks.

    Rules:
    - Only splits at paragraph boundaries (double newline).
    - Never splits inside a paragraph.
    - Oversized single paragraphs become their own chunk.
    - overlap_size is always 0. No exceptions.

    Args:
        text:       Full chapter text (UTF-8 string).
        max_tokens: Max tokens per chunk. Default 1500.

    Returns:
        List of chunk strings. Each chunk is one or more complete paragraphs.
    """
    paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]  # remove empty

    chunks: List[str] = []
    current_group: List[str] = []
    current_tokens: int = 0

    for para in paragraphs:
        para_tokens = int(len(para) * 1.5)  # Myanmar/Chinese token estimate

        # Case B: single paragraph is too large — its own chunk
        if para_tokens > max_tokens:
            if current_group:
                chunks.append("\n\n".join(current_group))
                current_group = []
                current_tokens = 0
            chunks.append(para)
            continue

        # Case C: adding this paragraph would overflow — flush first
        if current_tokens + para_tokens > max_tokens:
            chunks.append("\n\n".join(current_group))
            current_group = [para]
            current_tokens = para_tokens

        # Case D: fits — add to current group
        else:
            current_group.append(para)
            current_tokens += para_tokens

    # Step 3: flush remainder
    if current_group:
        chunks.append("\n\n".join(current_group))

    return chunks


def get_rolling_context(
    prev_chunk: str,
    max_context_tokens: int = 400,
) -> str:
    """
    Extract the tail of the previous chunk as rolling context.

    Takes as many complete paragraphs from the END of prev_chunk
    as fit within max_context_tokens. Never truncates mid-paragraph.

    Args:
        prev_chunk:         The fully translated previous chunk (Myanmar text).
        max_context_tokens: Token budget for context. Default 400.

    Returns:
        String of complete paragraphs (≤ max_context_tokens).
        Empty string if this is the first chunk.
    """
    if not prev_chunk:
        return ""

    paragraphs = prev_chunk.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    if not paragraphs:
        return ""

    context: List[str] = []
    total_tokens: int = 0

    for para in reversed(paragraphs):
        para_tokens = int(len(para) * 1.5)
        if total_tokens + para_tokens > max_context_tokens:
            break
        context.insert(0, para)
        total_tokens += para_tokens

    return "\n\n".join(context)


def estimate_tokens(text: str) -> int:
    """Estimate token count for Myanmar/Chinese text.
    
    Myanmar + Chinese: 1 char ≈ 1.5 tokens — conservative estimate.
    """
    return int(len(text) * 1.5)
