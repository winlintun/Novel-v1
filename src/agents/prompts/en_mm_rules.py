"""
English-to-Myanmar Linguistic Transformation Rules
Novel-v1 Project — en_mm_rules.py

Based on:
  - cn_mm_rules.py structure (Novel-v1)
  - saturngod/prompt.md reference gist
  - English→Myanmar specific linguistic patterns
  - Cultivation/Xianxia/Wuxia novel conventions

Covers:
  - SVO (English) → SOV (Myanmar) structural conversion
  - Tense adaptation (English tense → Myanmar particle)
  - Pronoun resolution by character status/relationship
  - Dialogue naturalness rules
  - Literary narration vs casual narration
  - Unicode safety rules
  - Cultural adaptation
"""



# ===========================================================================
# SECTION 1: STRUCTURAL CONVERSION
# SVO (English) → SOV (Myanmar)
# ===========================================================================

SVO_TO_SOV_RULES = {
    "basic_structure": (
        "English: Subject + Verb + Object\n"
        "Myanmar: Subject + Object + Verb\n"
        "Example:\n"
        "  EN: He [S] struck [V] the enemy [O]\n"
        "  MM: သူ [S] ရန်သူကို [O] ထိုးလိုက်တယ် [V]"
    ),

    "time_adverbials": (
        "Time expressions move to SENTENCE START in Myanmar\n"
        "Example:\n"
        "  EN: He arrived yesterday\n"
        "  MM: မနေ့က သူ ရောက်လာတယ်  (yesterday → front)"
    ),

    "location_adverbials": (
        "Location phrases move to BEFORE the verb in Myanmar\n"
        "Example:\n"
        "  EN: He fought in the valley\n"
        "  MM: သူ ချိုင့်ဝှမ်းထဲမှာ တိုက်ခဲ့တယ်"
    ),

    "adjective_position": (
        "English: adjective BEFORE noun (the tall man)\n"
        "Myanmar: adjective AFTER noun with သော/တဲ့\n"
        "Example:\n"
        "  EN: the tall man\n"
        "  MM: အရပ်မြင့်တဲ့ လူ  OR  လူကြီး (natural adaptation)"
    ),

    "relative_clauses": (
        "English relative clauses (who/which/that) → Myanmar သော/တဲ့ before noun\n"
        "Example:\n"
        "  EN: The man who saved him\n"
        "  MM: သူ့ကို ကယ်တင်တဲ့ လူ"
    ),

    "negation": (
        "Myanmar negation မ precedes verb, ဘူး ends sentence\n"
        "Example:\n"
        "  EN: He did not speak\n"
        "  MM: သူ မပြောဘူး  (not: သူ ပြောမဘူး)"
    ),

    "passive_voice": (
        "English passive → Myanmar active preferred\n"
        "Example:\n"
        "  EN: He was struck by the sword\n"
        "  MM: သူ ဓားနဲ့ထိုးခံရပြီး  (agent becomes subject)\n"
        "  OR: သူက ဓားနဲ့ထိုးခံလိုက်ရတာပါ။  (if passive emphasis needed)"
    ),
}


# ===========================================================================
# SECTION 2: TENSE ADAPTATION
# English has grammatical tense; Myanmar uses particles + context
# ===========================================================================

TENSE_TO_PARTICLE = {
    "simple_past": {
        "english": "He walked",
        "myanmar_literary": "သူ လျှောက်သွားခဲ့သည်",
        "myanmar_casual": "သူ လျှောက်သွားခဲ့တယ်",
        "rule": "ခဲ့ particle marks completed past action",
    },

    "simple_present": {
        "english": "He walks",
        "myanmar_literary": "သူလမ်းလျှောက်သည်",
        "myanmar_casual": "သူလမ်းလျှောက်တယ်",
        "rule": "သည်/တယ် = present or habitual action",
    },

    "present_continuous": {
        "english": "He is walking",
        "myanmar": "သူလမ်းလျှောက်နေတယ်",
        "rule": "နေ particle marks ongoing action",
    },

    "past_continuous": {
        "english": "He was walking",
        "myanmar": "သူ လမ်းလျှောက်နေခဲ့တယ်။",
        "rule": "နေ + ခဲ့ = was doing",
    },

    "perfect": {
        "english": "He has arrived",
        "myanmar": "သူ ရောက်လာပြီ  OR  သူ ရောက်နေပြီ",
        "rule": "ပြီ marks completion/relevance to now",
    },

    "future": {
        "english": "He will fight",
        "myanmar": "သူ တိုက်မယ်",
        "rule": "မယ် = intention/future",
    },

    "anger_vivid_past": {
        "rule": (
            "SPECIAL RULE for dialogue expressing anger or accusation:\n"
            "Drop ခဲ့ to create vivid present-tense intensity\n"
            "Example:\n"
            "  Standard: နင် ငါ့ကို ထိုးခဲ့တယ် (You struck me — neutral recall)\n"
            "  Vivid:    နင် ငါ့ကို ထိုးတယ်    (You struck me — burning memory)\n"
            "Use vivid form in: accusation speeches, emotional confrontations"
        ),
    },
}


# ===========================================================================
# SECTION 3: PRONOUN RESOLUTION
# Based on character status, relationship, and emotional context
# ===========================================================================

PRONOUN_HIERARCHY = {
    "first_person": {
        "male_formal":    "ကျွန်တော်",
        "female_formal":  "ကျွန်မ",
        "male_casual":    "ငါ",
        "female_casual":  "ငါ / ကိုယ်",
        "humble":         "ကျွန်ုပ်",
        "arrogant":       "ငါ (flat, no softening)",
    },

    "second_person": {
        "to_enemy":            "နင် (contemptuous, enemy)",
        "to_inferior_casual":  "မင်း",
        "to_equal":            "မင်း / ခင်ဗျ (male) / ရှင် (female)",
        "to_superior":         "ခင်ဗျ / ရှင်",
        "to_master_teacher":   "ဆရာ / ဆရာကြီး",
        "rule": (
            "CRITICAL: Enemy dialogue = နင် (not မင်း)\n"
            "မင်း = neutral/equal\n"
            "နင် = contempt, anger, dominance\n"
            "Example:\n"
            "  Neutral:  မင်း ဒါ ဘာကြောင့် လုပ်တာလဲ\n"
            "  Hostile:  နင် ဒါ ဘာကြောင့် လုပ်တာလဲ"
        ),
    },

    "third_person": {
        "male":          "သူ",
        "female":        "သူမ",
        "plural":        "သူတို့",
        "respectful":    "သူတော် / ထိုပုဂ္ဂိုလ်",
        "contemptuous":  "ဒီကောင် / အဲဒီကောင် / ထိုသူ",
        "rule": (
            "Use သူ for male characters unless context requires otherwise\n"
            "Use ဒီကောင် when speaker is contemptuous of third party\n"
            "Use ထိုပုဂ္ဂိုလ် for very formal/respected figures"
        ),
    },
}


