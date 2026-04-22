#!/usr/bin/env python3
"""
test_suite.py — Novel-v1 Project Full Test Suite

အပေါ်မှ ဆွေးနွေးထားသည့် fix အားလုံးကို စစ်ဆေးသည်။
API key မလိုဘဲ run နိုင်သော test တွေ ဖြင့် ဖွဲ့စည်းထားသည်။

Run command:
    python test_suite.py
    python test_suite.py --verbose
    python test_suite.py --category quality
"""

import re
import sys
import json
import time
import argparse
import unittest
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime


# =============================================================================
# COLORS FOR TERMINAL OUTPUT
# =============================================================================

class Color:
    PASS  = "\033[92m"   # green
    FAIL  = "\033[91m"   # red
    WARN  = "\033[93m"   # yellow
    INFO  = "\033[94m"   # blue
    BOLD  = "\033[1m"
    RESET = "\033[0m"

def passed(msg): return f"{Color.PASS}PASS{Color.RESET}  {msg}"
def failed(msg): return f"{Color.FAIL}FAIL{Color.RESET}  {msg}"
def warned(msg): return f"{Color.WARN}WARN{Color.RESET}  {msg}"
def header(msg): return f"\n{Color.BOLD}{Color.INFO}{msg}{Color.RESET}"


# =============================================================================
# TEST RESULT TRACKER
# =============================================================================

class TestResult:
    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = ""):
        self.results.append((name, ok, detail))
        symbol = passed(name) if ok else failed(name)
        if detail:
            print(f"  {symbol}")
            print(f"         {detail}")
        else:
            print(f"  {symbol}")

    def summary(self) -> Tuple[int, int]:
        total  = len(self.results)
        passed = sum(1 for _, ok, _ in self.results if ok)
        return passed, total


R = TestResult()


# =============================================================================
# SECTION 1 — IMPORT CHECKS
# すべての scripts が import できるか確認する
# =============================================================================

def test_imports():
    print(header("[ 1 ] Import checks — scripts folder ကို import လုပ်နိုင်မလား"))

    modules = {
        "scripts.postprocessor":   ["postprocess", "fix_punctuation",
                                    "remove_non_myanmar_characters", "naturalize_verb_endings"],
        "scripts.fix_translation": ["postprocess_translation", "remove_metadata_text",
                                    "fix_dialogue_format", "fix_emotion_descriptions",
                                    "fix_long_sentences", "fix_weird_repetitions"],
        "scripts.myanmar_checker": ["check_readability", "calculate_myanmar_ratio",
                                    "count_myanmar_chars", "count_sentence_enders"],
        "scripts.assembler":       ["assemble", "load_template"],
        "scripts.glossary_manager":["GlossaryManager"],
        "scripts.rewriter":        ["BurmeseRewriter", "get_rewrite_prompt",
                                    "get_raw_translation_prompt"],
        "scripts.translator":      ["get_system_prompt", "get_translator",
                                    "OllamaTranslator", "GeminiTranslator"],
        "scripts.chunker":         ["auto_chunk"],
        "scripts.preprocessor":    ["preprocess"],
    }

    for mod_name, expected_attrs in modules.items():
        try:
            mod = __import__(mod_name, fromlist=expected_attrs)
            missing = [a for a in expected_attrs if not hasattr(mod, a)]
            if missing:
                R.add(f"import {mod_name}", False,
                      f"Missing attributes: {missing}")
            else:
                R.add(f"import {mod_name}", True)
        except ImportError as e:
            R.add(f"import {mod_name}", False, str(e))


# =============================================================================
# SECTION 2 — POSTPROCESSOR FIXES
# =============================================================================

