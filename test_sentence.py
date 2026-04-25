#!/usr/bin/env python3
"""
Test translation of single sentence.
"""
import sys
sys.path.insert(0, '/home/wangyi/Desktop/Novel_Translation/novel_translation_project')

from src.utils.ollama_client import OllamaClient
from src.agents.prompt_patch import TRANSLATOR_SYSTEM_PROMPT

# Test sentence
chinese_text = "神仙打群架？千年难逢的事儿吧！正巧，被我撞到了！虽然很扯，但是事实！不要羡慕，不要鼓掌！说必要说明一下，我遇到的这波神仙，十分之不仗义，脾气太爆，火气太大，不够温柔，白白张了一幅仙风道骨、超然脱俗的外表，失望，失望的紧。不管怎样吧，咱不能鄙视人家，毕竟，咱的小命握在人家手中！"

print("=" * 80)
print("TRANSLATING SINGLE SENTENCE TEST")
print("=" * 80)
print(f"\nChinese:\n{chinese_text}\n")

client = OllamaClient(
    model="qwen2.5:14b",
    base_url="http://localhost:11434",
    temperature=0.5,
    top_p=0.92,
    top_k=50,
    repeat_penalty=1.3,
    max_retries=3,
    timeout=300
)

if not client.check_model_available():
    print("ERROR: Model not available!")
    sys.exit(1)

print("Translating...")
print("-" * 80)

user_prompt = f"""SOURCE TEXT TO TRANSLATE:
{chinese_text}

MYANMAR TRANSLATION:"""

try:
    result = client.chat(
        prompt=user_prompt,
        system_prompt=TRANSLATOR_SYSTEM_PROMPT
    )
    
    print("\nRESULT:")
    print("=" * 80)
    print(result)
    print("=" * 80)
    
    # Quality check
    myanmar_chars = sum(1 for c in result if '\u1000' <= c <= '\u109F')
    thai_chars = sum(1 for c in result if '\u0E00' <= c <= '\u0E7F')
    chinese_chars = sum(1 for c in result if '\u4E00' <= c <= '\u9FFF')
    english_chars = sum(1 for c in result if c.isascii() and c.isalpha())
    total_chars = len([c for c in result if not c.isspace()])
    
    print(f"\nQUALITY CHECK:")
    print(f"  Total: {total_chars}")
    print(f"  Myanmar: {myanmar_chars} ({myanmar_chars/total_chars*100:.1f}%)")
    print(f"  Thai: {thai_chars}")
    print(f"  Chinese: {chinese_chars}")
    print(f"  English: {english_chars}")
    
    if myanmar_chars/total_chars > 0.7:
        print("  Status: ✅ GOOD")
    else:
        print("  Status: ❌ BAD - Need fixes")
    
    # Save result
    with open('/home/wangyi/Desktop/Novel_Translation/novel_translation_project/test_sentence_result.txt', 'w', encoding='utf-8') as f:
        f.write(f"Chinese: {chinese_text}\n\n")
        f.write(f"Myanmar: {result}\n\n")
        f.write(f"Quality: Myanmar {myanmar_chars/total_chars*100:.1f}%\n")
    
    print("\nSaved to: test_sentence_result.txt")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    client.cleanup()
