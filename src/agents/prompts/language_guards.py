"""
Language Guard and Safety Constants
Prevents language leakage in translation output
"""

# Critical rule to prevent Chinese/English leakage
LANGUAGE_GUARD = """CRITICAL RULE — OBEY WITHOUT EXCEPTION:
You MUST output ONLY in Myanmar (Burmese) language using Myanmar Unicode script (U+1000–U+109F).

✅ CORRECT OUTPUT examples:
   "ဤအရာသည် မြန်မာဘာသာစကားဖြစ်သည်။"
   "ကျွန်တော်နားလည်ပါတယ်။"
   "ဒါက အရမ်းကောင်းတဲ့ စာအုပ်ပါ။"

❌ WRONG OUTPUT (Language contamination - NEVER DO THIS):
   "This is a book" - English words are FORBIDDEN
   "神仙打群架，正好被我撞到了" - Chinese characters are FORBIDDEN
   "这件事很扯" - Any Chinese text is FORBIDDEN  
   "นี่คือหนังสือ" - Thai script is FORBIDDEN
   "গাঢ়" / "অ" / "ক" - Bengali script is FORBIDDEN

⚠️ ABSOLUTE PROHIBITIONS - ZERO TOLERANCE:
- 🚫 NEVER output ANY Chinese characters (中文字符) - NOT EVEN ONE
- 🚫 NEVER output English words or phrases
- 🚫 NEVER output Thai script
- 🚫 NEVER output Bengali script (U+0980–U+09FF)
- 🚫 NEVER output Japanese or Korean
- 🚫 NEVER output Latin alphabet (a-z, A-Z) except in 【?term?】 placeholders
- 🚫 NEVER copy/paste the original Chinese input text
- 🚫 NEVER leave Chinese words untranslated in the output

VIOLATION CONSEQUENCE: Output containing ANY Chinese characters will be REJECTED completely.

CORRECT OUTPUT FORMAT:
- ALL text MUST be Myanmar Unicode characters (U+1000–U+109F) only
- Use 【?term?】 for unknown words - NEVER use Chinese or English as substitute
- Do NOT output <think>, <answer>, or any XML/HTML tags
- Do NOT output the original Chinese text
- Do NOT include Chinese phrases or colloquialisms
- Return ONLY the Myanmar translation. Zero preamble. Zero explanation.
- Myanmar ONLY. No exceptions. No Chinese allowed.
"""

# Unicode safety checklist for post-processing
UNICODE_SAFETY_CHECKLIST = """
UNICODE SAFETY VERIFICATION:
□ All characters are Myanmar Unicode (U+1000-U+109F) OR standard ASCII punctuation
□ No Chinese characters (CJK: U+4E00-U+9FFF) in output
□ No Korean Hangul (U+AC00-U+D7FF) in output  
□ No Bengali script (U+0980-U+09FF) in output
□ No Arabic script (U+0600-U+06FF) in output
□ No Thai script (U+0E00-U+0E7F) in output
□ ASCII question mark ? used (not Arabic ؟)
□ Myanmar Extended-A/B blocks (U+AA60-U+AA7F, U+A9E0-U+A9FF) preserved
"""