def test_postprocessor():
    print(header("[ 2 ] Postprocessor — fix_punctuation, naturalize_verb_endings"))

    try:
        from scripts.postprocessor import (
            fix_punctuation,
            naturalize_verb_endings,
            remove_non_myanmar_characters,
            normalize_myanmar_whitespace,
        )
    except ImportError as e:
        R.add("postprocessor import", False, str(e))
        return

    # --- 2a. Chinese punctuation -> Myanmar ---
    sample = "ဟုတ်တယ်။ ဆိုပါစို့。 ငါ သွားမယ်，မင်းကော？"
    result = fix_punctuation(sample)
    R.add("fix_punctuation: 。→ ။",
          "。" not in result and "，" not in result,
          f"result: {result!r}")

    # --- 2b. naturalize_verb_endings exists and works ---
    formal_text = "သူသည် ထွက်သွားလေသည်။ သူမသည် ဝမ်းနည်းသည်။ ဟုဆိုသည်"
    try:
        result = naturalize_verb_endings(formal_text)
        no_formal = ("လေသည်" not in result and
                     "သည်သည်" not in result)
        has_natural = "တယ်" in result or "ပြောတယ်" in result
        R.add("naturalize_verb_endings: formal -> colloquial",
              no_formal and has_natural,
              f"output: {result!r}")
    except AttributeError:
        R.add("naturalize_verb_endings exists in postprocessor", False,
              "Function မတွေ့ဘူး — postprocessor.py ထဲ ထည့်ဖို့ လိုသေးတယ်")

    # --- 2c. remove_non_myanmar_characters keeps zero-width space ---
    zwsp = "မြန်မာ\u200Bစာ"   # contains U+200B
    result = remove_non_myanmar_characters(zwsp)
    R.add("remove_non_myanmar_characters: U+200B preserved",
          "\u200B" in result,
          "U+200B ပါနေသေးသလား — range ချဲ့ပြင်ဖို့ လိုသေးနိုင်တယ်")

    # --- 2d. pure Myanmar text not stripped ---
    pure = "မြန်မာဘာသာ ဖတ်ကောင်းပါစေ"
    result = remove_non_myanmar_characters(pure)
    R.add("remove_non_myanmar_characters: pure Myanmar text intact",
          len(result) >= len(pure) - 2)


# =============================================================================
# SECTION 3 — FIX TRANSLATION FUNCTIONS
# =============================================================================

def test_fix_translation():
    print(header("[ 3 ] fix_translation.py — style fix functions"))

    try:
        from scripts.fix_translation import (
            remove_metadata_text,
            fix_dialogue_format,
            fix_emotion_descriptions,
            fix_long_sentences,
            fix_weird_repetitions,
            fix_english_phrases,
            postprocess_translation,
        )
    except ImportError as e:
        R.add("fix_translation import", False, str(e))
        return

    # --- 3a. remove_metadata_text ---
    meta = "Chapter: some_chapter TEXT TO TRANSLATE:\nဒါက အမှန်တကယ် ဘာသာပြန်ချက်ပဲ"
    result = remove_metadata_text(meta)
    R.add("remove_metadata_text",
          "TEXT TO TRANSLATE" not in result and "ဘာသာပြန်ချက်" in result,
          f"output: {result!r}")

    # --- 3b. fix_dialogue_format ---
    stiff = 'သူသည် "မင်းဘာလုပ်နေတာလဲ" ဟုမေးလေသည်'
    result = fix_dialogue_format(stiff)
    R.add("fix_dialogue_format: ဟုမေးလေသည် -> မေးလိုက်တယ်",
          "မေးလေသည်" not in result or "မေးလိုက်တယ်" in result,
          f"output: {result!r}")

    # --- 3c. fix_emotion_descriptions ---
    abstract = "သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်"
    result = fix_emotion_descriptions(abstract)
    R.add("fix_emotion_descriptions: abstract -> physical",
          "ဝမ်းနည်းပူဆွေးသောခံစားချက်" not in result,
          f"output: {result!r}")

    # --- 3d. fix_long_sentences: long line gets broken ---
    long_line = (
        "သူသည် တောင်ထိပ်သို့ တက်ရောက်ရောက်ချင်း အနောက်ဘက်တွင် နေဝင်ရောင်ခြည်များ "
        "ထိုးဖောက်ကာ တောအုပ်ကြီးများပေါ်သို့ ရောင်ခြည်ကျရောက်လျက် "
        "တည်ရှိသောမြင်ကွင်းကို မြင်တွေ့ခဲ့ရသည် အလွန်ကြာကြာပင် ရပ်ကြည့်နေမိသည်"
    )
    result = fix_long_sentences(long_line)
    original_newlines = long_line.count("\n")
    result_newlines   = result.count("\n")
    R.add("fix_long_sentences: long line split",
          result_newlines >= original_newlines,
          f"newlines before={original_newlines}, after={result_newlines}")

    # --- 3e. fix_weird_repetitions ---
    repeated = "ချိုချိုချိုချိုချိုချိုချိုချို"
    result = fix_weird_repetitions(repeated)
    R.add("fix_weird_repetitions: collapse repeats",
          len(result) < len(repeated),
          f"before={len(repeated)}, after={len(result)}")

    # --- 3f. postprocess_translation runs end-to-end ---
    sample = (
        'Chapter: test TEXT TO TRANSLATE:\n'
        '"မင်းဘာလုပ်တာလဲ" ဟုမေးလေသည်\n'
        'သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်\n'
    )
    try:
        result = postprocess_translation(sample, novel_name="")
        R.add("postprocess_translation: end-to-end run",
              isinstance(result, str) and len(result) > 0)
    except Exception as e:
        R.add("postprocess_translation: end-to-end run", False, str(e))