# ===========================================================================
# SECTION 4: DIALOGUE RULES
# ===========================================================================

DIALOGUE_RULES = {
    "dialogue_tag_format": {
        "rule": "MANDATORY FORMAT for all dialogue tags",
        "correct": [
            '"စကားပြောကြောင်း" လို့ [character] [verb]တယ်',
            '"မင်း ဒါ မသိဘူးလား" လို့ သူ မေးလိုက်တယ်',
            '"ရပ်!" လို့ ဆရာကြီး အော်လိုက်တယ်',
            '"ငါ မသိဘူး" လို့ သူမ တိုးတိုး ပြောတယ်',
        ],
        "wrong": [
            '"..." ဟု သူ မေးမြန်းလေသည်',
            '"..." ဟု ဆိုလေသည်',
            '"..." ဟု ပြောဆိုလေသည်',
        ],
        "note": "ဟု...လေသည် pattern is archaic — NEVER USE in novel translation",
    },

    "speech_verb_variety": {
        "neutral":        "ပြောတယ် / ပြောလိုက်တယ်",
        "asked":          "မေးတယ် / မေးလိုက်တယ်",
        "whispered":      "တိုးတိုး ပြောတယ် / တိုးတိုးလေး ဆိုတယ်",
        "shouted":        "အော်လိုက်တယ် / ကြွေးကြော်လိုက်တယ်",
        "laughed_said":   "ရယ်ရင်း ပြောတယ် / ပြုံးရင်း ဆိုတယ်",
        "coldly_said":    "အေးစက်စက်နဲ့ ပြောတယ်",
        "sneered":        "ကြိတ်ပြောတယ် / မာနတင်းတင်းနဲ့ ဆိုတယ်",
        "replied":        "ပြန်ပြောတယ် / တုံ့ပြန်တယ်",
        "muttered":       "တဆိတ်ဆိတ် ပြောတယ် / မျှာမြောက် ဆိုတယ်",
        "commanded":      "အမိန့်ပေးလိုက်တယ် / ညွှန်ကြားလိုက်တယ်",
    },

    "internal_monologue": {
        "format_1": "(ဒါ မဖြစ်နိုင်ဘူး) လို့ ထင်မိတယ်",
        "format_2": "*ဒါမျိုး ဘယ်ဖြစ်မလဲ* (italic in markdown)",
        "format_3": "သူ စိတ်ထဲမှာ တွေးနေမိတယ် — ဒါ မဟုတ်ဘူးဆိုတာ",
        "rule": "Internal thought ≠ spoken dialogue. Style different from speech.",
    },

    "sentence_rhythm_by_scene": {
        "action_combat": (
            "SHORT sentences. 3-6 words each.\n"
            "Example:\n"
            "  သူ တိုးဝင်လာတယ်။ ဓားကို ကာရင်း။ "
            "ချက်ချင်း ပြန်ထိုးလိုက်တယ်။"
        ),
        "tense_confrontation": (
            "SHORT, PUNCHY. One accusation per sentence.\n"
            "Example:\n"
            "  နင် ငါ့ကို နာကျင်စေခဲ့တယ်။ ငါ့ မိသားစုကို သတ်တယ်။ "
            "ဒီနေ့ နင် လက်စားချေရမယ်။"
        ),
        "calm_narration": (
            "MEDIUM sentences. 10-18 words okay.\n"
            "Flowing but not compound-heavy."
        ),
        "romantic_scene": (
            "Slightly longer, poetic.\n"
            "Use sensory details over direct emotional labels."
        ),
    },
}


# ===========================================================================
# SECTION 5: NARRATION STYLE RULES
# ===========================================================================

NARRATION_RULES = {
    "literary_narration": {
        "particle": "သည် / ၏ / သော",
        "use_when": "Third person narration, scene description, action sequences",
        "example": (
            "EN: His robes waved in the mountain breeze like a war flag.\n"
            "MM: သူ့ဝတ်ရုံသည် တောင်လေပြေထဲတွင် စစ်အလံတစ်ခု ထောင်ထားသလို တစ်လူလူ လွင့်နေသည်။"
        ),
    },

    "casual_narration": {
        "particle": "တယ် / တာ / နေတယ်",
        "use_when": "Close POV, character's immediate perception, light scenes",
        "example": (
            "EN: He looked around.\n"
            "MM: သူ ပတ်ဝန်းကျင်ကို ကြည့်လိုက်တယ်။"
        ),
    },

    "register_matching": {
        "rule": (
            "Match narration register to scene intensity:\n"
            "High drama / battle / death     → သည် literary\n"
            "POV character perception        → တယ် casual\n"
            "Epic description                → သည် literary\n"
            "Humor / light moment            → တယ် casual"
        ),
    },

    "emotion_show_not_tell": {
        "rule": "Show emotions through physical sensation — NEVER abstract labels alone",
        "wrong": [
            "သူ ဝမ်းနည်းသောခံစားချက်ကို ခံစားနေသည်  (abstract)",
            "သူ အလွန် ဒေါသဖြစ်သည်  (label only)",
        ],
        "correct": [
            "သူ့နှလုံးသားဟာ တစ်စစီ ကျိုးပဲ့ပျက်စီးသွားသလို ခံစားလိုက်ရတယ်  (sadness)",
            "သူ့မေးရိုးတွေ တင်းခနဲဖြစ်သွားပြီး သွားတွေကို တင်းတင်းကြိတ်ထားမိတယ်  (anger)",
            "သူ့ကျောရိုးတစ်လျှောက် စိမ့်ခနဲ အေးစက်သွားပြီး ကြက်သီးမွေးညင်းတွေ ထသွားတယ်  (fear)",
            "သူ့နှလုံးသားတစ်ခုလုံး နွေးထွေးကြည်နူးမှုတွေနဲ့ ပြည့်လျှံသွားတယ်  (warmth/love)",
        ],
    },
}


