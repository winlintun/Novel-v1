#!/usr/bin/env python3
"""
Test translation of the specific Chinese sentence with FIXED settings.
"""
import sys
sys.path.insert(0, '/home/wangyi/Desktop/Novel_Translation/novel_translation_project')

from src.utils.ollama_client import OllamaClient
from src.agents.prompt_patch import TRANSLATOR_SYSTEM_PROMPT

# Test sentence - colloquial, dialogue-heavy Chinese
chinese_text = "神仙打群架？千年难逢的事儿吧！正巧，被我撞到了！虽然很扯，但是事实！不要羡慕，不要鼓掌！说必要说明一下，我遇到的这波神仙，十分之不仗义，脾气太爆，火气太大，不够温柔，白白张了一幅仙风道骨、超然脱俗的外表，失望，失望的紧。不管怎样吧，咱不能鄙视人家，毕竟，咱的小命握在人家手中！"

print("=" * 80)
print("TEST TRANSLATION WITH FIXED SETTINGS")
print("=" * 80)
print(f"\nChinese Text:\n{chinese_text}\n")
print("=" * 80)

# Initialize client with FIXED settings
client = OllamaClient(
    model="qwen2.5:14b",
    base_url="http://localhost:11434",
    temperature=0.5,          # Increased for more natural dialogue
    top_p=0.92,
    top_k=50,
    repeat_penalty=1.3,       # Increased to prevent Myanmar char repetition
    max_retries=3,
    timeout=300
)

# Check if model is available
if not client.check_model_available():
    print("ERROR: Model qwen2.5:14b not available!")
    sys.exit(1)

print("\nSettings:")
print(f"  Model: qwen2.5:14b")
print(f"  Temperature: {client.temperature}")
print(f"  Top_p: {client.top_p}")
print(f"  Top_k: {client.top_k}")
print(f"  Repeat_penalty: {client.repeat_penalty}")
print("\n" + "=" * 80)
print("TRANSLATING...")
print("=" * 80 + "\n")

# Build user prompt with glossary and context
user_prompt = f"""GLOSSARY:
神仙 = နတ်ဆရာ (celestial being/immortal - note: informal/casual tone)
仙风道骨 = နတ်ဆရာသဏ္ဍာန် (immortal-like demeanor)
超然脱俗 = လောကဓာတ်မှအထက်တန်သော (transcendent, above worldly concerns)

PREVIOUS CONTEXT:
This is the narrator's opening monologue - very casual, colloquial, self-deprecating tone. First person perspective complaining about immortals.

SOURCE TEXT TO TRANSLATE:
{chinese_text}

MYANMAR TRANSLATION:"""

try:
    result = client.chat(
        prompt=user_prompt,
        system_prompt=TRANSLATOR_SYSTEM_PROMPT,
        stream=False
    )
    
    print("=" * 80)
    print("TRANSLATION RESULT:")
    print("=" * 80)
    print(result)
    print("\n" + "=" * 80)
    
    # Quality check
    myanmar_chars = sum(1 for c in result if '\u1000' <= c <= '\u109F')
    thai_chars = sum(1 for c in result if '\u0E00' <= c <= '\u0E7F')
    chinese_chars = sum(1 for c in result if '\u4E00' <= c <= '\u9FFF')
    english_chars = sum(1 for c in result if c.isascii() and c.isalpha())
    total_chars = len([c for c in result if not c.isspace()])
    
    print("\nQUALITY CHECK:")
    print(f"  Total non-space characters: {total_chars}")
    print(f"  Myanmar chars: {myanmar_chars} ({myanmar_chars/total_chars*100:.1f}%)")
    print(f"  Thai chars: {thai_chars} ({thai_chars/total_chars*100:.1f}%)")
    print(f"  Chinese chars: {chinese_chars} ({chinese_chars/total_chars*100:.1f}%)")
    print(f"  English chars: {english_chars} ({english_chars/total_chars*100:.1f}%)")
    
    if myanmar_chars/total_chars > 0.7 and thai_chars == 0:
        print(f"  Status: ✅ PASS - Good Myanmar ratio")
    else:
        print(f"  Status: ❌ FAIL - Quality issues detected")
    
    # Check for repetition
    sentences = [s.strip() for s in result.split('။') if s.strip()]
    unique_sentences = set(sentences)
    if len(sentences) > 0:
        repetition_ratio = 1 - (len(unique_sentences) / len(sentences))
        print(f"  Repetition: {repetition_ratio*100:.1f}% (lower is better)")
        if repetition_ratio > 0.3:
            print(f"  ⚠️  WARNING: High repetition detected!")
    
    # Save result to file for review
    with open('/home/wangyi/Desktop/Novel_Translation/novel_translation_project/test_result.txt', 'w', encoding='utf-8') as f:
        f.write("Chinese Source:\n")
        f.write(chinese_text)
        f.write("\n\n" + "=" * 80 + "\n\n")
        f.write("Myanmar Translation:\n")
        f.write(result)
        f.write("\n\n" + "=" * 80 + "\n\n")
        f.write(f"Quality Check:\n")
        f.write(f"  Myanmar ratio: {myanmar_chars/total_chars*100:.1f}%\n")
        f.write(f"  Thai chars: {thai_chars}\n")
        f.write(f"  Repetition: {repetition_ratio*100:.1f}%\n")
    
    print("\n✅ Result saved to: test_result.txt")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    client.cleanup()