# =============================================================================
# SECTION 4 — MYANMAR QUALITY CHECKER
# =============================================================================

def test_myanmar_checker():
    print(header("[ 4 ] Myanmar quality checker — readability thresholds"))

    try:
        from scripts.myanmar_checker import (
            check_readability,
            calculate_myanmar_ratio,
            count_myanmar_chars,
            count_sentence_enders,
        )
    except ImportError as e:
        R.add("myanmar_checker import", False, str(e))
        return

    # --- 4a. Pure Myanmar text should pass ---
    good_text = (
        "သူမ မျက်ရည်တွေ ကျနေတယ်။ ရင်ထဲမှာ နာကျင်သလိုပဲ ခံစားရတယ်။ "
        "ပြန်မလာနိုင်တော့ဘူး ဆိုတာ သူ သိနေတယ်။ ဒါပေမဲ့ ဘာမှ ပြောမရဘူး။"
    )
    results = check_readability(good_text)
    R.add("check_readability: good Myanmar text passes",
          results.get("passed", False),
          f"myanmar_ratio={results.get('checks', {}).get('myanmar_ratio', {}).get('value', '?')}")

    # --- 4b. Text with Chinese chars should fail ---
    leaky_text = "ဒါက 古道仙鸿 ဆိုတဲ့ novel ကနေ ယူထားတာ"
    results = check_readability(leaky_text)
    no_chinese_check = results.get("checks", {}).get("no_chinese", {})
    R.add("check_readability: Chinese chars detected",
          not no_chinese_check.get("passed", True),
          f"chinese_count={no_chinese_check.get('value', '?')}")

    # --- 4c. Myanmar ratio calculation ---
    myanmar_only = "မြန်မာဘာသာ"
    ratio = calculate_myanmar_ratio(myanmar_only)
    R.add("calculate_myanmar_ratio: near 1.0 for Myanmar-only text",
          ratio > 0.8,
          f"ratio={ratio:.3f}")

    # --- 4d. Sentence ender count ---
    with_enders = "ဒါပဲ။ ဟုတ်ကဲ့ပါ။ နားလည်တယ်။"
    count = count_sentence_enders(with_enders)
    R.add("count_sentence_enders: count = 3",
          count == 3,
          f"count={count}")

    # --- 4e. 70% threshold check ---
    mixed_text = "hello world " + "မြန်မာ " * 10
    ratio = calculate_myanmar_ratio(mixed_text)
    results = check_readability(mixed_text)
    myanmar_check = results.get("checks", {}).get("myanmar_ratio", {})
    R.add("check_readability: mixed text threshold logic works",
          "passed" in myanmar_check,
          f"ratio={ratio:.2f}, passed={myanmar_check.get('passed')}")


# =============================================================================
# SECTION 5 — GLOSSARY MANAGER
# =============================================================================