# ===========================================================================
# SECTION 6: PARTICLE GUIDELINES
# ===========================================================================

PARTICLE_GUIDELINES = {
    "subject_markers": {
        "သည်": "Formal literary subject marker",
        "က": "Emphasis, contrast, colloquial subject",
        "မှာ": "Topic marker (as for X...)",
        "rule": "သည် for narration, က for dialogue/emphasis",
    },

    "object_markers": {
        "ကို": "Direct object (him, it, them)",
        "သို့": "Direction / toward (to the mountain)",
        "အတွက်": "Purpose / for (for him, for this)",
        "နဲ့": "With / using (with a sword)",
    },

    "location_markers": {
        "မှာ": "Colloquial location (at, in)",
        "တွင်": "Formal literary location",
        "၌": "Formal/archaic literary location",
        "rule": "တွင်/၌ for narration, မှာ for dialogue",
    },

    "sentence_final_particles": {
        "တယ်": "Neutral statement (casual)",
        "သည်": "Statement (literary narration)",
        "ပါတယ်": "Polite statement",
        "ဘူး": "Negative",
        "မယ်": "Future / intention",
        "ပြီ": "Completion / already done",
        "လဲ": "Question (casual)",
        "လား": "Yes/No question",
        "ပါ": "Soft command / polite request",
        "တာပဲ": "Emphasis / that's just how it is",
        "rule": (
            "NEVER mix formal (သည်) and casual (တယ်) in same character's dialogue.\n"
            "NEVER use Korean/wrong unicode accidentally:\n"
            "  WRONG: ဟန်ဆောင်နေ봤자  (봤자 is Korean!)\n"
            "  RIGHT: ဟန်ဆောင်နေတာ"
        ),
    },
}


# ===========================================================================
# SECTION 7: UNICODE SAFETY RULES
# Critical: prevent mixed-script errors
# ===========================================================================

UNICODE_SAFETY_RULES = {
    "banned_patterns": [
        {
            "pattern": "봐 / 봤자 / 해서 / 는데 (Korean Hangul)",
            "unicode_range": "U+AC00–U+D7FF",
            "reason": "Korean characters injected by AI models into Myanmar text",
            "correct": "တာ / ပေမဲ့ / နေ (context-dependent Myanmar particle)",
            "example": (
                "WRONG: ဟန်ဆောင်နေ봤자 အသုံးမဝင်ပါဘူး\n"
                "RIGHT: ဟန်ဆောင်နေတာ အသုံးမဝင်ပါဘူး"
            ),
        },
        {
            "pattern": "Bengali/Devanagari script (গাঢ় ক খ ড ग ह etc.)",
            "unicode_range": "U+0980–U+09FF (Bengali) | U+0900–U+097F (Devanagari)",
            "reason": (
                "Bengali or Devanagari characters leaked into Myanmar output.\n"
                "Real case observed in Novel-v1:\n"
                "  ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံ\n"
                "  গাঢ় is Bengali for 'deep/dark colour' — AI hallucinated it\n"
                "  instead of writing the Myanmar word."
            ),
            "correct": (
                "Replace with Myanmar color-depth words:\n"
                "  deep/dark green → အစိမ်းရောင်တောက်တောက် / ရင့်သောအစိမ်းရောင်\n"
                "  deep blue       → နက်ပြာရောင် / ပြာနက်\n"
                "  deep red        → အနီတောက် / နီမြင့်"
            ),
            "example": (
                "WRONG: ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံ\n"
                "RIGHT: စုတ်ပြဲနေသာ အစိမ်းရောင်တောက်တောက် ဝတ်ရုံကြီး"
            ),
        },
        {
            "pattern": "؟ (Arabic question mark)",
            "unicode_range": "U+061F",
            "reason": "Arabic question mark used instead of standard ASCII",
            "correct": "? (U+003F — standard ASCII question mark)",
            "example": (
                "WRONG: မင်း ဘယ်မှာ လဲ؟\n"
                "RIGHT: မင်း ဘယ်မှာ လဲ?"
            ),
        },
        {
            "pattern": "Chinese/CJK characters in output",
            "unicode_range": "U+4E00–U+9FFF",
            "reason": "Source language leakage into Myanmar output",
            "correct": "Translate or transliterate every Chinese term",
            "example": (
                "WRONG: 气 ကို သူ အသုံးချလိုက်တယ်\n"
                "RIGHT: ချီ ကို သူ အသုံးချလိုက်တယ်"
            ),
        },
    ],

    "myanmar_unicode_ranges": {
        "basic":      "U+1000–U+109F  (Myanmar basic block — required)",
        "extended_a": "U+AA60–U+AA7F  (Myanmar Extended-A — valid, do NOT strip)",
        "extended_b": "U+A9E0–U+A9FF  (Myanmar Extended-B — valid, do NOT strip)",
        "note": (
            "postprocessor.py remove_non_myanmar_characters() must ONLY strip:\n"
            "  CJK:     U+4E00–U+9FFF\n"
            "  Korean:  U+AC00–U+D7FF\n"
            "  Bengali: U+0980–U+09FF\n"
            "  Arabic:  U+0600–U+06FF\n"
            "Do NOT strip Extended-A/B — they are valid Myanmar Unicode."
        ),
    },

    "postprocessor_regex": {
        "wrong": r"[^\u1000-\u109F\u0020-\u007E\n\r\t]+",
        "correct": r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7FF\u0980-\u09FF\u0900-\u097F\u0600-\u06FF]+",
        "note": (
            "The WRONG regex strips all non-Myanmar non-ASCII — including valid\n"
            "Myanmar Extended-A/B and Bengali leakage without distinction.\n"
            "The CORRECT regex only strips known bad script ranges."
        ),
    },

    "common_ai_mistakes": [
        "Korean Hangul (봐 봤자 해서) mixed into Myanmar — detected by U+AC00-U+D7FF",
        "Bengali script (গাঢ়) mixed into Myanmar — detected by U+0980-U+09FF",
        "Arabic punctuation (؟ ، ؛) — use ASCII ? , ; instead",
        "Chinese chars left in output — must be fully translated",
        "English words left untranslated in narration sections",
        "Starting output with 'Here is the translation:' or 'ဘာသာပြန်ချက်:'",
        "Adding [note: ...] or translator commentary inside output",
    ],
}


