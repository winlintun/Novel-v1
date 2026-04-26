#!/usr/bin/env python3
import sys
import time
from src.utils.ollama_client import OllamaClient

def test_model():
    client = OllamaClient(
        model="padauk-gemma:q8_0",
        temperature=0.2,
        repeat_penalty=1.15
    )
    
    # Test 1: EN -> MM
    english_text = "Luo Qing, twelve years old, a villager of Luo Village in Xiao Rong Town."
    system_prompt_en_mm = "CRITICAL: Output ONLY Myanmar (Burmese) language using Myanmar Unicode script. NO English words or Chinese characters."
    
    print("Testing EN -> MM")
    print(f"Input: {english_text}")
    res = client.chat(prompt=english_text, system_prompt=system_prompt_en_mm)
    print(f"Output: {res}\n")

    time.sleep(1)

    # Test 2: CN -> MM
    chinese_text = "罗青，十二岁，小戎镇罗家村村民。"
    system_prompt_cn_mm = "You are an expert Chinese-to-Myanmar literary translator specializing in Wuxia/Xianxia novels. Output ONLY Myanmar text."
    
    print("Testing CN -> MM")
    print(f"Input: {chinese_text}")
    res2 = client.chat(prompt=chinese_text, system_prompt=system_prompt_cn_mm)
    print(f"Output: {res2}\n")

if __name__ == "__main__":
    test_model()