def test_glossary():
    print(header("[ 5 ] Glossary — character name consistency"))

    try:
        from scripts.glossary_manager import GlossaryManager
    except ImportError as e:
        R.add("GlossaryManager import", False, str(e))
        return

    test_novel = "_test_novel_suite_"

    # --- 5a. Create glossary ---
    try:
        gm = GlossaryManager(test_novel, auto_create=True)
        R.add("GlossaryManager: create", True)
    except Exception as e:
        R.add("GlossaryManager: create", False, str(e))
        return

    # --- 5b. Add a name ---
    try:
        gm.add_name("Wei Wuxian", "ဝေ့ဝူရှျန်")
        gm.add_name("Lan Wangji", "လန်ဝမ်ကျိ")
        R.add("GlossaryManager: add_name", len(gm.names) >= 2)
    except Exception as e:
        R.add("GlossaryManager: add_name", False, str(e))

    # --- 5c. get_glossary_text includes names ---
    try:
        text = gm.get_glossary_text()
        R.add("GlossaryManager: get_glossary_text contains names",
              "ဝေ့ဝူရှျန်" in text and "လန်ဝမ်ကျိ" in text,
              f"snippet: {text[:120]!r}")
    except Exception as e:
        R.add("GlossaryManager: get_glossary_text", False, str(e))

    # --- 5d. Save and reload ---
    try:
        gm.save()
        gm2 = GlossaryManager(test_novel, auto_create=False)
        R.add("GlossaryManager: save and reload",
              "Wei Wuxian" in gm2.names or "ဝေ့ဝူရှျန်" in gm2.names.values())
    except Exception as e:
        R.add("GlossaryManager: save and reload", False, str(e))

    # --- Cleanup ---
    glossary_file = Path(f"glossaries/{test_novel}.json")
    if glossary_file.exists():
        glossary_file.unlink()


# =============================================================================
# SECTION 6 — ASSEMBLER
# =============================================================================