# ===========================================================================
# SECTION 8: CULTURAL ADAPTATION RULES
# ===========================================================================

CULTURAL_RULES = {
    "english_idioms": {
        "rule": "Never translate English idioms literally. Find Myanmar equivalent.",
        "examples": [
            {
                "en": "It takes two to tango",
                "wrong_mm": "တင်းဂိုကခုန်ဖို့ နှစ်ယောက်လိုတယ်",
                "correct_mm": "လက်ချင်းနှစ်ဖက် မပွတ်ဘဲ မြည်ဘူး",
            },
            {
                "en": "He let the cat out of the bag",
                "wrong_mm": "အိတ်ထဲက ကြောင်ကို ထုတ်လိုက်တယ်",
                "correct_mm": "လျှို့ဝှက်ချက်ကို ဖြုတ်မိသွားတယ်",
            },
            {
                "en": "Blood is thicker than water",
                "wrong_mm": "သွေးက ရေထက် ထူတယ်",
                "correct_mm": "အသဲချင်းတူသောနေ့",
            },
        ],
    },

    "figurative_language": {
        "rule": (
            "Similes and metaphors: adapt imagery to feel natural in Myanmar.\n"
            "If English metaphor translates naturally → keep it.\n"
            "If it feels foreign → find Myanmar equivalent imagery."
        ),
        "examples": [
            {
                "en": "His heart felt like it was cut by a knife",
                "direct_mm": "သူ့ရင်ထဲ ဓားနဲ့ ဖြတ်သလို ဖြစ်မိတယ်",
                "note": "This works — keep it",
            },
            {
                "en": "Like a lamb to the slaughter",
                "myanmar_equiv": "ကြက်မသိဆိတ်မသိ",
                "note": "Use Myanmar idiom equivalent",
            },
        ],
    },

    "honorifics_address": {
        "rule": "Use Myanmar honorifics based on age and status, not English conventions",
        "mappings": {
            "Master / Teacher":   "ဆရာ (general) / ဆရာကြီး (grand master)",
            "Senior disciple":    "ဆရာနောင်",
            "Junior disciple":    "ဆရာညီ",
            "Young lord / sir":   "ကိုကြီး / မင်းသား",
            "Miss / Lady":        "မမ / ဒကာမ",
            "Elder":              "အကြီးသား / သူကြီး",
            "Respected stranger": "ဆရာ / ဒါနပတိ",
        },
        "warning": "Do NOT use ဦး/ဒေါ်/ကို/မ for non-Myanmar characters unless cultural context demands it",
    },

    "cultivation_novel_terms": {
        "rule": (
            "For xianxia/wuxia/cultivation terms coming through English:\n"
            "Prefer Myanmar transliteration from PINYIN source, not from English.\n"
            "Keep consistent with glossary."
        ),
        "examples": [
            {"en": "Golden Core",    "mm": "ရွှေဘောလုံး (from 金丹)"},
            {"en": "Nascent Soul",   "mm": "ဝိညာဉ်ကလေး (from 元婴)"},
            {"en": "Tribulation",    "mm": "ကြိတ်ကျော်ဒဏ် (from 渡劫)"},
            {"en": "Qi / Chi",       "mm": "ချီ (from 气)"},
            {"en": "Flying Sword",   "mm": "ပျံတိုက် (from 飞剑)"},
            {"en": "Sect",           "mm": "ဂိုဏ်း (large) / အဖွဲ့ (small)"},
            {"en": "Cultivation",    "mm": "ကျင့်ကြံ / တည်းဆိုင်"},
        ],
    },

    "name_transliteration": {
        "rule": (
            "English names of characters originally Chinese → use Pinyin-based Myanmar\n"
            "NOT English pronunciation-based Myanmar.\n"
            "Always defer to novel's established glossary."
        ),
        "example": {
            "character": "Fan Xian (范闲)",
            "wrong_from_english": "ဖန်ရှင်",
            "correct_from_pinyin": "ဖန့်ရှန့်",
            "note": "Use the glossary. Never deviate mid-novel.",
        },
    },

    "measure_words": {
        "rule": "Use Myanmar classifiers (သနပ်) appropriate to the noun",
        "examples": [
            {"noun": "people",   "classifier": "ယောက်",  "example": "လူသုံးယောက်"},
            {"noun": "animals",  "classifier": "ကောင်",  "example": "ကြောင်နှစ်ကောင်"},
            {"noun": "objects",  "classifier": "ခု",     "example": "ဓားတစ်ခု"},
            {"noun": "flat",     "classifier": "ချပ်",   "example": "စာရွက်တစ်ချပ်"},
            {"noun": "long",     "classifier": "ချောင်", "example": "တောင်ကြောတစ်ချောင်"},
            {"noun": "rivers",   "classifier": "သွယ်",   "example": "မြစ်တစ်သွယ်"},
        ],
    },
}


# ===========================================================================
# SECTION 9: FORMATTING RULES
# ===========================================================================

FORMATTING_RULES = {
    "markdown_preservation": {
        "rule": "Preserve ALL original Markdown formatting exactly",
        "preserve": ["*italic*", "**bold**", "# headings", "> blockquotes", "---"],
        "example": (
            "EN: He was *incredibly* fast\n"
            "MM: သူ *မယုံနိုင်လောက်အောင်* မြန်တယ်"
        ),
    },

    "chapter_heading_format": {
        "rule": "Chapter headings MUST follow exact format",
        "format": (
            "# [Chapter Number]\n"
            "\n"
            "## [Chapter Title in Myanmar]"
        ),
        "example": (
            "# 001\n"
            "\n"
            "## ကျင့်ကြံသူငယ်"
        ),
    },

    "paragraph_breaks": {
        "rule": "Preserve original paragraph breaks exactly",
        "note": "Do NOT merge paragraphs. Do NOT split single paragraphs.",
    },

    "ellipsis": {
        "english": "......  or  ...",
        "myanmar": "......  (preserve as-is)",
        "rule": "Keep ellipsis exactly as in source",
    },

    "output_cleanliness": {
        "forbidden_prefix": [
            "Here is the translation:",
            "ဘာသာပြန်ချက်:",
            "Translation:",
            "Below is the translated text:",
        ],
        "forbidden_suffix": [
            "Note: ...",
            "[Translator note: ...]",
            "I have translated the above...",
        ],
        "rule": "Output ONLY Myanmar text. Zero meta-commentary.",
    },

    "translators_notes": {
        "rule": (
            "Include 'Translator's Notes:' section AT THE END when:\n"
            "  - Cultural term needs explanation\n"
            "  - Wordplay cannot be fully preserved\n"
            "  - Significant adaptation was made\n"
            "Format: Translator's Notes: [brief explanation]"
        ),
    },
}


