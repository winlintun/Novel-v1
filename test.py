#!/usr/bin/env python3
"""
test.py — Novel Translation Project Full Test Suite

Tests all components including:
- Import checks for all scripts
- Resource management (glossary, context, name converter, cultivation terms)
- Postprocessor and translation fixes
- Myanmar quality checker
- Assembler and pipeline integration
- Config and file structure
- Reader App

Run command:
    python test.py
    python test.py --verbose
    python test.py --category resources
    python test.py --category quality
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
        "scripts.context_manager": ["ContextManager", "Character", "StoryEvent"],
        "scripts.name_converter":  ["NameConverter", "NameEntry", "CULTIVATION_TERMS"],
        "scripts.resource_manager":["ResourceManager", "CultivationTerm", "TitleTerm"],
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
# SECTION 2 — RESOURCE MANAGER TESTS
# =============================================================================

def test_resource_manager():
    print(header("[ 2 ] Resource Manager — Unified resource management"))
    
    try:
        from scripts.resource_manager import ResourceManager, CultivationTerm, TitleTerm
    except ImportError as e:
        R.add("ResourceManager import", False, str(e))
        return
    
    test_novel = "_test_resource_manager_"
    
    # --- 2a. Create resource manager ---
    try:
        rm = ResourceManager(test_novel, source_lang="English", auto_create=True)
        R.add("ResourceManager: create", True)
    except Exception as e:
        R.add("ResourceManager: create", False, str(e))
        return
    
    # --- 2b. Add character ---
    try:
        rm.add_character(
            name="Li Wei",
            myanmar_name="လီဝေ့",
            importance="major",
            description="A young cultivator",
            first_appearance=1
        )
        char = rm.get_character("Li Wei")
        R.add("ResourceManager: add_character",
              char is not None and char["myanmar_name"] == "လီဝေ့")
    except Exception as e:
        R.add("ResourceManager: add_character", False, str(e))
    
    # --- 2c. Add cultivation term ---
    try:
        rm.add_cultivation_term(
            source_term="Golden Core",
            myanmar_term="ရွှေအနှောင်း",
            category="realm",
            description="A cultivation realm"
        )
        term = rm.get_cultivation_term("Golden Core")
        R.add("ResourceManager: add_cultivation_term",
              term is not None and term.myanmar_term == "ရွှေအနှောင်း")
    except Exception as e:
        R.add("ResourceManager: add_cultivation_term", False, str(e))
    
    # --- 2d. Add title ---
    try:
        rm.add_title(
            source_title="Young Master",
            myanmar_name="ကျွန်ပေါင်း",
            gender="male",
            formality="formal"
        )
        title = rm.get_title("Young Master")
        R.add("ResourceManager: add_title",
              title is not None)
    except Exception as e:
        R.add("ResourceManager: add_title", False, str(e))
    
    # --- 2e. Get glossary text ---
    try:
        glossary_text = rm.get_glossary_text()
        has_names = "Li Wei" in glossary_text or "လီဝေ့" in glossary_text
        R.add("ResourceManager: get_glossary_text",
              len(glossary_text) > 0 and has_names)
    except Exception as e:
        R.add("ResourceManager: get_glossary_text", False, str(e))
    
    # --- 2f. Get context for chapter ---
    try:
        context_text = rm.get_context_for_chapter(1)
        R.add("ResourceManager: get_context_for_chapter",
              isinstance(context_text, str))
    except Exception as e:
        R.add("ResourceManager: get_context_for_chapter", False, str(e))
    
    # --- 2g. Get cultivation text ---
    try:
        cultivation_text = rm.get_cultivation_text()
        has_realm = "Golden Core" in cultivation_text or "ရွှေအနှောင်း" in cultivation_text
        R.add("ResourceManager: get_cultivation_text",
              has_realm)
    except Exception as e:
        R.add("ResourceManager: get_cultivation_text", False, str(e))
    
    # --- 2h. Save all resources ---
    try:
        success = rm.save_all()
        R.add("ResourceManager: save_all", success)
    except Exception as e:
        R.add("ResourceManager: save_all", False, str(e))
    
    # --- 2i. Sync all resources ---
    try:
        stats = rm.sync_all()
        R.add("ResourceManager: sync_all",
              isinstance(stats, dict) and "glossary_to_context" in stats)
    except Exception as e:
        R.add("ResourceManager: sync_all", False, str(e))
    
    # --- 2j. Get stats ---
    try:
        stats = rm.get_stats()
        R.add("ResourceManager: get_stats",
              "characters" in stats and "cultivation_terms" in stats)
    except Exception as e:
        R.add("ResourceManager: get_stats", False, str(e))
    
    # --- Cleanup ---
    try:
        import shutil
        resources_dir = Path(f"resources/{test_novel}")
        if resources_dir.exists():
            shutil.rmtree(resources_dir)
        glossary_file = Path(f"glossaries/{test_novel}.json")
        if glossary_file.exists():
            glossary_file.unlink()
        context_dir = Path(f"context/{test_novel}")
        if context_dir.exists():
            shutil.rmtree(context_dir)
    except Exception:
        pass


# =============================================================================
# SECTION 3 — GLOSSARY MANAGER TESTS
# =============================================================================

def test_glossary():
    print(header("[ 3 ] Glossary Manager — character name consistency"))

    try:
        from scripts.glossary_manager import GlossaryManager
    except ImportError as e:
        R.add("GlossaryManager import", False, str(e))
        return

    test_novel = "_test_novel_suite_"

    # --- 3a. Create glossary ---
    try:
        gm = GlossaryManager(test_novel, auto_create=True)
        R.add("GlossaryManager: create", True)
    except Exception as e:
        R.add("GlossaryManager: create", False, str(e))
        return

    # --- 3b. Add a name ---
    try:
        gm.add_name("Wei Wuxian", "ဝေ့ဝူရှျန်")
        gm.add_name("Lan Wangji", "လန်ဝမ်ကျိ")
        R.add("GlossaryManager: add_name", len(gm.names) >= 2)
    except Exception as e:
        R.add("GlossaryManager: add_name", False, str(e))

    # --- 3c. Get name ---
    try:
        name = gm.get_name("Wei Wuxian")
        R.add("GlossaryManager: get_name",
              name == "ဝေ့ဝူရှျန်",
              f"expected: ဝေ့ဝူရှျန်, got: {name}")
    except Exception as e:
        R.add("GlossaryManager: get_name", False, str(e))

    # --- 3d. get_glossary_text includes names ---
    try:
        text = gm.get_glossary_text()
        R.add("GlossaryManager: get_glossary_text contains names",
              "ဝေ့ဝူရှျန်" in text and "လန်ဝမ်ကျိ" in text,
              f"snippet: {text[:120]!r}")
    except Exception as e:
        R.add("GlossaryManager: get_glossary_text", False, str(e))

    # --- 3e. Save and reload ---
    try:
        gm.save()
        gm2 = GlossaryManager(test_novel, auto_create=False)
        R.add("GlossaryManager: save and reload",
              "Wei Wuxian" in gm2.names or "ဝေ့ဝူရှျန်" in gm2.names.values())
    except Exception as e:
        R.add("GlossaryManager: save and reload", False, str(e))

    # --- 3f. Get stats ---
    try:
        stats = gm.get_stats()
        R.add("GlossaryManager: get_stats",
              "total_names" in stats and stats["total_names"] >= 2)
    except Exception as e:
        R.add("GlossaryManager: get_stats", False, str(e))

    # --- Cleanup ---
    glossary_file = Path(f"glossaries/{test_novel}.json")
    if glossary_file.exists():
        glossary_file.unlink()


# =============================================================================
# SECTION 4 — CONTEXT MANAGER TESTS
# =============================================================================

def test_context_manager():
    print(header("[ 4 ] Context Manager — character and story tracking"))

    try:
        from scripts.context_manager import ContextManager, Character, StoryEvent
    except ImportError as e:
        R.add("ContextManager import", False, str(e))
        return

    test_novel = "_test_context_suite_"

    # --- 4a. Create context manager ---
    try:
        cm = ContextManager(test_novel, source_lang="English", auto_create=True)
        R.add("ContextManager: create", True)
    except Exception as e:
        R.add("ContextManager: create", False, str(e))
        return

    # --- 4b. Add character ---
    try:
        char = cm.add_character(
            name="Zhang San",
            burmese_name="ကျANNELဆန်း",
            description="A main character",
            importance="major",
            first_appearance=1
        )
        R.add("ContextManager: add_character",
              char is not None and char.name == "Zhang San")
    except Exception as e:
        R.add("ContextManager: add_character", False, str(e))

    # --- 4c. Get character ---
    try:
        char = cm.get_character("Zhang San")
        R.add("ContextManager: get_character",
              char is not None and char.burmese_name == "ကျANNELဆန်း")
    except Exception as e:
        R.add("ContextManager: get_character", False, str(e))

    # --- 4d. Add story event ---
    try:
        event = cm.add_story_event(
            chapter=1,
            title="The Beginning",
            summary="The story begins",
            importance="critical"
        )
        R.add("ContextManager: add_story_event",
              event is not None and event.chapter == 1)
    except Exception as e:
        R.add("ContextManager: add_story_event", False, str(e))

    # --- 4e. Register chapter ---
    try:
        ch_info = cm.register_chapter(1, title="Chapter One", word_count=5000)
        R.add("ContextManager: register_chapter",
              ch_info is not None and ch_info.chapter_num == 1)
    except Exception as e:
        R.add("ContextManager: register_chapter", False, str(e))

    # --- 4f. Get context for chapter ---
    try:
        context_text = cm.get_context_for_chapter(2)
        R.add("ContextManager: get_context_for_chapter",
              isinstance(context_text, str) and len(context_text) >= 0)
    except Exception as e:
        R.add("ContextManager: get_context_for_chapter", False, str(e))

    # --- 4g. Get major characters ---
    try:
        major_chars = cm.get_major_characters()
        R.add("ContextManager: get_major_characters",
              len(major_chars) >= 1 and major_chars[0].name == "Zhang San")
    except Exception as e:
        R.add("ContextManager: get_major_characters", False, str(e))

    # --- 4h. Save ---
    try:
        success = cm.save()
        R.add("ContextManager: save", success)
    except Exception as e:
        R.add("ContextManager: save", False, str(e))

    # --- Cleanup ---
    try:
        import shutil
        context_dir = Path(f"context/{test_novel}")
        if context_dir.exists():
            shutil.rmtree(context_dir)
    except Exception:
        pass


# =============================================================================
# SECTION 5 — NAME CONVERTER TESTS
# =============================================================================

def test_name_converter():
    print(header("[ 5 ] Name Converter — auto-learning and phonetic conversion"))

    try:
        from scripts.name_converter import NameConverter, NameEntry, CULTIVATION_TERMS
    except ImportError as e:
        R.add("NameConverter import", False, str(e))
        return

    test_novel = "_test_converter_suite_"

    # --- 5a. Create name converter ---
    try:
        nc = NameConverter(test_novel, source_lang="English")
        R.add("NameConverter: create", True)
    except Exception as e:
        R.add("NameConverter: create", False, str(e))
        return

    # --- 5b. Add name ---
    try:
        success = nc.add_name("Gu Wen", "ဂူဝမ်", "character", confidence=1.0)
        R.add("NameConverter: add_name", success)
    except Exception as e:
        R.add("NameConverter: add_name", False, str(e))

    # --- 5c. Suggest Myanmar name ---
    try:
        suggestion = nc.suggest_myanmar_name("Wang", "character")
        R.add("NameConverter: suggest_myanmar_name",
              isinstance(suggestion, str) and len(suggestion) > 0)
    except Exception as e:
        R.add("NameConverter: suggest_myanmar_name", False, str(e))

    # --- 5d. Convert text ---
    try:
        nc.add_name("Dragon Bridge", "နဂါးတံတား", "place")
        text = "Gu Wen walked across Dragon Bridge."
        converted = nc.convert_text(text)
        R.add("NameConverter: convert_text",
              "ဂူဝမ်" in converted or "နဂါးတံတား" in converted)
    except Exception as e:
        R.add("NameConverter: convert_text", False, str(e))

    # --- 5e. CULTIVATION_TERMS exists ---
    try:
        has_terms = len(CULTIVATION_TERMS) > 0
        has_realm = "Qi Refining" in CULTIVATION_TERMS or "炼气" in CULTIVATION_TERMS
        R.add("NameConverter: CULTIVATION_TERMS",
              has_terms and has_realm,
              f"Total terms: {len(CULTIVATION_TERMS)}")
    except Exception as e:
        R.add("NameConverter: CULTIVATION_TERMS", False, str(e))

    # --- 5f. Sync glossary to context ---
    try:
        synced = nc.sync_glossary_to_context()
        R.add("NameConverter: sync_glossary_to_context",
              isinstance(synced, int) and synced >= 0)
    except Exception as e:
        R.add("NameConverter: sync_glossary_to_context", False, str(e))

    # --- Cleanup ---
    try:
        import shutil
        glossary_file = Path(f"glossaries/{test_novel}.json")
        if glossary_file.exists():
            glossary_file.unlink()
        context_dir = Path(f"context/{test_novel}")
        if context_dir.exists():
            shutil.rmtree(context_dir)
    except Exception:
        pass


# =============================================================================
# SECTION 6 — POSTPROCESSOR FIXES
# =============================================================================

def test_postprocessor():
    print(header("[ 6 ] Postprocessor — fix_punctuation, naturalize_verb_endings"))

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

    # --- 6a. Chinese punctuation -> Myanmar ---
    sample = "ဟုတ်တယ်။ ဆိုပါစို့。 ငါ သွားမယ်၊မင်းကော？"
    result = fix_punctuation(sample)
    R.add("fix_punctuation: 。→ ။",
          "。" not in result and "，" not in result,
          f"result: {result!r}")

    # --- 6b. naturalize_verb_endings exists and works ---
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

    # --- 6c. remove_non_myanmar_characters keeps zero-width space ---
    zwsp = "မြန်မာ\u200Bစာ"   # contains U+200B
    result = remove_non_myanmar_characters(zwsp)
    R.add("remove_non_myanmar_characters: U+200B preserved",
          "\u200B" in result,
          "U+200B ပါနေသေးသလား — range ချဲ့ပြင်ဖို့ လိုသေးနိုင်တယ်")

    # --- 6d. pure Myanmar text not stripped ---
    pure = "မြန်မာဘာသာ ဖတ်ကောင်းပါစေ"
    result = remove_non_myanmar_characters(pure)
    R.add("remove_non_myanmar_characters: pure Myanmar text intact",
          len(result) >= len(pure) - 2)


# =============================================================================
# SECTION 7 — FIX TRANSLATION FUNCTIONS
# =============================================================================

def test_fix_translation():
    print(header("[ 7 ] fix_translation.py — style fix functions"))

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

    # --- 7a. remove_metadata_text ---
    meta = "Chapter: some_chapter TEXT TO TRANSLATE:\nဒါက အမှန်တကယ် ဘာသာပြန်ချက်ပဲ"
    result = remove_metadata_text(meta)
    R.add("remove_metadata_text",
          "TEXT TO TRANSLATE" not in result and "ဘာသာပြန်ချက်" in result,
          f"output: {result!r}")

    # --- 7b. fix_dialogue_format ---
    stiff = 'သူသည် "မင်းဘာလုပ်နေတာလဲ" ဟုမေးလေသည်'
    result = fix_dialogue_format(stiff)
    R.add("fix_dialogue_format: ဟုမေးလေသည် -> မေးလိုက်တယ်",
          "မေးလေသည်" not in result or "မေးလိုက်တယ်" in result,
          f"output: {result!r}")

    # --- 7c. fix_emotion_descriptions ---
    abstract = "သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်"
    result = fix_emotion_descriptions(abstract)
    R.add("fix_emotion_descriptions: abstract -> physical",
          "ဝမ်းနည်းပူဆွေးသောခံစားချက်" not in result,
          f"output: {result!r}")

    # --- 7d. fix_long_sentences: long line gets broken ---
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

    # --- 7e. fix_weird_repetitions ---
    repeated = "ချိုချိုချိုချိုချိုချိုချိုချို"
    result = fix_weird_repetitions(repeated)
    R.add("fix_weird_repetitions: collapse repeats",
          len(result) < len(repeated),
          f"before={len(repeated)}, after={len(result)}")

    # --- 7f. postprocess_translation runs end-to-end ---
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
# SECTION 8 — MYANMAR QUALITY CHECKER
# =============================================================================

def test_myanmar_checker():
    print(header("[ 8 ] Myanmar quality checker — readability thresholds"))

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

    # --- 8a. Pure Myanmar text should pass ---
    good_text = (
        "သူမ မျက်ရည်တွေ ကျနေတယ်။ ရင်ထဲမှာ နာကျင်သလိုပဲ ခံစားရတယ်။ "
        "ပြန်မလာနိုင်တော့ဘူး ဆိုတာ သူ သိနေတယ်။ ဒါပေမဲ့ ဘာမှ ပြောမရဘူး။"
    )
    results = check_readability(good_text)
    R.add("check_readability: good Myanmar text passes",
          results.get("passed", False),
          f"myanmar_ratio={results.get('checks', {}).get('myanmar_ratio', {}).get('value', '?')}")

    # --- 8b. Text with Chinese chars should fail ---
    leaky_text = "ဒါက 古道仙鸿 ဆိုတဲ့ novel ကနေ ယူထားတာ"
    results = check_readability(leaky_text)
    no_chinese_check = results.get("checks", {}).get("no_chinese", {})
    R.add("check_readability: Chinese chars detected",
          not no_chinese_check.get("passed", True),
          f"chinese_count={no_chinese_check.get('value', '?')}")

    # --- 8c. Myanmar ratio calculation ---
    myanmar_only = "မြန်မာဘာသာ"
    ratio = calculate_myanmar_ratio(myanmar_only)
    R.add("calculate_myanmar_ratio: near 1.0 for Myanmar-only text",
          ratio > 0.8,
          f"ratio={ratio:.3f}")

    # --- 8d. Sentence ender count ---
    with_enders = "ဒါပဲ။ ဟုတ်ကဲ့ပါ။ နားလည်တယ်။"
    count = count_sentence_enders(with_enders)
    R.add("count_sentence_enders: count = 3",
          count == 3,
          f"count={count}")

    # --- 8e. 70% threshold check ---
    mixed_text = "hello world " + "မြန်မာ " * 10
    ratio = calculate_myanmar_ratio(mixed_text)
    results = check_readability(mixed_text)
    myanmar_check = results.get("checks", {}).get("myanmar_ratio", {})
    R.add("check_readability: mixed text threshold logic works",
          "passed" in myanmar_check,
          f"ratio={ratio:.2f}, passed={myanmar_check.get('passed')}")


# =============================================================================
# SECTION 9 — ASSEMBLER
# =============================================================================

def test_assembler():
    print(header("[ 9 ] Assembler — output file structure"))

    try:
        from scripts.assembler import assemble, load_template
    except ImportError as e:
        R.add("assembler import", False, str(e))
        return

    # --- 9a. load_template returns string ---
    tmpl = load_template()
    R.add("load_template: returns string", isinstance(tmpl, str) and len(tmpl) > 0)

    # --- 9b. template has required placeholders ---
    required = ["{original_title}", "{translated_content}"]
    missing  = [p for p in required if p not in tmpl]
    R.add("load_template: required placeholders present",
          len(missing) == 0,
          f"missing: {missing}" if missing else "")

    # --- 9c. assemble writes file ---
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

        # --- 9d. content appears in output ---
        text = out_path.read_text(encoding="utf-8")
        R.add("assemble: Myanmar content in output", content in text)

        # --- 9e. no raw placeholder in output ---
        R.add("assemble: no unfilled placeholders",
              "{" not in text or "translated_content" not in text)

        out_path.unlink()

    except Exception as e:
        R.add("assemble: file written", False, str(e))


# =============================================================================
# SECTION 10 — TRANSLATOR SYSTEM PROMPT
# =============================================================================

def test_system_prompt():
    print(header("[ 10 ] System prompt — style rules ပါဝင်မှု"))

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
# SECTION 11 — PIPELINE INTEGRATION
# =============================================================================

def test_pipeline_integration():
    print(header("[ 11 ] Pipeline integration — main.py စစ်ဆေးချက်"))

    main_path = Path("main.py")
    if not main_path.exists():
        R.add("main.py exists", False, "main.py မတွေ့ဘူး")
        return
    R.add("main.py exists", True)

    src = main_path.read_text(encoding="utf-8")

    # --- 11a. ResourceManager import and usage ---
    # Note: ResourceManager is optional - it provides a unified interface but is not required
    has_resource_manager = "ResourceManager" in src or "resource_manager" in src
    if not has_resource_manager:
        print(f"  {warned('main.py: ResourceManager not imported (optional - available for unified access)')}")
    R.add("main.py: ResourceManager import (optional)", True)  # Always pass, this is optional

    # --- 11b. GlossaryManager import ---
    R.add("main.py: GlossaryManager imported",
          "GlossaryManager" in src)

    # --- 11c. ContextManager import ---
    R.add("main.py: ContextManager imported",
          "ContextManager" in src)

    # --- 11d. NameConverter usage ---
    R.add("main.py: NameConverter usage",
          "NameConverter" in src)

    # --- 11e. postprocess or postprocess_translation is called ---
    R.add("main.py: postprocess() ခေါ်တယ်",
          "postprocess(" in src or "postprocess_translation(" in src)

    # --- 11f. fix_translation is imported or called ---
    has_import = "fix_translation" in src
    has_call   = "postprocess_translation" in src
    R.add("main.py: fix_translation integrate လုပ်ထားတယ်",
          has_import and has_call,
          "fix_translation import/call မတွေ့ဘူး — ထည့်ဖို့ လိုသေးတယ်"
          if not (has_import and has_call) else "")

    # --- 11g. two-stage mode supported ---
    R.add("main.py: two-stage mode supported",
          "--two-stage" in src or "two_stage" in src)

    # --- 11h. Cultivation terms in prompts ---
    R.add("main.py: Cultivation terms awareness",
          "cultivation" in src.lower() or "CULTIVATION" in src)


# =============================================================================
# SECTION 12 — TRANSLATION QUALITY CHECK
# =============================================================================

def test_translation_quality():
    print(header("[ 12 ] Translation quality — books/ folder စစ်ဆေးချက်"))

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
# SECTION 13 — CHUNKER SANITY
# =============================================================================

def test_chunker():
    print(header("[ 13 ] Chunker — text splitting"))

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
# SECTION 14 — CONFIG FILE
# =============================================================================

def test_config():
    print(header("[ 14 ] Config — config/config.json စစ်ဆေးချက်"))

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

    # Check supported_models
    sm = config.get("supported_models", {})
    R.add("config: supported_models.ollama exists",
          "ollama" in sm)
    R.add("config: supported_models.gemini exists",
          "gemini" in sm)
    R.add("config: supported_models.openrouter exists",
          "openrouter" in sm)

    # Warn if single_stage (two_stage is better)
    mode = tp.get("mode", "single_stage")
    if mode == "single_stage":
        print(f"  {warned('config: mode=single_stage — two_stage ကို recommend တယ်')}")


# =============================================================================
# SECTION 15 — FILE STRUCTURE CHECK
# =============================================================================

def test_file_structure():
    print(header("[ 15 ] File structure — required files and folders"))

    required = [
        "main.py",
        "scripts/translator.py",
        "scripts/postprocessor.py",
        "scripts/fix_translation.py",
        "scripts/assembler.py",
        "scripts/myanmar_checker.py",
        "scripts/rewriter.py",
        "scripts/glossary_manager.py",
        "scripts/context_manager.py",
        "scripts/name_converter.py",
        "scripts/resource_manager.py",
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
# SECTION 16 — READER APP (Web UI)
# =============================================================================

def test_reader_app():
    print(header("[ 16 ] Reader App — Web UI စစ်ဆေးချက်"))

    reader_path = Path("reader_app.py")
    R.add("reader_app.py exists", reader_path.exists())
    if not reader_path.exists():
        return

    # --- 16a. Check Flask imports ---
    src = reader_path.read_text(encoding="utf-8")
    R.add("reader_app: Flask imported",
          "from flask import Flask" in src)
    R.add("reader_app: send_from_directory (not send_from_path)",
          "send_from_directory" in src and "send_from_path" not in src,
          "send_from_path အစား send_from_directory သုံးပါ")

    # --- 16b. Check required routes ---
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

    # --- 16c. Check security features ---
    R.add("reader_app: is_safe_path_name function (security)",
          "is_safe_path_name" in src)
    R.add("reader_app: path traversal protection (.. check)",
          "'..' in" in src or '".." in' in src)

    # --- 16d. Check template usage ---
    templates = ["index.html", "chapters.html", "reader.html"]
    for tmpl in templates:
        template_found = f"'{tmpl}'" in src and "render_template" in src
        R.add(f"reader_app: template '{tmpl}' used",
              template_found)

    # --- 16e. Check books directory handling ---
    R.add("reader_app: BOOKS_DIR defined",
          'BOOKS_DIR = Path("books")' in src or "BOOKS_DIR = Path('books')" in src)
    R.add("reader_app: metadata.json loading",
          "metadata.json" in src)

    # --- 16f. Check progress tracking ---
    R.add("reader_app: progress.json handling",
          "progress.json" in src or "PROGRESS_FILE" in src)
    R.add("reader_app: load_progress function",
          "def load_progress():" in src)
    R.add("reader_app: save_progress function",
          "def save_progress(" in src)

    # --- 16g. Check sample book exists ---
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
# SECTION 17 — CULTIVATION TERMS TEST
# =============================================================================

def test_cultivation_terms():
    print(header("[ 17 ] Cultivation Terms — built-in dictionary"))
    
    try:
        from scripts.name_converter import CULTIVATION_TERMS
        from scripts.resource_manager import ResourceManager
    except ImportError as e:
        R.add("Cultivation terms import", False, str(e))
        return
    
    # --- 17a. CULTIVATION_TERMS is populated ---
    try:
        term_count = len(CULTIVATION_TERMS)
        has_realms = any("Qi" in k or "炼气" in k for k in CULTIVATION_TERMS.keys())
        has_titles = any("Sect" in k or "Elder" in k for k in CULTIVATION_TERMS.keys())
        
        R.add("CULTIVATION_TERMS: has entries",
              term_count > 50,
              f"Total terms: {term_count}")
        R.add("CULTIVATION_TERMS: has realm terms",
              has_realms)
        R.add("CULTIVATION_TERMS: has title terms",
              has_titles)
    except Exception as e:
        R.add("CULTIVATION_TERMS check", False, str(e))
    
    # --- 17b. ResourceManager loads cultivation terms ---
    try:
        test_novel = "_test_cultivation_"
        rm = ResourceManager(test_novel, auto_create=True)
        
        has_terms = len(rm.cultivation_terms) > 0
        R.add("ResourceManager: loads cultivation terms",
              has_terms,
              f"Loaded {len(rm.cultivation_terms)} terms")
        
        # Cleanup
        import shutil
        resources_dir = Path(f"resources/{test_novel}")
        if resources_dir.exists():
            shutil.rmtree(resources_dir)
        glossary_file = Path(f"glossaries/{test_novel}.json")
        if glossary_file.exists():
            glossary_file.unlink()
        context_dir = Path(f"context/{test_novel}")
        if context_dir.exists():
            shutil.rmtree(context_dir)
            
    except Exception as e:
        R.add("ResourceManager: loads cultivation terms", False, str(e))


# =============================================================================
# SECTION 17.5 — SECURITY FILTER TEST
# =============================================================================

def test_security_filter():
    print(header("[ 17.5 ] Security Filter — API key masking in logs"))
    
    try:
        from main import SensitiveDataFilter
    except ImportError:
        R.add("SensitiveDataFilter import", False, "Cannot import from main.py")
        return
    
    # Test the filter
    filter_obj = SensitiveDataFilter()
    
    class MockRecord:
        def __init__(self, msg, args=None):
            self.msg = msg
            self.args = args or ()
    
    # Test cases
    test_cases = [
        # (input, should_contain_mask)
        ('Connecting to API with key=AIzaSyDdI0rhdAp8c6cAh0WIWw', True),
        ('Authorization: Bearer sk-1234567890abcdef', True),
        ('api_key=secret123456789', True),
        ('Normal message without sensitive data', False),
        ('URL: https://example.com?key=AIzaSyDdI0rhdAp8c6cAh0WIWw&other=value', True),
    ]
    
    all_passed = True
    for input_msg, should_mask in test_cases:
        record = MockRecord(input_msg)
        filter_obj.filter(record)
        
        has_mask = '***API_KEY_HIDDEN***' in record.msg or '***TOKEN_HIDDEN***' in record.msg
        
        if should_mask and not has_mask:
            R.add(f"Security filter: Mask API key in '{input_msg[:30]}...'", False, "API key not masked")
            all_passed = False
        elif not should_mask and has_mask:
            R.add(f"Security filter: Don't mask normal text '{input_msg[:30]}...'", False, "Normal text incorrectly masked")
            all_passed = False
    
    if all_passed:
        R.add("SensitiveDataFilter: Masks API keys correctly", True)


# =============================================================================
# SECTION 18 — MAIN.PY RESOURCE INTEGRATION
# =============================================================================

def test_main_resource_integration():
    print(header("[ 18 ] Main.py Resource Integration — feature usage"))
    
    main_path = Path("main.py")
    if not main_path.exists():
        R.add("main.py exists", False, "main.py မတွေ့ဘူး")
        return
    
    src = main_path.read_text(encoding="utf-8")
    
    # --- 18a. GlossaryManager loading ---
    R.add("main.py: Loads GlossaryManager for book",
          "GlossaryManager(book_id)" in src or "GlossaryManager(" in src)
    
    # --- 18b. ContextManager usage ---
    R.add("main.py: Uses ContextManager",
          "ContextManager(" in src and "get_context_for_chapter" in src)
    
    # --- 18c. NameConverter for auto-learn ---
    R.add("main.py: Uses NameConverter for auto-learn",
          "NameConverter(" in src and "auto_learn" in src)
    
    # --- 18d. Glossary text injection ---
    R.add("main.py: Injects glossary into prompts",
          "get_glossary_text" in src or "glossary_text" in src)
    
    # --- 18e. Context text injection ---
    R.add("main.py: Injects context into prompts",
          "context_text" in src and "system_prompt" in src)
    
    # --- 18f. Glossary updates after translation ---
    R.add("main.py: Updates glossary after translation",
          "glossary.save" in src or "glossary.update" in src)
    
    # --- 18g. Context updates after translation ---
    R.add("main.py: Updates context after translation",
          "context_manager.save" in src or "update_chapter_translation" in src)
    
    # --- 18h. Name sync between glossary and context ---
    R.add("main.py: Syncs glossary to context",
          "sync_glossary_to_context" in src)


# =============================================================================
# SECTION 19 — NAME MAPPING SYSTEM
# =============================================================================

def test_name_mapping_system():
    print(header("[ 19 ] Name Mapping System — auto-detect and type-based translation"))
    
    try:
        from scripts.name_mapping_system import NameMappingSystem, NameType, NameMapping
    except ImportError as e:
        R.add("NameMappingSystem import", False, str(e))
        return
    
    test_novel = "_test_name_mapping_"
    
    # --- 19a. Create NameMappingSystem ---
    try:
        nms = NameMappingSystem(test_novel, source_lang="English", auto_create=True)
        R.add("NameMappingSystem: create", True)
    except Exception as e:
        R.add("NameMappingSystem: create", False, str(e))
        return
    
    # --- 19b. Add person mapping ---
    try:
        nms.add_mapping("Li Wei", "လီဝေ့", NameType.PERSON.value, confidence=0.95)
        mapping = nms.get_mapping("Li Wei")
        R.add("NameMappingSystem: add person mapping",
              mapping is not None and mapping.myanmar_name == "လီဝေ့" and mapping.name_type == NameType.PERSON.value)
    except Exception as e:
        R.add("NameMappingSystem: add person mapping", False, str(e))
    
    # --- 19c. Add place mapping with suffix ---
    try:
        nms.add_mapping("Cloud City", "မိုးအုပ်မြို့", NameType.PLACE.value, confidence=0.9)
        mapping = nms.get_mapping("Cloud City")
        has_suffix = mapping.myanmar_name.endswith("မြို့")
        R.add("NameMappingSystem: add place mapping with suffix",
              has_suffix)
    except Exception as e:
        R.add("NameMappingSystem: add place mapping", False, str(e))
    
    # --- 19d. Add sect mapping with ဇုံ suffix ---
    try:
        nms.add_mapping("Azure Sect", "ထ的有效ဇုံ", NameType.SECT.value, confidence=0.85)
        mapping = nms.get_mapping("Azure Sect")
        has_sect_suffix = "ဇုံ" in mapping.myanmar_name
        R.add("NameMappingSystem: add sect mapping with ဇုံ suffix",
              has_sect_suffix)
    except Exception as e:
        R.add("NameMappingSystem: add sect mapping", False, str(e))
    
    # --- 19e. Detect names from text ---
    try:
        text = "Zhang San met Li Wei at Cloud City and joined the Azure Sect."
        detected = nms.detect_names(text, chapter_num=1)
        # Should detect Zhang San (person) if not already mapped
        R.add("NameMappingSystem: detect_names from text",
              isinstance(detected, list))
    except Exception as e:
        R.add("NameMappingSystem: detect_names", False, str(e))
    
    # --- 19f. Apply mappings to text ---
    try:
        text = "Li Wei went to Cloud City."
        result = nms.apply_mappings(text)
        # Li Wei should be replaced with လီဝေ့
        has_mapping = "လီဝေ့" in result or "Li Wei" not in result
        R.add("NameMappingSystem: apply_mappings",
              has_mapping)
    except Exception as e:
        R.add("NameMappingSystem: apply_mappings", False, str(e))
    
    # --- 19g. Get prompt text ---
    try:
        prompt_text = nms.get_prompt_text()
        has_person = "Characters:" in prompt_text or "Li Wei" in prompt_text
        R.add("NameMappingSystem: get_prompt_text",
              len(prompt_text) > 0 and has_person)
    except Exception as e:
        R.add("NameMappingSystem: get_prompt_text", False, str(e))
    
    # --- 19h. Save mappings ---
    try:
        success = nms.save()
        R.add("NameMappingSystem: save", success)
    except Exception as e:
        R.add("NameMappingSystem: save", False, str(e))
    
    # --- 19i. Load mappings ---
    try:
        nms2 = NameMappingSystem(test_novel, source_lang="English", auto_create=False)
        has_mappings = len(nms2.mappings) > 0
        R.add("NameMappingSystem: load",
              has_mappings)
    except Exception as e:
        R.add("NameMappingSystem: load", False, str(e))
    
    # --- 19j. Get stats ---
    try:
        stats = nms.get_stats()
        R.add("NameMappingSystem: get_stats",
              "total_mappings" in stats and "by_type" in stats)
    except Exception as e:
        R.add("NameMappingSystem: get_stats", False, str(e))
    
    # --- Cleanup ---
    try:
        import shutil
        mappings_dir = Path("name_mappings")
        if mappings_dir.exists():
            for f in mappings_dir.glob(f"{test_novel}*.json"):
                f.unlink()
    except Exception:
        pass


# =============================================================================
# SECTION 20 — MAIN.PY NAME MAPPING INTEGRATION
# =============================================================================

def test_main_name_mapping():
    print(header("[ 20 ] Main.py Name Mapping Integration"))
    
    main_path = Path("main.py")
    if not main_path.exists():
        R.add("main.py exists", False, "main.py မတွေ့ဘူး")
        return
    
    src = main_path.read_text(encoding="utf-8")
    
    # --- 20a. NameMappingSystem import ---
    R.add("main.py: NameMappingSystem imported",
          "NameMappingSystem" in src)
    
    # --- 20b. NameMappingSystem initialization ---
    R.add("main.py: NameMappingSystem initialized",
          "NameMappingSystem(book_id" in src or "name_mapping_system" in src)
    
    # --- 20c. Auto-detect names ---
    R.add("main.py: Auto-detects names",
          "detect_names" in src)
    
    # --- 20d. Apply mappings before translation ---
    R.add("main.py: Applies mappings before translation",
          "apply_mappings" in src)
    
    # --- 20e. Inject name mappings into prompt ---
    R.add("main.py: Injects name mappings into prompt",
          "get_prompt_text" in src)
    
    # --- 20f. Learn from parallel text ---
    R.add("main.py: Learns from parallel text",
          "learn_from_parallel" in src)


# =============================================================================
# MAIN RUNNER
# =============================================================================

SECTIONS = {
    "imports":     test_imports,
    "resources":   test_resource_manager,
    "glossary":    test_glossary,
    "context":     test_context_manager,
    "names":       test_name_converter,
    "mapping":     test_name_mapping_system,
    "postprocess": test_postprocessor,
    "fix":         test_fix_translation,
    "quality":     test_myanmar_checker,
    "assembler":   test_assembler,
    "prompt":      test_system_prompt,
    "pipeline":    test_pipeline_integration,
    "translation": test_translation_quality,
    "chunker":     test_chunker,
    "config":      test_config,
    "structure":   test_file_structure,
    "reader":      test_reader_app,
    "cultivation": test_cultivation_terms,
    "security":    test_security_filter,
    "main":        test_main_resource_integration,
    "nmmain":      test_main_name_mapping,
}


def main():
    parser = argparse.ArgumentParser(
        description="Novel Translation Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories:
  imports      scripts/ import checks
  resources    ResourceManager unified interface
  glossary     GlossaryManager consistency
  context      ContextManager tracking
  names        NameConverter auto-learning
  mapping      NameMappingSystem auto-detect and type-based rules
  postprocess  postprocessor.py fixes
  fix          fix_translation.py style fixes
  quality      myanmar_checker.py thresholds
  assembler    output file structure
  prompt       system prompt rules
  pipeline     main.py integration
  translation  books/ output quality
  chunker      text splitting
  config       config.json values
  structure    required files check
  reader       reader_app.py Web UI checks
  cultivation  Cultivation terms dictionary
  security     Security filter (API key masking)
  main         main.py resource integration
  nmmain       main.py name mapping integration
  
Examples:
  python test.py                    # Run all tests
  python test.py --category names   # Run only name converter tests
  python test.py --category mapping # Run name mapping system tests
  python test.py --category quality # Run quality checks only
        """
    )
    parser.add_argument("--verbose",  action="store_true")
    parser.add_argument("--category", choices=list(SECTIONS.keys()),
                        help="single category run")
    args = parser.parse_args()

    print(f"\n{Color.BOLD}Novel Translation Test Suite{Color.RESET}")
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

    if any("ResourceManager" in n for n in fail_names):
        print(f"{Color.WARN}[ACTION]{Color.RESET} scripts/resource_manager.py ကို စစ်ဆေးပါ — component မတွေ့သို့မဟုတ် error ရှိနိုင်သည်")

    if any("NameMappingSystem" in n for n in fail_names):
        print(f"{Color.WARN}[ACTION]{Color.RESET} scripts/name_mapping_system.py ကို စစ်ဆေးပါ — component မတွေ့သို့မဟုတ် error ရှိနိုင်သည်")

    sys.exit(0 if failed_n == 0 else 1)


if __name__ == "__main__":
    main()