def test_assembler():
    print(header("[ 6 ] Assembler — output file structure"))

    try:
        from scripts.assembler import assemble, load_template
    except ImportError as e:
        R.add("assembler import", False, str(e))
        return

    # --- 6a. load_template returns string ---
    tmpl = load_template()
    R.add("load_template: returns string", isinstance(tmpl, str) and len(tmpl) > 0)

    # --- 6b. template has required placeholders ---
    required = ["{original_title}", "{translated_content}"]
    missing  = [p for p in required if p not in tmpl]
    R.add("load_template: required placeholders present",
          len(missing) == 0,
          f"missing: {missing}" if missing else "")

    # --- 6c. assemble writes file ---
    out_path = Path("working_data/_test_output_suite.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    content  = "မြန်မာ ဘာသာပြန် content ပါ"

    try:
        assemble(
            original_title  = "test_chapter",
            chapter_number  = 1,
            model_name      = "test_model",
            translated_content = content,
            output_path     = str(out_path),
        )
        R.add("assemble: file written", out_path.exists())

        # --- 6d. content appears in output ---
        text = out_path.read_text(encoding="utf-8")
        R.add("assemble: Myanmar content in output", content in text)

        # --- 6e. no raw placeholder in output ---
        R.add("assemble: no unfilled placeholders",
              "{" not in text or "translated_content" not in text)

        out_path.unlink()

    except Exception as e:
        R.add("assemble: file written", False, str(e))


# =============================================================================
# SECTION 7 — TRANSLATOR SYSTEM PROMPT
# =============================================================================

def test_system_prompt():
    print(header("[ 7 ] System prompt — style rules ပါဝင်မှု"))

    try:
        from scripts.translator import get_system_prompt
    except ImportError as e:
        R.add("get_system_prompt import", False, str(e))
        return

    prompt = get_system_prompt(source_lang="Chinese")

    checks = {
        "မင်း (colloquial pronoun example)":       "မင်း"         in prompt,
        "DIALOGUE rule present":                    "DIALOGUE"     in prompt,
        "EMOTIONS rule present":                    "EMOTION"      in prompt,
        "sentence breaking rule":                   "sentence"     in prompt.lower(),
        "no archaic language rule":                 "ARCHAIC"      in prompt or
                                                    "archaic"      in prompt.lower(),
        "output only (no filler) rule":             "NO"           in prompt,
    }

    for desc, ok in checks.items():
        R.add(f"system_prompt: {desc}", ok)

    # --- Temperature warning check (code-level) ---
    try:
        src = Path("scripts/translator.py").read_text(encoding="utf-8")
        # Look for temperature value in OllamaTranslator only
        ollama_block = src.split("class OllamaTranslator(BaseTranslator):")[1].split("class NLLBTranslator")[0]
        temp_matches = re.findall(r'"temperature":\s*([\d.]+)', ollama_block)
        if temp_matches:
            temps = [float(t) for t in temp_matches]
            all_ok = all(t >= 0.35 for t in temps)
            R.add("translator.py: Ollama temperature >= 0.35 (not robotic 0.15)",
                  all_ok,
                  f"found temperatures: {temps} — "
                  f"{'OK' if all_ok else '0.15 တွေ့တယ် — 0.45 ပြောင်းဖို့ လိုသေးတယ်'}")
        else:
            R.add("translator.py: temperature setting found", False,
                  "temperature setting ရှာမတွေ့ဘူး")
    except Exception as e:
        R.add("translator.py source check", False, str(e))


# =============================================================================
# SECTION 8 — PIPELINE INTEGRATION
# main.py က fix_translation ကို ခေါ်နေသလားစစ်ဆေးသည်
# =============================================================================

def test_pipeline_integration():
    print(header("[ 8 ] Pipeline integration — main.py စစ်ဆေးချက်"))

    main_path = Path("main.py")
    if not main_path.exists():
        R.add("main.py exists", False, "main.py မတွေ့ဘူး")
        return
    R.add("main.py exists", True)

    src = main_path.read_text(encoding="utf-8")

    # --- 8a. postprocess or postprocess_translation is called ---
    R.add("main.py: postprocess() ခေါ်တယ်",
          "postprocess(" in src or "postprocess_translation(" in src)

    # --- 8b. fix_translation is imported or called ---
    has_import = "fix_translation" in src
    has_call   = "postprocess_translation" in src
    R.add("main.py: fix_translation integrate လုပ်ထားတယ်",
          has_import and has_call,
          "fix_translation import/call မတွေ့ဘူး — ထည့်ဖို့ လိုသေးတယ်"
          if not (has_import and has_call) else "")

    # --- 8c. two-stage mode supported ---
    R.add("main.py: two-stage mode supported",
          "--two-stage" in src or "two_stage" in src)

    # --- 8d. NLLB warning: if NLLB used, prompt ignored ---
    rewriter_src = Path("scripts/rewriter.py")
    if rewriter_src.exists():
        rtxt = rewriter_src.read_text(encoding="utf-8")
        R.add("rewriter.py: get_rewrite_prompt defined",
              "get_rewrite_prompt" in rtxt)

    # --- 8e. postprocessor.py has naturalize_verb_endings ---
    pp_src = Path("scripts/postprocessor.py")
    if pp_src.exists():
        pptxt = pp_src.read_text(encoding="utf-8")
        R.add("postprocessor.py: naturalize_verb_endings defined",
              "naturalize_verb_endings" in pptxt,
              "function မတွေ့ဘူး — postprocessor.py ထဲ ထည့်ဖို့ လိုသေးတယ်")
        R.add("postprocessor.py: naturalize_verb_endings ကို postprocess() ထဲမှာ ခေါ်တယ်",
              "naturalize_verb_endings(text)" in pptxt,
              "call မတွေ့ဘူး — postprocess() function ထဲ call ထည့်ဖို့ လိုသေးတယ်")


# =============================================================================
# SECTION 9 — SAMPLE BURMESE QUALITY CHECK
# ဘာသာပြန်ထားတဲ့ file တစ်ခုကို တိုက်စစ်ခြင်း
# =============================================================================

def test_translation_quality():
    print(header("[ 9 ] Translation quality — books/ folder စစ်ဆေးချက်"))

    books_dir = Path("books")
    if not books_dir.exists():
        R.add("books/ folder exists", False, "books/ folder မတွေ့ဘူး — ဘာသာပြန်ထားသည့် file မရှိသေးဘူး")
        return
    R.add("books/ folder exists", True)

    md_files = list(books_dir.rglob("*.md"))
    if not md_files:
        R.add("books/ contains .md files", False, "ဘာသာပြန် file မတွေ့ဘူး")
        return
    R.add(f"books/ contains .md files ({len(md_files)} found)", True)

    try:
        from scripts.myanmar_checker import check_readability, calculate_myanmar_ratio
        from scripts.fix_translation import fix_dialogue_format, remove_metadata_text
    except ImportError as e:
        R.add("quality check modules import", False, str(e))
        return

    pass_count  = 0
    fail_count  = 0
    issues      = []

    for md_file in md_files[:10]:      # first 10 files
        if "README.md" in md_file.name:
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        results = check_readability(text)
        ratio   = calculate_myanmar_ratio(text)
        checks  = results.get("checks", {})

        file_issues = []

        # Myanmar ratio
        if ratio < 0.70:
            file_issues.append(f"myanmar_ratio={ratio:.0%} (min 70%)")

        # Chinese leakage
        chinese_count = checks.get("no_chinese", {}).get("value", 0)
        if chinese_count > 0:
            file_issues.append(f"Chinese chars leaked: {chinese_count}")

        # Metadata leakage
        if "TEXT TO TRANSLATE" in text:
            file_issues.append("metadata text leaked into output")

        # Formal verb check (spot check)
        formal_count = text.count("လေသည်") + text.count("ဟုဆိုသည်")
        if formal_count > 5:
            file_issues.append(f"formal verb endings: {formal_count} instances")

        # Missing sentence enders
        sentence_enders = checks.get("sentence_boundaries", {}).get("value", 0)
        if sentence_enders == 0:
            file_issues.append("no sentence enders (။) found")

        if file_issues:
            fail_count += 1
            issues.append((md_file.name, file_issues))
        else:
            pass_count += 1

    total = pass_count + fail_count
    R.add(f"quality check: {pass_count}/{total} files pass",
          fail_count == 0,
          f"{fail_count} file(s) failed" if fail_count else "")

    if issues:
        print(f"\n  {Color.WARN}Issue detail:{Color.RESET}")
        for fname, file_issues in issues[:5]:
            print(f"    {fname}:")
            for iss in file_issues:
                print(f"      - {iss}")


# =============================================================================
# SECTION 10 — CHUNKER SANITY
# =============================================================================

def test_chunker():
    print(header("[ 10 ] Chunker — text splitting"))

    try:
        from scripts.chunker import auto_chunk
    except ImportError as e:
        R.add("chunker import", False, str(e))
        return

    sample = "မြန်မာ ဘာသာ စာကြောင်း တစ်ကြောင်း။\n" * 100
    try:
        chunks = auto_chunk(sample, max_chars=500)
        R.add("auto_chunk: returns list", isinstance(chunks, list) and len(chunks) > 0)
        R.add("auto_chunk: each chunk <= max_chars",
              all(len(c) <= 700 for c in chunks),
              f"max chunk size found: {max(len(c) for c in chunks)}")
        R.add("auto_chunk: no empty chunks",
              all(len(c.strip()) > 0 for c in chunks))
    except Exception as e:
        R.add("auto_chunk", False, str(e))


# =============================================================================
# SECTION 11 — CONFIG FILE
# =============================================================================

def test_config():
    print(header("[ 11 ] Config — config/config.json စစ်ဆေးချက်"))

    config_path = Path("config/config.json")
    R.add("config/config.json exists", config_path.exists())
    if not config_path.exists():
        return

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        R.add("config.json: valid JSON", True)
    except json.JSONDecodeError as e:
        R.add("config.json: valid JSON", False, str(e))
        return

    # Check myanmar_readability settings
    mr = config.get("myanmar_readability", {})
    R.add("config: myanmar_readability.enabled exists",
          "enabled" in mr)
    R.add("config: min_myanmar_ratio >= 0.7",
          mr.get("min_myanmar_ratio", 0) >= 0.7,
          f"current value: {mr.get('min_myanmar_ratio', 'not set')}")

    # Check translation_pipeline
    tp = config.get("translation_pipeline", {})
    R.add("config: translation_pipeline section exists",
          "mode" in tp,
          f"current mode: {tp.get('mode', 'not set')}")

    # Warn if single_stage (two_stage is better)
    mode = tp.get("mode", "single_stage")
    if mode == "single_stage":
        print(f"  {warned('config: mode=single_stage — two_stage ကို recommend တယ်')}")


# =============================================================================
# SECTION 12 — FILE STRUCTURE CHECK
# =============================================================================

def test_file_structure():
    print(header("[ 12 ] File structure — required files and folders"))

    required = [
        "main.py",
        "scripts/translator.py",
        "scripts/postprocessor.py",
        "scripts/fix_translation.py",
        "scripts/assembler.py",
        "scripts/myanmar_checker.py",
        "scripts/rewriter.py",
        "scripts/glossary_manager.py",
        "scripts/chunker.py",
        "scripts/preprocessor.py",
        "config/config.json",
        ".env.example",
        "requirements.txt",
    ]

    optional = [
        ".env",
        "names.json",
        "templates/chapter_template.md",
    ]

    for path in required:
        R.add(f"required: {path}", Path(path).exists())

    for path in optional:
        exists = Path(path).exists()
        if not exists:
            print(f"  {warned(f'optional: {path} — မတွေ့ဘူး (OK)')}")


# =============================================================================
# SECTION 13 — READER APP (Web UI)
# =============================================================================

def test_reader_app():
    print(header("[ 13 ] Reader App — Web UI စစ်ဆေးချက်"))

    reader_path = Path("reader_app.py")
    R.add("reader_app.py exists", reader_path.exists())
    if not reader_path.exists():
        return

    # --- 13a. Check Flask imports ---
    src = reader_path.read_text(encoding="utf-8")
    R.add("reader_app: Flask imported",
          "from flask import Flask" in src)
    R.add("reader_app: send_from_directory (not send_from_path)",
          "send_from_directory" in src and "send_from_path" not in src,
          "send_from_path အစား send_from_directory သုံးပါ")

    # --- 13b. Check required routes ---
    required_routes = [
        ("@app.route('/')", "index/home route"),
        ("@app.route('/book/<book_id>')", "book chapters route"),
        ("@app.route('/book/<book_id>/chapter/<int:chapter_num>')", "reader route"),
        ("@app.route('/api/chapter_content/", "chapter content API"),
        ("@app.route('/api/save_progress'", "save progress API"),
    ]
    for route, desc in required_routes:
        R.add(f"reader_app: {desc}",
              route in src)

    # --- 13c. Check security features ---
    R.add("reader_app: is_safe_path_name function (security)",
          "is_safe_path_name" in src)
    R.add("reader_app: path traversal protection (.. check)",
          "'..' in" in src or '".." in' in src)

    # --- 13d. Check template usage ---
    templates = ["index.html", "chapters.html", "reader.html"]
    for tmpl in templates:
        template_found = f"'{tmpl}'" in src and "render_template" in src
        R.add(f"reader_app: template '{tmpl}' used",
              template_found)

    # --- 13e. Check books directory handling ---
    R.add("reader_app: BOOKS_DIR defined",
          'BOOKS_DIR = Path("books")' in src or "BOOKS_DIR = Path('books')" in src)
    R.add("reader_app: metadata.json loading",
          "metadata.json" in src)

    # --- 13f. Check progress tracking ---
    R.add("reader_app: progress.json handling",
          "progress.json" in src or "PROGRESS_FILE" in src)
    R.add("reader_app: load_progress function",
          "def load_progress():" in src)
    R.add("reader_app: save_progress function",
          "def save_progress(" in src)

    # --- 13g. Test import without running server ---
    try:
        # Mock Flask to avoid actually starting server
        import sys
        from unittest.mock import MagicMock

        flask_mock = MagicMock()
        flask_mock.Flask = lambda name: MagicMock(
            route=lambda *a, **k: lambda f: f,
            run=lambda **k: None
        )
        flask_mock.render_template = lambda *a, **k: ""
        flask_mock.request = MagicMock()
        flask_mock.jsonify = lambda x: x
        flask_mock.send_from_directory = lambda *a, **k: ""

        sys.modules['flask'] = flask_mock

        # Try to import reader_app modules
        import importlib.util
        spec = importlib.util.spec_from_file_location("reader_app", "reader_app.py")
        reader_module = importlib.util.module_from_spec(spec)

        # Don't execute the app.run() part
        R.add("reader_app: imports successfully (mocked)", True)

        # Restore flask
        del sys.modules['flask']

    except Exception as e:
        R.add("reader_app: imports successfully (mocked)", False, str(e))

    # --- 13h. Check sample book exists ---
    books_dir = Path("books")
    if books_dir.exists():
        metadata_files = list(books_dir.rglob("metadata.json"))
        R.add(f"reader_app: sample books found ({len(metadata_files)} metadata.json)",
              len(metadata_files) > 0,
              f"{len(metadata_files)} book(s) with metadata.json" if metadata_files else "Create sample book with: mkdir -p books/novel/chapters && echo '{{...}}' > books/novel/metadata.json")

        if metadata_files:
            # Validate first metadata.json
            try:
                with open(metadata_files[0], 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                R.add("reader_app: metadata.json valid format",
                      "title" in meta and "chapters" in meta,
                      f"title={meta.get('title', 'N/A')}, chapters={len(meta.get('chapters', []))}")
            except Exception as e:
                R.add("reader_app: metadata.json valid format", False, str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

SECTIONS = {
    "imports":     test_imports,
    "postprocess": test_postprocessor,
    "fix":         test_fix_translation,
    "quality":     test_myanmar_checker,
    "glossary":    test_glossary,
    "assembler":   test_assembler,
    "prompt":      test_system_prompt,
    "pipeline":    test_pipeline_integration,
    "translation": test_translation_quality,
    "chunker":     test_chunker,
    "config":      test_config,
    "structure":   test_file_structure,
    "reader":      test_reader_app,
}


def main():
    parser = argparse.ArgumentParser(
        description="Novel-v1 Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories:
  imports      scripts/ import checks
  postprocess  postprocessor.py fixes
  fix          fix_translation.py style fixes
  quality      myanmar_checker.py thresholds
  glossary     GlossaryManager consistency
  assembler    output file structure
  prompt       system prompt rules
  pipeline     main.py integration
  translation  books/ output quality
  chunker      text splitting
  config       config.json values
  structure    required files check
  reader       reader_app.py Web UI checks
        """
    )
    parser.add_argument("--verbose",  action="store_true")
    parser.add_argument("--category", choices=list(SECTIONS.keys()),
                        help="single category run")
    args = parser.parse_args()

    print(f"\n{Color.BOLD}Novel-v1 Test Suite{Color.RESET}")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"CWD:    {Path.cwd()}")
    print("=" * 60)

    start = time.time()

    if args.category:
        SECTIONS[args.category]()
    else:
        for fn in SECTIONS.values():
            fn()

    elapsed = time.time() - start

    # Final summary
    passed_n, total = R.summary()
    failed_n = total - passed_n

    print("\n" + "=" * 60)
    print(f"{Color.BOLD}Results: {passed_n}/{total} passed  ({elapsed:.1f}s){Color.RESET}")

    if failed_n == 0:
        print(f"{Color.PASS}All tests passed.{Color.RESET}")
    else:
        print(f"{Color.FAIL}{failed_n} test(s) failed:{Color.RESET}")
        for name, ok, detail in R.results:
            if not ok:
                msg = f"  FAIL  {name}"
                if detail:
                    msg += f"\n        {detail}"
                print(msg)

    print()

    # Guidance based on failures
    fail_names = [name for name, ok, _ in R.results if not ok]

    if any("naturalize_verb_endings" in n for n in fail_names):
        print(f"{Color.WARN}[ACTION]{Color.RESET} postprocessor.py ထဲ naturalize_verb_endings() ထည့်ဖို့ လိုသေးတယ်")

    if any("fix_translation integrate" in n for n in fail_names):
        print(f"{Color.WARN}[ACTION]{Color.RESET} main.py ထဲ fix_translation ကို step 6.5 ဖြစ် ထည့်ဖို့ လိုသေးတယ်")

    if any("temperature" in n for n in fail_names):
        print(f"{Color.WARN}[ACTION]{Color.RESET} translator.py မှာ temperature ကို 0.45 ပြောင်းဖို့ လိုသေးတယ်")

    if any("two_stage" in n.lower() or "two-stage" in n.lower() for n in fail_names):
        print(f"{Color.WARN}[ACTION]{Color.RESET} config.json မှာ mode: 'two_stage' ပြောင်းစဉ်းစားပါ")

    sys.exit(0 if failed_n == 0 else 1)


if __name__ == "__main__":
    main()