# ===========================================================================
# SECTION 10: VOCABULARY PRECISION
# Common wrong word choices — based on real observed translation errors
# Source: Novel-v1 translated_result vs want_to_translated analysis
# ===========================================================================

VOCABULARY_PRECISION = {

    "demon_evil_terms": {
        "rule": (
            "English 'Demon' has multiple Myanmar translations depending on context.\n"
            "Choose based on speaker's relationship and emotional state."
        ),
        "mappings": [
            {
                "context":   "Enemy/cultivation antagonist — contemptuous",
                "wrong":     "နတ်ဆိုး (supernatural, neutral religious tone)",
                "correct":   "မိစ္ဆာကောင် (evil creature, contemptuous)",
                "reason":    "နတ်ဆိုး sounds mythological/neutral. မိစ္ဆာကောင် carries hatred.",
            },
            {
                "context":   "Formal narrative description",
                "correct":   "နတ်ဆိုး (acceptable when neutral narrator describes)",
            },
            {
                "context":   "Character's angry address to enemy",
                "correct":   "မိစ္ဆာကောင် — with နင် pronoun, short sentence",
                "example":   '"မိစ္ဆာကောင်" လို့ သူ ကြွေးကြော်လိုက်တယ်',
            },
        ],
    },

    "purity_chastity_terms": {
        "rule": (
            "'Purity' in cultivation novels often means chastity/virginity — NOT cleanliness.\n"
            "Wrong word creates completely different meaning."
        ),
        "mappings": [
            {
                "context":   "Body purity / chastity (cultivation, romantic context)",
                "wrong":     "သန့်ရှင်းမှု (cleanliness, hygiene)",
                "correct":   "ဖြူစင်မှု (moral purity, chastity, innocence)",
                "reason":    "သန့်ရှင်းမှု = physical cleanliness. ဖြူစင်မှု = moral/spiritual purity.",
            },
            {
                "context":   "General cleanliness (washing, environment)",
                "correct":   "သန့်ရှင်းမှု (appropriate here)",
            },
        ],
    },

    "exterminate_family_terms": {
        "rule": "Killing entire family/generations needs impactful Myanmar idiom expression.",
        "mappings": [
            {
                "context":   "Executed nine generations / killed entire family line",
                "wrong":     "မျိုးဆက်ကို ကိုးဆက်အထိ သေဒဏ်ပေးခဲ့တယ် (legalistic, bureaucratic tone)",
                "correct":   "မျိုးဆက် ကိုးဆက်လုံးကို အမြစ်ဖြတ် သုတ်သင်သွားတယ် (rooted out completely)",
                "reason":    "အမြစ်ဖြတ် (uproot) + သုတ်သင် (sweep clean) = powerful Myanmar idiom for total annihilation",
            },
        ],
    },

    "hatred_intensity_terms": {
        "rule": "Expressing deep hatred — English idiom 'burning passion' needs Myanmar idiom equivalent.",
        "mappings": [
            {
                "english":   "I hated you with a burning passion",
                "wrong":     "ငါ မင်းကို မီးလို မုန်းတီးခဲ့တယ် (literal — awkward)",
                "correct":   "ငါ နင့်ကို အရိုးစွဲအောင် မုန်းသွားတာ (bone-deep hatred — Myanmar idiom)",
                "reason":    "အရိုးစွဲ = seeped into the bones = deeply ingrained. Natural Myanmar expression.",
            },
            {
                "alternative": "ငါ နင့်ကို သေသည့်တိုင် မမေ့နိုင်လောက်အောင် မုန်းတယ် (hate until death)",
            },
        ],
    },

    "death_threat_expressions": {
        "rule": "Death threats in confrontation scenes need dramatic Myanmar finale phrasing.",
        "mappings": [
            {
                "english":   "Today, I want you to die!",
                "wrong":     "ဒီနေ့၊ မင်းသေစေချင်တယ် (flat, lacks drama)",
                "correct_1": "ဒီနေ့ နင့်ကို အသေသတ်ရမယ့် နေ့ပဲ (today is the day you die — declarative)",
                "correct_2": "ဒီနေ့ နင် ကလဲ့စားချေရမယ် (today you pay the debt — implies execution)",
                "correct_3": "ဒီနေ့ နင်သေရမယ်! (direct, short, powerful)",
                "reason":    "Myanmar confrontation speeches end with declarative fate statements, not wishes.",
            },
        ],
    },

    "robe_appearance_terms": {
        "rule": "Describing torn clothing in battle scenes — word choice affects visual impact.",
        "mappings": [
            {
                "english":   "deep green robes that had been torn to shreds",
                "wrong":     "ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံ (Bengali script leaked: গাঢ়)",
                "correct":   "အပေါ်မှ အောက်ထိ စုတ်ပြဲနေသာ အစိမ်းရောင်တောက်တောက် ဝတ်ရုံကြီး",
                "breakdown": {
                    "အပေါ်မှ အောက်ထိ": "from top to bottom",
                    "စုတ်ပြဲနေသာ":     "torn/shredded (literary သာ particle)",
                    "တောက်တောက်":      "vivid/bright (replaces Bengali গাঢ়)",
                },
            },
        ],
    },

    "war_flag_simile": {
        "rule": "Simile comparison — battle flag visual should evoke power, not lightness.",
        "mappings": [
            {
                "english": "waved lightly in the mountain breeze like a war flag",
                "wrong":   "စစ်ပွဲအလံလို ပေါ့ပေါ့ပါးပါး လွှဲယမ်းနေတယ် (ပေါ့ပေါ့ပါးပါး = lightly/trivially)",
                "correct": "စစ်အလံတစ်ခု ထောင်ထားသလို တစ်လူလူ လွင့်နေသည် (flag standing proud, floating)",
                "reason":  "တစ်လူလူ = wavering/floating with dignity. ပေါ့ပေါ့ပါးပါး = trivially light — wrong tone for epic scene.",
            },
        ],
    },

    "narration_verb_precision": {
        "rule": "Describing character's state/appearance — verb choice sets literary register.",
        "mappings": [
            {
                "english": "Fang Yuan was in deep green robes",
                "wrong":   "ဖန်ယွမ်ဟာ ... ဝတ်ရုံတွေနဲ့ ရှိနေခဲ့တယ် (casual/flat)",
                "correct": "ဖန်ယွမ် သည် ... ဝတ်ရုံကြီးကို ဝတ်ထားသည် (literary, character-establishing)",
                "reason":  "ရှိနေခဲ့တယ် = 'was there with' (vague). ဝတ်ထားသည် = 'wore' (precise, literary).",
            },
            {
                "english": "his entire body was covered in blood",
                "wrong":   "သူ့ကိုယ်ခန္ဓာတစ်ခုလုံးက သွေးတွေနဲ့ ဖုံးလွှမ်းနေတယ် (casual တယ်)",
                "correct": "သူ့တစ်ကိုယ်လုံးမှာ သွေးများဖြင့် ပေရေနေသည် (literary သည်, ဖြင့် formal)",
                "reason":  "Battle aftermath narration → literary register required.",
            },
        ],
    },
}


# ===========================================================================
# SECTION 11: CONFRONTATION SPEECH PATTERN
# Real example analysis — want_to_translated vs translated_result
# Novel: Reverend Insanity — Fang Yuan confrontation scene
# ===========================================================================

CONFRONTATION_SPEECH_PATTERN = {

    "description": (
        "Confrontation/accusation speeches are the most emotionally charged moments.\n"
        "They require a specific pattern of rules applied together:\n"
        "  1. Enemy pronoun (နင်)\n"
        "  2. Vivid tense (drop ခဲ့)\n"
        "  3. One accusation per sentence (split comma chains)\n"
        "  4. Precise vocabulary (မိစ္ဆာကောင်, ဖြူစင်မှု, အမြစ်ဖြတ်)\n"
        "  5. Myanmar idiom for hatred and death threat\n"
        "  6. Literary narration for surrounding scene description"
    ),

    "real_example": {
        "original_english": (
            '"Demon, 300 years ago you insulted me, took away my body\'s purity, '
            'killed my entire family and executed my nine generations. '
            'From that moment onwards, I hated you with a burning passion! '
            'Today, I want you to die!"\n\n'
            '......\n\n'
            'Fang Yuan was in deep green robes that had been torn to shreds. '
            'His hair was disheveled and his entire body was covered in blood. '
            'He looked around.\n\n'
            'The bloody robes waved lightly in the mountain breeze like a war flag.'
        ),

        "bad_translation": (
            '"နတ်ဆိုး၊ သုံးရာနှစ်လောက်က မင်းက ငါ့ကို စော်ကားခဲ့တယ်၊ '
            'ငါ့ခန္ဓာကိုယ်ရဲ့ သန့်ရှင်းမှုကို ယူသွားခဲ့တယ်၊ '
            'ငါ့မိသားစုတစ်ခုလုံးကို သတ်ခဲ့ပြီး ငါ့မျိုးဆက်ကို ကိုးဆက်အထိ '
            'သေဒဏ်ပေးခဲ့တယ်။ အဲဒီအချိန်ကစပြီး ငါ မင်းကို မီးလို မုန်းတီးခဲ့တယ်! '
            'ဒီနေ့၊ မင်းသေစေချင်တယ်!" '
            '...... '
            'ဖန်ယွမ်ဟာ ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံတွေနဲ့ ရှိနေခဲ့တယ်။ '
            'သူ့ဆံပင်တွေ ရှုပ်ပွနေပြီး သူ့ကိုယ်ခန္ဓာတစ်ခုလုံးက သွေးတွေနဲ့ '
            'ဖုံးလွှမ်းနေတယ်။သူပတ်ဝန်းကျင်ကို ကြည့်လိုက်တယ်။ '
            'သွေးစွန်းနေတဲ့ ဝတ်ရုံတွေဟာ တောင်တန်းလေထဲမှာ စစ်ပွဲအလံလို '
            'ပေါ့ပေါ့ပါးပါး လွှဲယမ်းနေတယ်။'
        ),

        "good_translation": (
            '"မိစ္ဆာကောင် လွန်ခဲ့တဲ့ နှစ်သုံးရာလောက်တုန်းက '
            'နင် ငါ့ကို စော်ကားတယ် '
            'ငါ့ခန္ဓာရဲ့ ဖြူစင်မှုကို နင် ဖျက်ဆီးတယ်။ '
            'ငါ့ရဲ့ မျိုးဆက် ကိုးဆက်လုံးကို အမြစ်ဖြတ် သုတ်သင်သွားတယ်။ '
            'အဲ့ဒီအချိန်ကစပြီး ငါ နင့်ကို အရိုးစွဲအောင် မုန်းသွားတာ။ '
            'ဒီနေ့ နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ" '
            'ဖန်ယွမ် သည် အပေါ်မှ အောက်ထိ စုတ်ပြဲနေသာ '
            'အစိမ်းရောင်တောက်တောက် ဝတ်ရုံကြီးကို ဝတ်ထားသည်။ '
            'သူ့၏ ဆံပင်များမှာ ဖရိုဖရဲ ဖြစ်နေပြီး '
            'သူ့ တစ်ကိုယ်လုံးမှာ သွေးများဖြင့် ပေရေနေသည်။ '
            'သွေးများဖြင့် ပေကြံနေသာ ဝတ်ရုံရှည်ကြီးမှာ '
            'တောင်လေပြထဲတွင် စစ်အလံတစ်ခု ထောင်ထားသလို တစ်လူလူ လွင့်နေသည်။'
        ),

        "error_analysis": {
            "error_1": {
                "issue":   "Wrong pronoun — မင်း instead of နင်",
                "bad":     "မင်းက ငါ့ကို စော်ကားခဲ့တယ်",
                "good":    "နင် ငါ့ကို စော်ကားတယ်",
                "rule":    "Enemy speaker → နင် mandatory",
            },
            "error_2": {
                "issue":   "Wrong vocabulary — သန့်ရှင်းမှု instead of ဖြူစင်မှု",
                "bad":     "ငါ့ခန္ဓာကိုယ်ရဲ့ သန့်ရှင်းမှု",
                "good":    "ငါ့ခန္ဓာရဲ့ ဖြူစင်မှု",
                "rule":    "Purity/chastity → ဖြူစင်မှု (not cleanliness)",
            },
            "error_3": {
                "issue":   "Tense particle ခဲ့ kills vivid anger intensity",
                "bad":     "စော်ကားခဲ့တယ် / ယူသွားခဲ့တယ် / သတ်ခဲ့ပြီး",
                "good":    "စော်ကားတယ် / ဖျက်ဆီးတယ် / သုတ်သင်သွားတယ်",
                "rule":    "Anger accusation speech → drop ခဲ့ for vivid present intensity",
            },
            "error_4": {
                "issue":   "Comma-chained long sentence — should be split",
                "bad":     "...စော်ကားခဲ့တယ်၊ ...ယူသွားခဲ့တယ်၊ ...သတ်ခဲ့ပြီး...",
                "good":    "One accusation per sentence. Each ends with ။",
                "rule":    "Confrontation speech → one accusation, one sentence",
            },
            "error_5": {
                "issue":   "Weak hatred idiom — literal translation",
                "bad":     "မင်းကို မီးလို မုန်းတီးခဲ့တယ်",
                "good":    "နင့်ကို အရိုးစွဲအောင် မုန်းသွားတာ",
                "rule":    "Use Myanmar idiom: အရိုးစွဲ = bone-deep",
            },
            "error_6": {
                "issue":   "Flat death threat — lacks Myanmar dramatic finale",
                "bad":     "မင်းသေစေချင်တယ်",
                "good":    "နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ",
                "rule":    "Death declaration = declarative fate, not wish",
            },
            "error_7": {
                "issue":   "Bengali script leaked into narration (গাঢ়)",
                "bad":     "ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်",
                "good":    "စုတ်ပြဲနေသာ အစိမ်းရောင်တောက်တောက်",
                "rule":    "Bengali Unicode U+0980-U+09FF — must be caught by postprocessor",
            },
            "error_8": {
                "issue":   "Narration register — casual တယ် instead of literary သည်",
                "bad":     "ဖန်ယွမ်ဟာ ... ရှိနေခဲ့တယ်",
                "good":    "ဖန်ယွမ် သည် ... ဝတ်ထားသည်",
                "rule":    "Battle aftermath scene description → literary သည် register",
            },
            "error_9": {
                "issue":   "War flag simile — ပေါ့ပေါ့ပါးပါး wrong tone (trivially light)",
                "bad":     "စစ်ပွဲအလံလို ပေါ့ပေါ့ပါးပါး လွှဲယမ်းနေတယ်",
                "good":    "စစ်အလံတစ်ခု ထောင်ထားသလို တစ်လူလူ လွင့်နေသည်",
                "rule":    "Epic simile → dignified motion word (တစ်လူလူ), literary register",
            },
        },
    },

    "confrontation_checklist": [
        "① Pronoun: enemy → နင် (not မင်း)",
        "② Tense: accusation speech → drop ခဲ့ for vivid intensity",
        "③ Structure: one accusation per sentence (split comma chains)",
        "④ Vocabulary: မိစ္ဆာကောင် / ဖြူစင်မှု / အမြစ်ဖြတ် (precision terms)",
        "⑤ Hatred: Myanmar idiom — အရိုးစွဲ / သေသည့်တိုင် မမေ့နိုင်",
        "⑥ Death threat: declarative fate — '... ရမယ့် နေ့ပဲ' / '... သေရမယ်'",
        "⑦ Narration: literary သည် register for scene description",
        "⑧ Unicode: no Bengali (গাঢ়) / Korean (봐) / Arabic (؟) leakage",
        "⑨ Simile: dignified motion words for epic scenes (တစ်လူလူ not ပေါ့ပေါ့ပါးပါး)",
    ],
}



# ===========================================================================
# SECTION 12: PIPELINE INTEGRATION
# For use in translator.py and rewriter.py
# ===========================================================================

PIPELINE_SETTINGS = {
    "recommended_temperature": {
        "stage1_translation": 0.2,
        "stage2_rewrite":     0.4,
        "note": (
            "0.2 for literal accuracy in Stage 1\n"
            "0.4 for natural expression in Stage 2\n"
            "NEVER use 0.1 or below — produces robotic output"
        ),
    },

    "stage1_goal": (
        "COMPLETE and ACCURATE translation.\n"
        "Literal is fine. Style will be fixed in Stage 2.\n"
        "Priority: nothing skipped, nothing added."
    ),

    "stage2_goal": (
        "REWRITE for natural Myanmar literary quality.\n"
        "Fix: dialogue tags, pronoun choices, sentence rhythm,\n"
        "     emotion expression, particle register.\n"
        "DO NOT change story content."
    ),

    "chunk_size": {
        "recommended": 900,
        "max": 1000,
        "note": "Smaller chunks = better quality per chunk on 16GB RAM systems",
    },
}


# ===========================================================================
# SECTION 11: PROMPT BUILDER
# Generate prompt snippet for injection into LLM calls
# ===========================================================================

def build_linguistic_context(
    source_lang: str = "English",
    scene_type: str = "narration",
    include_unicode_warning: bool = True,
) -> str:
    """
    Generate a prompt snippet with EN→MM linguistic rules.

    Args:
        source_lang:             "English" or "English (from Chinese original)"
        scene_type:              "narration" | "dialogue" | "action" | "confrontation"
        include_unicode_warning: Include unicode safety rules in prompt

    Returns:
        str: Formatted prompt snippet for injection into system prompt
    """

    scene_sentence_rule = {
        "narration":       "Medium sentences (10-18 words). Literary သည် particle.",
        "dialogue":        "Short natural sentences. တယ်/ဘူး particles. Real speech rhythm.",
        "action":          "SHORT sentences (3-7 words). Fast rhythm. Active verbs.",
        "confrontation":   "SHORT punchy sentences. One accusation per sentence. Vivid tense.",
    }.get(scene_type, "Adapt sentence length to match scene intensity.")

    unicode_section = ""
    if include_unicode_warning:
        unicode_section = """
UNICODE SAFETY:
  ❌ NEVER output Korean chars: 봤자 해서 는데
  ❌ NEVER use Arabic ? mark: ؟
  ❌ NEVER leave Chinese chars in output
  ✅ Use only Myanmar Unicode (U+1000-U+109F, U+AA60-U+AA7F)
  Example WRONG: ဟန်ဆောင်နေ봐  →  CORRECT: ဟန်ဆောင်နေတာ
"""

    return f"""
[LINGUISTIC RULES — {source_lang} → Myanmar]

1. STRUCTURE: English SVO → Myanmar SOV
   EN: He [S] struck [V] the enemy [O]
   MM: သူ [S] ရန်သူကို [O] ထိုးလိုက်တယ် [V]
   Time phrases → move to SENTENCE START

2. DIALOGUE FORMAT (MANDATORY):
   ✅ CORRECT: "စကားပြော" လို့ [character] [verb]တယ်
   ❌ WRONG:   "စကားပြော" ဟု [character] မေးမြန်းလေသည်
   Enemy/hostile speaker: always use "နင်" not "မင်း"

3. PRONOUNS:
   Enemy/contempt → နင် (2nd), ဒီကောင် (3rd)
   Equal/neutral  → မင်း (2nd), သူ/သူမ (3rd)
   Formal/polite  → ခင်ဗျ / ရှင် (2nd)
   Self (casual)  → ငါ / Self (formal) → ကျွန်တော်/ကျွန်မ

4. SENTENCE RHYTHM:
   {scene_sentence_rule}

5. EMOTIONS — SHOW PHYSICALLY:
   ❌ သူ ဝမ်းနည်းတယ် (abstract label)
   ✅ သူ့ ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလို ဖြစ်မိတယ် (physical)

6. TENSE:
   Past (standard):  ခဲ့တယ်
   Vivid accusation: drop ခဲ့ → present intensity

7. NARRATION STYLE:
   Scene description / action → သည် particle (literary)
   Close POV perception       → တယ် particle (casual)
{unicode_section}
OUTPUT: ONLY Myanmar text. No notes. No English. No Chinese. Preserve Markdown.
"""


def build_rewriter_prompt(
    glossary_text: str = "",
    context: str = "",
) -> str:
    """
    Generate Stage 2 rewriter system prompt for EN→MM literary rewrite.

    Args:
        glossary_text: Character name glossary block
        context:       Previous chunk/chapter context (Burmese text)

    Returns:
        str: Complete system prompt for Stage 2 rewriter
    """

    context_section = ""
    if context:
        ctx = context[-500:] if len(context) > 500 else context
        context_section = f"\nPREVIOUS CONTEXT (for continuity):\n{ctx}\n---\n"

    glossary_section = ""
    if glossary_text:
        glossary_section = f"\n{glossary_text}\n"

    return f"""You are an expert Myanmar literary editor rewriting a rough English→Myanmar translation.
{context_section}{glossary_section}
YOUR TASK: Rewrite the rough translation into natural, flowing, literary Myanmar.
You are NOT re-translating. You are REWRITING for quality and naturalness.

MANDATORY REWRITING RULES:

RULE 1 — DIALOGUE TAGS
  Every dialogue tag MUST follow this format:
  "spoken words" လို့ [character] [verb]တယ်
  NEVER use: "..." ဟု ... မေးမြန်းလေသည်

RULE 2 — PRONOUNS
  Enemy/hostile context:  နင် (NEVER မင်း when speaking to enemy)
  Equal/casual:           မင်း
  Self casual:            ငါ
  Self formal:            ကျွန်တော် / ကျွန်မ

RULE 3 — SENTENCE LENGTH
  Action/battle scenes:   3-7 words per sentence MAX
  Confrontation speech:   ONE accusation per sentence — split all comma chains
  Calm narration:         10-18 words acceptable

RULE 4 — CONFRONTATION TENSE (CRITICAL)
  Accusation speeches → DROP ခဲ့ particle for vivid intensity
  WRONG: နင် ငါ့ကို စော်ကားခဲ့တယ် (neutral past recall)
  RIGHT: နင် ငါ့ကို စော်ကားတယ်    (burning present-vivid memory)

RULE 5 — VOCABULARY PRECISION
  Demon (enemy address)     → မိစ္ဆာကောင် (NOT နတ်ဆိုး)
  Purity / chastity         → ဖြူစင်မှု   (NOT သန့်ရှင်းမှု)
  Exterminate family        → အမြစ်ဖြတ် သုတ်သင် (NOT သေဒဏ်ပေး)
  Burning hatred            → အရိုးစွဲအောင် မုန်း (NOT မီးလို မုန်းတီး)
  Death threat (today)      → နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ (NOT မင်းသေစေချင်တယ်)
  Deep color (dark green)   → တောက်တောက် / ရင့် (NOT Bengali গাঢ়)
  Epic motion (flag waves)  → တစ်လူလူ လွင့် (NOT ပေါ့ပေါ့ပါးပါး လွှဲ)

RULE 6 — EMOTIONS
  Show through physical sensation, not abstract labels
  WRONG: သူ ဝမ်းနည်းတယ်
  RIGHT: သူ့ ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလို ဖြစ်မိတယ်

RULE 7 — REGISTER
  Narration/battle scene description: သည် / ၏ / သော / ဖြင့် (literary)
  Dialogue/close-POV:                 တယ် / ဘူး / မယ် (conversational)
  WRONG: ဖန်ယွမ်ဟာ ဝတ်ရုံနဲ့ ရှိနေခဲ့တယ် (casual for epic scene)
  RIGHT: ဖန်ယွမ် သည် ဝတ်ရုံကြီးကို ဝတ်ထားသည် (literary)

RULE 8 — UNICODE SAFETY (CRITICAL)
  ❌ Bengali script (গাঢ় ক খ) U+0980-U+09FF: FORBIDDEN
  ❌ Korean Hangul (봐 봤자 해서) U+AC00-U+D7FF: FORBIDDEN
  ❌ Arabic question mark (؟) U+061F: use ? instead
  ❌ Chinese characters in output: FORBIDDEN
  ✅ Myanmar Unicode only: U+1000-U+109F, U+AA60-U+AA7F

RULE 9 — CONTENT INTEGRITY
  Do NOT add events. Do NOT remove events.
  Only improve language quality, register, and vocabulary.

OUTPUT: ONLY the rewritten Myanmar text. Nothing else.
"""
