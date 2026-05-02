"""
Chinese-to-Myanmar Linguistic Transformation Rules
Novel-v1 Project — ch_mm_rules.py

Based on:
  - cn_mm_rules.py (original lightweight version)
  - en_mm_rules.py structure (expanded version)
  - Real translation error analysis (Reverend Insanity / Fang Yuan scene)
  - Chinese linguistic patterns specific to Myanmar adaptation
  - Cultivation/Xianxia/Wuxia novel conventions

Covers:
  - SVO (Chinese) → SOV (Myanmar) structural conversion
  - Chinese aspect markers → Myanmar particle mapping
  - Pronoun resolution by character hierarchy and emotional context
  - Dialogue naturalness rules
  - Literary narration vs casual narration register
  - Chinese-specific grammar patterns (把/被/得/地/的)
  - Unicode safety rules (Bengali/Korean/Arabic leakage)
  - Cultural adaptation (成语, honorifics, cultivation terms)
  - Vocabulary precision (real error examples)
  - Confrontation speech pattern
"""



# ===========================================================================
# SECTION 1: STRUCTURAL CONVERSION
# SVO (Chinese) → SOV (Myanmar)
# ===========================================================================

SVO_TO_SOV_RULES = {
    "basic_structure": {
        "rule": (
            "Chinese: Subject + Verb + Object\n"
            "Myanmar: Subject + Object + Verb\n"
        ),
        "example": (
            "CN: 他(S) + 打(V) + 他(O)  →  MM: သူ(S) + သူ့ကို(O) + ထိုးလိုက်တယ်(V)\n"
            "CN: 她(S) + 说(V) + 话(O)  →  MM: သူမ(S) + စကားကို(O) + ပြောတယ်(V)"
        ),
    },

    "time_adverbials": {
        "rule": "Time expressions move to SENTENCE START in Myanmar",
        "example": (
            "CN: 他昨天来了\n"
            "MM: မနေ့က သူ ရောက်လာတယ်  (昨天 moves to front)\n\n"
            "CN: 三百年前\n"
            "MM: လွန်ခဲ့တဲ့ နှစ်သုံးရာကျော်တုန်းက  (time phrase → sentence start)"
        ),
    },

    "location_adverbials": {
        "rule": "Location phrases move to BEFORE the verb in Myanmar",
        "example": (
            "CN: 他在山上打架\n"
            "MM: သူ တောင်ပေါ်မှာ တိုက်ခဲ့တယ်  (在山上 → verb position)"
        ),
    },

    "adjective_position": {
        "rule": (
            "Chinese: adjective BEFORE noun (高个子男人)\n"
            "Myanmar: modifier AFTER noun with သော/တဲ့, OR restructure naturally\n"
        ),
        "example": (
            "CN: 深绿色长袍\n"
            "MM: အစိမ်းရောင်တောက်တောက် ဝတ်ရုံရှည်ကြီး  (natural adaptation)\n"
            "NOT: ရောင်အနက်ရောင် အစိမ်းကြီးမားသော ဝတ်ရုံ  (awkward)"
        ),
    },

    "relative_clauses": {
        "rule": "Chinese 的-clauses → Myanmar သော/တဲ့ before noun",
        "example": (
            "CN: 救了他的人  →  MM: သူ့ကို ကယ်တင်တဲ့ လူ\n"
            "CN: 飘动的长袍  →  MM: လွင့်မျောနေသာ ဝတ်ရုံ"
        ),
    },

    "negation": {
        "rule": "Myanmar မ precedes verb; ဘူး ends negative sentence",
        "example": (
            "CN: 他没有说话\n"
            "MM: သူ မပြောဘူး  (NOT: သူ ပြောမဘူး)\n\n"
            "CN: 不是\n"
            "MM: မဟုတ်ဘူး"
        ),
    },

    "ba_sentence": {
        "rule": (
            "Chinese 把-sentence: Subject + 把 + Object + Verb\n"
            "Myanmar: Convert to active, object-verb order naturally"
        ),
        "example": (
            "CN: 他把剑拔出来了\n"
            "MM: သူ ဓားကို ဆွဲထုတ်လိုက်တယ်  (把 disappears, SOV restored)\n\n"
            "CN: 把我的纯洁夺走了\n"
            "MM: ငါ့ရဲ့ ဖြူစင်မှုကို ဖျက်ဆီးသွားတယ်"
        ),
    },

    "bei_passive": {
        "rule": (
            "Chinese 被-sentence (passive): Agent + 被 + Verb\n"
            "Myanmar: Prefer active voice. If passive needed, use ခံ"
        ),
        "example": (
            "CN: 他被剑刺中了\n"
            "MM: ဓားက သူ့ကို ထိုးသွားတယ်  (active preferred)\n"
            "OR: သူ ဓားနဲ့ ထိုးခံလိုက်ရတယ်  (passive emphasis)"
        ),
    },

    "de_particles": {
        "rule": "Chinese 的/得/地 particles → different Myanmar structures",
        "mappings": {
            "的 (noun modifier)": "→ သော/တဲ့/ရဲ့  before or after noun",
            "得 (complement)":    "→ embed into verb phrase naturally",
            "地 (adverb marker)": "→ adverb directly before verb (no marker needed)",
        },
        "example": (
            "CN: 飘动地 走路  →  MM: တလူလူနဲ့ လျှောက်သွားတယ်  (地 dropped, adverb direct)\n"
            "CN: 快得很         →  MM: အလွန် မြန်တယ်"
        ),
    },

    "question_patterns": {
        "rule": "Chinese question markers → Myanmar sentence-final particles",
        "mappings": {
            "吗 (yes/no)":    "→ လား at sentence end",
            "呢 (soft)":      "→ ရော / သော at sentence end",
            "吧 (tag)":       "→ နော / ဟုတ်လား at end",
            "什么 (what)":    "→ ဘာ at appropriate position",
            "怎么 (how)":     "→ ဘယ်လို",
            "为什么 (why)":   "→ ဘာကြောင့်",
        },
    },
}


# ===========================================================================
# SECTION 2: ASPECT MARKER → MYANMAR PARTICLE MAPPING
# Chinese uses aspect markers (了/着/过) instead of tense
# ===========================================================================

ASPECT_TO_PARTICLE = {
    "le_completion": {
        "chinese": "了 (completed action)",
        "myanmar": "ပြီ / ပြီတယ် / လိုက်တယ်",
        "example": (
            "CN: 他来了  →  MM: သူ ရောက်လာပြီ\n"
            "CN: 打了他  →  MM: သူ့ကို ထိုးလိုက်တယ်"
        ),
    },

    "zhe_continuous": {
        "chinese": "着 (ongoing state/action)",
        "myanmar": "နေတယ် / ထားတယ်",
        "example": (
            "CN: 他站着  →  MM: သူ ရပ်နေတယ်\n"
            "CN: 穿着长袍  →  MM: ဝတ်ရုံ ဝတ်ထားတယ်"
        ),
    },

    "guo_experience": {
        "chinese": "过 (past experience)",
        "myanmar": "ဖူးတယ် / ဖူးသည် / ခဲ့တယ်",
        "example": (
            "CN: 他来过  →  MM: သူ လာဖူးတယ်\n"
            "CN: 我恨过你  →  MM: ငါ နင့်ကို မုန်းဖူးတယ်"
        ),
    },

    "anger_vivid_accusation": {
        "rule": (
            "SPECIAL RULE for anger/accusation speeches:\n"
            "Drop completion markers and ခဲ့ to create vivid present intensity.\n"
            "The accused action feels PRESENT and BURNING, not past and resolved."
        ),
        "example": (
            "Standard past:\n"
            "  CN: 你侮辱了我  →  MM: နင် ငါ့ကို စော်ကားခဲ့တယ်  (neutral recall)\n\n"
            "Vivid accusation:\n"
            "  CN: 你侮辱了我  →  MM: နင် ငါ့ကို စော်ကားတယ်    (burning memory)\n\n"
            "Use vivid form in: accusation speeches, confrontations, revenge declarations"
        ),
    },
}


# ===========================================================================
# SECTION 3: PRONOUN RESOLUTION
# Chinese pronouns + hierarchy + emotional context → Myanmar pronouns
# ===========================================================================

PRONOUN_HIERARCHY = {
    "first_person": {
        "我 casual":        "ငါ (male or female, casual/equal)",
        "我 formal_male":   "ကျွန်တော်",
        "我 formal_female": "ကျွန်မ",
        "我 humble":        "ကျွန်ုပ်",
        "我 arrogant":      "ငါ (flat, no softening, dominant character)",
        "咱们 inclusive":   "ငါတို့ / ကျွန်တော်တို့",
        "rule": (
            "Choose based on character's status and emotional state:\n"
            "Protagonist in battle → ငါ (assertive)\n"
            "Junior to master     → ကျွန်တော်\n"
            "Formal announcement  → ကျွန်ုပ်"
        ),
    },

    "second_person": {
        "你 to_enemy":           "နင် (contemptuous — MANDATORY for enemy address)",
        "你 to_inferior":        "မင်း (casual superior to inferior)",
        "你 to_equal":           "မင်း / ခင်ဗျ",
        "您 polite":             "ခင်ဗျ / ဆရာ",
        "你们 plural":           "မင်းတို့ / နင်တို့ (based on context)",
        "rule": (
            "CRITICAL:\n"
            "你 → နင် ONLY when speaker is hostile/contemptuous to target\n"
            "你 → မင်း for neutral/casual address\n"
            "Enemy speech: 你 = နင် without exception\n\n"
            "EXAMPLE from Fang Yuan scene:\n"
            "  WRONG: 你 → မင်း (in accusation speech to hated enemy)\n"
            "  RIGHT: 你 → နင်  (enemy address, contemptuous)"
        ),
    },

    "third_person": {
        "他 male":              "သူ",
        "她 female":            "သူမ",
        "它 object/animal":     "သူ / ၎င်း / အဲဒါ",
        "他们/她们 plural":      "သူတို့",
        "contemptuous_3rd":     "ဒီကောင် / အဲဒီကောင်",
        "respectful_3rd":       "ထိုပုဂ္ဂိုလ် / သူတော်",
        "rule": (
            "Use သူ by default for known male character\n"
            "Use ဒီကောင် when speaker holds contempt for third party\n"
            "Use ထိုပုဂ္ဂိုလ် for grand/respected figures in formal narration"
        ),
    },
}


# ===========================================================================
# SECTION 4: DIALOGUE RULES
# ===========================================================================

DIALOGUE_RULES = {
    "dialogue_tag_format": {
        "rule": "MANDATORY FORMAT for all dialogue tags in Myanmar",
        "correct": [
            '"ငါ့ကို စော်ကားတယ်" လို့ သူ ဆိုတယ်',
            '"မိစ္ဆာကောင်!" လို့ ဖန်ယွမ် အော်လိုက်တယ်',
            '"ဒါ ဘာကြောင့်လဲ" လို့ သူမ တိုးတိုး မေးလိုက်တယ်',
            '"ရပ်!" လို့ ဆရာကြီး ကြွေးကြော်လိုက်တယ်',
        ],
        "wrong": [
            '"..." ဟု သူ မေးမြန်းလေသည်',
            '"..." ဟု ပြောဆိုလေသည်',
            '"..." ဟု ဆိုကာ လေသည်',
            '"..." ဟု ကြွေးကြော်ရင်း',
        ],
        "rule_note": (
            "ဟု...လေသည် pattern is archaic Burmese — NEVER use in modern novel translation.\n"
            "Chinese 说 → Myanmar လို့ [name] ပြောတယ်"
        ),
    },

    "speech_verb_from_chinese": {
        "说 (said)":        "ပြောတယ် / ပြောလိုက်တယ်",
        "问 (asked)":       "မေးတယ် / မေးလိုက်တယ်",
        "喊/叫 (shouted)":  "အော်လိုက်တယ် / ကြွေးကြော်လိုက်တယ်",
        "低声 (whispered)": "တိုးတိုး ပြောတယ် / တဆိတ်ဆိတ် ဆိုတယ်",
        "冷声 (coldly)":    "အေးစက်စက်နဲ့ ပြောတယ်",
        "笑着说 (said laughing)": "ရယ်ရင်း ပြောတယ် / ပြုံးရင်း ဆိုတယ်",
        "怒吼 (roared angrily)":  "ဒေါသတကြီး အော်ငြိမ်းလိုက်တယ်",
        "答 (replied)":     "ပြန်ပြောတယ် / တုံ့ပြန်တယ်",
        "命令 (commanded)": "အမိန့်ပေးလိုက်တယ်",
        "嘟囔 (muttered)":  "တဆိတ်ဆိတ် ငြီးငူတယ်",
    },

    "internal_monologue_from_chinese": {
        "心想 (thought)":    "(ဒါ မဖြစ်နိုင်ဘူး) လို့ ထင်မိတယ်",
        "心道 (thought)":    "စိတ်ထဲမှာ တွေးမိတယ် — ဒါ မဟုတ်ဘူးဆိုတာ",
        "心中暗想":          "*ဒါမျိုး ဖြစ်ရမှာ မဟုတ်ဘူး*  (italic in markdown)",
        "rule": "Internal thought ≠ spoken dialogue. Must feel close and personal.",
    },

    "sentence_rhythm_by_scene": {
        "action_combat (战斗)": (
            "SHORT sentences. 3-6 words each. Fast rhythm.\n"
            "Example:\n"
            "  သူ တိုးဝင်လာတယ်။ ဓားကို ကာမိတယ်။ ချက်ချင်း ပြန်ထိုးလိုက်တယ်။"
        ),
        "confrontation (对峙/质问)": (
            "SHORT, PUNCHY. One accusation per sentence. No comma chains.\n"
            "Example:\n"
            "  နင် ငါ့ကို စော်ကားတယ်။\n"
            "  ငါ့ မိသားစုကို သတ်တယ်။\n"
            "  ဒီနေ့ နင် ကြေးချေရမယ်။"
        ),
        "calm_narration (叙述)": (
            "MEDIUM sentences. 10-18 words okay. Literary tone.\n"
            "Use သည်/၏ particles."
        ),
        "romantic (浪漫)": (
            "Slightly longer. Poetic rhythm.\n"
            "Physical sensation over abstract labels."
        ),
    },
}


# ===========================================================================
# SECTION 5: NARRATION STYLE RULES
# ===========================================================================

NARRATION_RULES = {
    "literary_narration": {
        "particles":  "သည် / ၏ / သော / ဖြင့် / တွင် / ၌",
        "use_when":   "Battle scene, epic description, character introduction, death scene",
        "example": (
            "CN: 范闲穿着破碎的深绿色长袍\n"
            "MM: ဖန်ယွမ် သည် အပေါ်မှ အောက်ထိ စုတ်ပြဲနေသာ\n"
            "    အစိမ်းရောင်တောက်တောက် ဝတ်ရုံကြီးကို ဝတ်ထားသည်"
        ),
    },

    "casual_narration": {
        "particles":  "တယ် / တာ / နေတယ် / မယ် / ဘူး",
        "use_when":   "Close POV, character's immediate perception, light comedy scenes",
        "example": (
            "CN: 他看了看四周\n"
            "MM: သူ ပတ်ဝန်းကျင်ကို ကြည့်လိုက်တယ်"
        ),
    },

    "register_by_scene": {
        "rule": (
            "Scene type determines narration register:\n"
            "  战斗 battle / 死亡 death / 史诗 epic  →  Literary သည်\n"
            "  日常 daily / 轻松 light / POV close   →  Casual တယ်\n"
            "  混合 mixed (dialogue + action)         →  Match scene by sentence"
        ),
    },

    "emotion_show_not_tell": {
        "rule": "Show emotions physically. NEVER abstract labels alone.",
        "wrong": [
            "他感到非常悲伤  →  MM: သူ အလွန် ဝမ်းနည်းတယ်  (abstract)",
            "他感到愤怒       →  MM: သူ ဒေါသဖြစ်တယ်          (label only)",
        ],
        "correct": [
            "Sadness   → သူ့နှလုံးသားဟာ တစ်စစီ ကျိုးပဲ့ပျက်စီးသွားသလို ခံစားလိုက်ရတယ်",
            "Anger     → ဒေါသကြောင့် သူ့မေးကြောတွေ ထောင်တက်လာတယ်",
            "Shock     → သူ့ ခြေထောက်တွေ ရပ်မိသွားတယ်",
            "Fear      → သူ့ကျောပြင်တစ်ခုလုံး အေးစိမ့်သွားပြီး တုန်လှုပ်ခြောက်ခြားသွားတယ်",
            "Hate      → ရင်ထဲမှာ နေနှစ်ပေါင်းများစွာ ဖျောက်မနိုင်ဘဲ ရှိနေတဲ့ မုန်းမီး",
        ],
    },
}


# ===========================================================================
# SECTION 6: PARTICLE GUIDELINES
# ===========================================================================

PARTICLE_GUIDELINES = {
    "subject_markers": {
        "သည်": "Formal literary subject (narrative, epic scenes)",
        "က":   "Emphasis / contrast / colloquial subject",
        "မှာ": "Topic marker — 'as for...'",
        "rule": "သည် for narration; က for dialogue/emphasis",
    },

    "object_markers": {
        "ကို":    "Direct object",
        "သို့":   "Direction / toward",
        "အတွက်": "Purpose / for the sake of",
        "နဲ့":    "With / using / by means of",
        "မှ":     "From / since",
    },

    "location_markers": {
        "မှာ":  "Colloquial location — in dialogue, casual narration",
        "တွင်": "Formal literary location — in narration",
        "၌":    "Archaic/formal literary — for epic tone",
        "rule": "တွင်/၌ for battle/epic narration; မှာ for dialogue/daily",
    },

    "conjunctive_particles": {
        "ပြီး":    "Then / after doing (sequence)",
        "ပြီးတော့": "Then / and then (casual sequence)",
        "ကာ":     "While / simultaneously (literary)",
        "လျှင်":  "If / when (conditional, literary)",
        "ဆိုရင်": "If / when (conditional, casual)",
        "သော်":   "But / however (literary)",
        "ပေမဲ့":  "But / however (casual)",
    },

    "sentence_final_particles": {
        "တယ်":   "Neutral statement (casual narration, dialogue)",
        "သည်":   "Statement (literary narration)",
        "ပါတယ်": "Polite statement",
        "ဘူး":   "Negative",
        "မယ်":   "Future / intention",
        "ပြီ":    "Completion / already done",
        "တာပဲ":  "Emphasis / inevitability",
        "လဲ":    "Question — what/why/how (casual)",
        "လား":   "Yes/No question",
        "ပါ":    "Soft command / polite",
        "rule": (
            "NEVER mix literary (သည်) and casual (တယ်) within same character's dialogue.\n"
            "NEVER use Korean/Bengali/Arabic unicode accidentally:\n"
            "  WRONG: ဟန်ဆောင်နေ봐  (봐 = Korean!)\n"
            "  WRONG: গাঢ়အစိမ်းရောင်  (গাঢ় = Bengali!)\n"
            "  RIGHT: ဟန်ဆောင်နေတာ  /  အစိမ်းရောင်တောက်တောက်"
        ),
    },
}


# ===========================================================================
# SECTION 7: UNICODE SAFETY RULES
# Critical: prevent mixed-script errors from Chinese source processing
# ===========================================================================

UNICODE_SAFETY_RULES = {
    "banned_patterns": [
        {
            "pattern": "봐 / 봤자 / 해서 / 는데 (Korean Hangul)",
            "unicode_range": "U+AC00–U+D7FF",
            "reason": (
                "Korean characters injected by AI models into Myanmar text.\n"
                "Happens when model confuses Myanmar and Korean scripts."
            ),
            "correct": "တာ / ပေမဲ့ / နေ (context-dependent Myanmar particle)",
            "example": (
                "WRONG: ဟန်ဆောင်နေ봤자 အသုံးမဝင်ပါဘူး\n"
                "RIGHT: ဟန်ဆောင်နေတာ အသုံးမဝင်ပါဘူး"
            ),
        },
        {
            "pattern": "Bengali/Devanagari script (গাঢ় ক খ ड ह etc.)",
            "unicode_range": "U+0980–U+09FF (Bengali) | U+0900–U+097F (Devanagari)",
            "reason": (
                "Bengali script leaked into Myanmar output.\n"
                "Real case from Novel-v1 (Reverend Insanity translation):\n"
                "  WRONG: ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံ\n"
                "  গাঢ় = Bengali for 'deep/dark colour'\n"
                "  AI hallucinated Bengali script instead of Myanmar equivalent."
            ),
            "correct_vocab": {
                "deep/dark green":  "အစိမ်းရောင်တောက်တောက် / ရင့်သောအစိမ်းရောင်",
                "deep blue":        "နက်ပြာရောင် / ပြာနက်",
                "deep red":         "အနီတောက် / နီမြင့်",
                "deep black":       "မည်းနက်",
            },
            "example": (
                "WRONG: ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံ\n"
                "RIGHT: စုတ်ပြဲနေသာ အစိမ်းရောင်တောက်တောက် ဝတ်ရုံကြီး"
            ),
        },
        {
            "pattern": "؟ (Arabic question mark)",
            "unicode_range": "U+061F",
            "reason": "Arabic question mark used instead of standard ASCII",
            "correct": "? (U+003F ASCII question mark)",
            "example": (
                "WRONG: မင်း ဘယ်မှာ လဲ؟\n"
                "RIGHT: မင်း ဘယ်မှာ လဲ?"
            ),
        },
        {
            "pattern": "Chinese/CJK characters left in output",
            "unicode_range": "U+4E00–U+9FFF",
            "reason": "Source language leaked into Myanmar output",
            "correct": "Fully translate OR transliterate every Chinese character",
            "example": (
                "WRONG: 气 ကို သူ ဖြန့်ကျက်လိုက်တယ်\n"
                "RIGHT: ချီ ကို သူ ဖြန့်ကျက်လိုက်တယ်"
            ),
        },
    ],

    "myanmar_unicode_ranges": {
        "basic":      "U+1000–U+109F  — Myanmar basic (required)",
        "extended_a": "U+AA60–U+AA7F  — Myanmar Extended-A (valid, do NOT strip)",
        "extended_b": "U+A9E0–U+A9FF  — Myanmar Extended-B (valid, do NOT strip)",
    },

    "postprocessor_regex": {
        "wrong_regex": r"[^\u1000-\u109F\u0020-\u007E\n\r\t]+",
        "correct_regex": r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7FF\u0980-\u09FF\u0900-\u097F\u0600-\u06FF]+",
        "note": (
            "WRONG regex strips ALL non-Myanmar non-ASCII — deletes valid\n"
            "  Myanmar Extended-A/B + Bengali leakage WITHOUT distinction.\n"
            "CORRECT regex ONLY strips known bad script ranges:\n"
            "  CJK, Japanese, Korean, Bengali, Devanagari, Arabic."
        ),
    },

    "common_ai_mistakes": [
        "Korean Hangul (봐 봤자 해서) — U+AC00-U+D7FF",
        "Bengali script (গাঢ় ক) — U+0980-U+09FF",
        "Arabic punctuation (؟ ،) — use ? , instead",
        "Chinese chars left in output — must be fully translated",
        "Pinyin left untranslated: Fang Yuan, Wei Wuxian instead of ဖန်ယွမ်",
        "Starting output with '以下是翻译:' or '这是翻译:'",
        "Adding [注: ...] or translation notes inside Myanmar output",
    ],
}


# ===========================================================================
# SECTION 8: CULTURAL ADAPTATION RULES
# Chinese-specific cultural elements
# ===========================================================================

CULTURAL_RULES = {
    "chinese_idioms_chengyu": {
        "rule": (
            "成语 (chéngyǔ) — 4-character Chinese idioms:\n"
            "NEVER translate literally. Find Myanmar idiom equivalent.\n"
            "If no exact equivalent: express the MEANING naturally."
        ),
        "examples": [
            {
                "cn":      "一石二鸟 (one stone two birds)",
                "wrong_mm": "ကျောက်တစ်ခုနဲ့ ငှက်နှစ်ကောင်",
                "correct_mm": "ခေါင်းတစ်ခုနဲ့ နှစ်ချောင်းဆောင်",
            },
            {
                "cn":      "刻骨铭心 (carved into bones and heart)",
                "wrong_mm": "အရိုးနဲ့ နှလုံးထဲ ထွင်းထားသလို",
                "correct_mm": "အရိုးစွဲ ထင်ကျန်နေတဲ့",
                "note":    "Used in hatred/love contexts — becomes Myanmar intensity idiom",
            },
            {
                "cn":      "斩草除根 (cut grass and remove roots)",
                "wrong_mm": "မြက်ပင်ကို ဖြတ်ပြီး အမြစ်ကို ထုတ်ပစ်",
                "correct_mm": "အမြစ်ဖြတ် သုတ်သင်",
                "note":    "Used for exterminating family/enemies",
            },
            {
                "cn":      "血债血偿 (blood debt repaid with blood)",
                "wrong_mm": "သွေးကြွေး သွေးနဲ့ ချေပြန်ရတယ်",
                "correct_mm": "သွေးကြွေး သွေးနဲ့ ဆပ်ရမယ်",
            },
        ],
    },

    "honorifics_titles": {
        "rule": "Use Myanmar-appropriate honorifics based on age/status — not Chinese-literal",
        "mappings": {
            "师父 (Master/Teacher)":    "ဆရာ (general) / ဆရာကြီး (grand master)",
            "前辈 (Senior)":             "အကြီးသား / ဆရာကြီး",
            "师兄 (Senior disciple)":    "ဆရာနောင်",
            "师弟 (Junior disciple)":    "ဆရာညီ",
            "道友 (Fellow practitioner)": "လမ်းဖော် / လုပ်ဖော်",
            "公子 (Young lord)":         "မင်းသားလေး / ကိုကြီး",
            "小姐 (Miss)":               "မမ / ဒကာမ",
            "老祖 (Ancestor/Elder)":     "ဘိုးဘိုးကြီး / ဘြူးကြီး",
            "宗主 (Sect Master)":        "ဂိုဏ်းဆရာကြီး",
            "魔头 (Demon Lord)":         "မိစ္ဆာမင်း / နတ်ဆိုးကြီး",
        },
        "warning": (
            "Do NOT use ဦး/ဒေါ်/ကိုဦး for Chinese characters.\n"
            "These are Myanmar ethnic honorifics — culturally wrong for Chinese names."
        ),
    },

    "cultivation_terms": {
        "rule": (
            "Keep core cultivation terms consistent with glossary.\n"
            "Use Pinyin-based Myanmar transliteration + gloss on first appearance."
        ),
        "standard_terms": {
            "气/灵气 (Qi)":         "ချီ",
            "真气 (True Qi)":        "စစ်မှန်တဲ့ ချီ / စစ်ချီ",
            "内力 (Inner force)":    "အတွင်းအင်အား / ချီ",
            "金丹 (Golden Core)":    "ရွှေဘောလုံး",
            "元婴 (Nascent Soul)":   "ဝိညာဉ်ကလေး",
            "渡劫 (Tribulation)":    "ကြိတ်ကျော်ဒဏ်",
            "飞剑 (Flying Sword)":   "ပျံတိုက်",
            "宗门 (Sect)":           "ဂိုဏ်း (large) / အဖွဲ့ (small)",
            "丹药 (Pill/Elixir)":    "ဆေးဆံ / ကျင့်ဆေး",
            "法宝 (Treasure/Tool)":  "မှော်ပစ္စည်း",
            "境界 (Realm/Stage)":    "အဆင့် / နယ်မြေ",
            "突破 (Breakthrough)":   "အဆင့်တက် / ကျော်လွန်",
            "修炼 (Cultivate)":      "ကျင့်ကြံ",
        },
    },

    "measure_words": {
        "rule": "Use Myanmar classifiers (သနပ်) matching the noun",
        "chinese_to_myanmar": {
            "个 people/objects":    "ယောက် (people) / ခု (objects)",
            "条 long/strip":        "ချောင်း (long objects) / သွယ် (rivers, roads)",
            "把 handle/grip":       "ချောင်း (swords) / ထုပ် (bundle)",
            "匹 horses/cloth":      "ကောင် (horses) / ချပ် (cloth)",
            "颗 round/small":       "လုံး (pills, beads) / စေ့ (seeds)",
            "柄 bladed weapons":    "ချောင်း / လက် (swords, knives)",
            "位 honored person":    "ယောက် (respectful)",
            "名 named individual":  "ယောက်",
        },
    },

    "time_expressions": {
        "rule": "Chinese time expressions → Myanmar naturalized forms",
        "mappings": {
            "三百年前":   "လွန်ခဲ့တဲ့ နှစ်သုံးရာကျော်တုန်းက",
            "一瞬间":     "တစ်ချက်ချင်း / တစ်ကြိမ်ချင်း",
            "片刻":       "ခဏတာ / တစ်ဝက်",
            "须臾":       "မျက်ခြေမပြတ် / ချက်ချင်း",
            "从那时起":   "အဲ့ဒီအချိန်ကစပြီး / ထိုအချိန်မှ",
            "今日":       "ဒီနေ့",
        },
    },

    "poetic_sections": {
        "rule": (
            "Chinese poems (诗/词) in novels:\n"
            "Do NOT translate word-for-word.\n"
            "Adapt to Myanmar poetic form — maintain FEELING and IMAGERY.\n"
            "Rhythm > literal meaning."
        ),
    },
}


# ===========================================================================
# SECTION 9: VOCABULARY PRECISION
# Common wrong word choices — based on real translation error analysis
# Source: Reverend Insanity — Fang Yuan confrontation scene
# ===========================================================================

VOCABULARY_PRECISION = {

    "demon_evil_address": {
        "rule": "Chinese 魔/魔头/妖 → Myanmar depends on speaker's emotional state",
        "mappings": [
            {
                "context":   "Enemy address in anger/confrontation",
                "cn_term":   "魔 (demon)",
                "wrong_mm":  "နတ်ဆိုး (supernatural, neutral religious tone)",
                "correct_mm": "မိစ္ဆာကောင် (evil creature, contemptuous)",
                "reason":    "နတ်ဆိုး = mythological/neutral. မိစ္ဆာကောင် = hatred/contempt.",
            },
            {
                "context":   "Neutral narrative description",
                "cn_term":   "魔头",
                "correct_mm": "နတ်ဆိုးကြီး / မိစ္ဆာကြီး (acceptable neutral)",
            },
        ],
    },

    "purity_chastity": {
        "rule": "Chinese 纯洁/清白 in cultivation = chastity/innocence, NOT physical cleanliness",
        "mappings": [
            {
                "cn_term":   "纯洁/清白 (purity, chastity)",
                "wrong_mm":  "သန့်ရှင်းမှု (physical cleanliness — WRONG context)",
                "correct_mm": "ဖြူစင်မှု (moral purity, chastity, innocence)",
                "reason":    "သန့်ရှင်းမှု = hygienic clean. ဖြူစင်မှု = morally/spiritually pure.",
            },
        ],
    },

    "exterminate_family": {
        "rule": "Chinese 诛九族 (execute nine clans) → powerful Myanmar idiom",
        "mappings": [
            {
                "cn_term":   "诛九族 / 杀了我全家",
                "wrong_mm":  "မျိုးဆက်ကို ကိုးဆက်အထိ သေဒဏ်ပေးခဲ့တယ် (legalistic, flat)",
                "correct_mm": "မျိုးဆက် ကိုးဆက်လုံးကို အမြစ်ဖြတ် သုတ်သင်သွားတယ်",
                "breakdown": {
                    "အမြစ်ဖြတ်": "uproot completely",
                    "သုတ်သင်":   "sweep away / wipe out",
                },
                "reason":    "Combined idiom = total annihilation with righteous anger",
            },
        ],
    },

    "hatred_burning": {
        "rule": "Chinese 刻骨铭心的恨 / 如火燃烧地恨 → Myanmar bone-deep idiom",
        "mappings": [
            {
                "cn_term":   "如火一样的恨意 (burning passion of hatred)",
                "wrong_mm":  "မင်းကို မီးလို မုန်းတီးခဲ့တယ် (literal — awkward in Myanmar)",
                "correct_mm": "နင့်ကို အရိုးစွဲအောင် မုန်းသွားတာ",
                "alternative": "နင့်ကို သေသည့်တိုင် မမေ့နိုင်လောက်အောင် မုန်းတယ်",
                "reason":    "အရိုးစွဲ = bone-deep ingrained hatred — strongest Myanmar hate idiom",
            },
        ],
    },

    "death_declaration": {
        "rule": "Chinese 今天让你死 / 今日你必死 → Myanmar declarative fate statement",
        "mappings": [
            {
                "cn_term":   "今天，我要你死！",
                "wrong_mm":  "ဒီနေ့၊ မင်းသေစေချင်တယ် (flat wish — lacks drama)",
                "correct_options": [
                    "ဒီနေ့ နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ  (declarative fate)",
                    "ဒီနေ့ နင် ကြေးချေရမယ်            (pay the debt today)",
                    "ဒီနေ့ နင်သေရမယ်!                  (direct, powerful)",
                ],
                "reason":    "Myanmar confrontation speeches declare fate — not express wishes",
            },
        ],
    },

    "deep_color_without_bengali": {
        "rule": "Chinese 深色 (deep/dark color) → Myanmar color-depth words WITHOUT Bengali script",
        "mappings": [
            {
                "cn_term":   "深绿色 (deep green)",
                "wrong_mm":  "গাঢ়အစိမ်းရောင်  (গাঢ় = Bengali word — FORBIDDEN)",
                "correct_mm": "အစိမ်းရောင်တောက်တောက် / ရင့်သောအစိမ်းရောင်",
            },
            {"cn_term": "深蓝色", "correct_mm": "နက်ပြာရောင် / ပြာနက်"},
            {"cn_term": "深红色", "correct_mm": "အနီတောက် / နီမြင့်"},
            {"cn_term": "深黑色", "correct_mm": "မည်းနက် / နက်မည်း"},
        ],
    },

    "epic_motion_simile": {
        "rule": "Epic simile comparisons need dignified motion words — not trivial lightness",
        "mappings": [
            {
                "cn_term":   "在山风中像战旗一样飘动 (waved like a war flag in mountain wind)",
                "wrong_mm":  "စစ်ပွဲအလံလို ပေါ့ပေါ့ပါးပါး လွှဲယမ်းနေတယ်",
                "correct_mm": "စစ်အလံတစ်ခု ထောင်ထားသလို တစ်လူလူ လွင့်နေသည်",
                "breakdown": {
                    "တစ်လူလူ":         "wavering with dignity / floating proudly",
                    "ပေါ့ပေါ့ပါးပါး": "trivially light — WRONG for epic scene",
                },
            },
        ],
    },

    "narration_verb_choice": {
        "rule": "Describing character state in battle/epic scene → precise literary verbs",
        "mappings": [
            {
                "cn_term":   "穿着深绿色的长袍 (wearing deep green robes)",
                "wrong_mm":  "ဆုတ်ဖြဲနေတဲ့ ဝတ်ရုံတွေနဲ့ ရှိနေခဲ့တယ် (flat, vague)",
                "correct_mm": "အပေါ်မှ အောက်ထိ စုတ်ပြဲနေသာ ဝတ်ရုံကြီးကို ဝတ်ထားသည်",
            },
            {
                "cn_term":   "全身是血 (body covered in blood)",
                "wrong_mm":  "သွေးတွေနဲ့ ဖုံးလွှမ်းနေတယ် (casual register — wrong for epic)",
                "correct_mm": "သွေးများဖြင့် ပေရေနေသည် (literary ဖြင့် + သည်)",
            },
        ],
    },
}


# ===========================================================================
# SECTION 10: CONFRONTATION SPEECH PATTERN
# Real example: Reverend Insanity — Fang Yuan accusation scene
# CN original → bad MM translation → good MM translation with analysis
# ===========================================================================

CONFRONTATION_SPEECH_PATTERN = {

    "description": (
        "Confrontation speeches require ALL these rules applied simultaneously:\n"
        "  ① Enemy pronoun (你 → နင်)\n"
        "  ② Vivid tense (drop 了/ခဲ့)\n"
        "  ③ One accusation per sentence (split comma chains)\n"
        "  ④ Vocabulary precision (မိစ္ဆာကောင်, ဖြူစင်မှု, အမြစ်ဖြတ်)\n"
        "  ⑤ Myanmar idiom for hatred and death threat\n"
        "  ⑥ Literary သည် register for surrounding scene narration\n"
        "  ⑦ No Bengali/Korean/Arabic unicode leakage"
    ),

    "real_example": {
        "original_chinese": (
            '"妖孽！三百年前，你侮辱了我，夺走了我身体的纯洁，'
            '杀了我全家，诛我九族。从那时起，我对你恨之入骨！'
            '今日，我要你死！"\n\n'
            '......\n\n'
            '方源穿着一件破碎的深绿色长袍。他的头发蓬乱，全身是血。他环顾四周。\n\n'
            '血迹斑斑的长袍在山风中像战旗一样飘动。'
        ),

        "bad_translation": (
            '"နတ်ဆိုး၊ သုံးရာနှစ်လောက်က မင်းက ငါ့ကို စော်ကားခဲ့တယ်၊\n'
            'ငါ့ခန္ဓာကိုယ်ရဲ့ သန့်ရှင်းမှုကို ယူသွားခဲ့တယ်၊\n'
            'ငါ့မိသားစုတစ်ခုလုံးကို သတ်ခဲ့ပြီး ငါ့မျိုးဆက်ကို ကိုးဆက်အထိ\n'
            'သေဒဏ်ပေးခဲ့တယ်။ အဲဒီအချိန်ကစပြီး ငါ မင်းကို မီးလို မုန်းတီးခဲ့တယ်!\n'
            'ဒီနေ့၊ မင်းသေစေချင်တယ်!"\n'
            '...... ဖန်ယွမ်ဟာ ဆုတ်ဖြဲနေတဲ့ গাঢ়အစိမ်းရောင်ဝတ်ရုံတွေနဲ့ ရှိနေခဲ့တယ်။\n'
            'သူ့ဆံပင်တွေ ရှုပ်ပွနေပြီး သူ့ကိုယ်ခန္ဓာတစ်ခုလုံးက သွေးတွေနဲ့\n'
            'ဖုံးလွှမ်းနေတယ်။ သူပတ်ဝန်းကျင်ကို ကြည့်လိုက်တယ်။\n'
            'သွေးစွန်းနေတဲ့ ဝတ်ရုံတွေဟာ တောင်တန်းလေထဲမှာ စစ်ပွဲအလံလို\n'
            'ပေါ့ပေါ့ပါးပါး လွှဲယမ်းနေတယ်။'
        ),

        "good_translation": (
            '"မိစ္ဆာကောင် လွန်ခဲ့တဲ့ နှစ်သုံးရာလောက်တုန်းက\n'
            'နင် ငါ့ကို စော်ကားတယ်\n'
            'ငါ့ခန္ဓာရဲ့ ဖြူစင်မှုကို နင် ဖျက်ဆီးတယ်။\n'
            'ငါ့ရဲ့ မျိုးဆက် ကိုးဆက်လုံးကို အမြစ်ဖြတ် သုတ်သင်သွားတယ်။\n'
            'အဲ့ဒီအချိန်ကစပြီး ငါ နင့်ကို အရိုးစွဲအောင် မုန်းသွားတာ။\n'
            'ဒီနေ့ နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ"\n'
            'ဖန်ယွမ် သည် အပေါ်မှ အောက်ထိ စုတ်ပြဲနေသာ\n'
            'အစိမ်းရောင်တောက်တောက် ဝတ်ရုံကြီးကို ဝတ်ထားသည်။\n'
            'သူ့၏ ဆံပင်များမှာ ဖရိုဖရဲ ဖြစ်နေပြီး\n'
            'သူ့ တစ်ကိုယ်လုံးမှာ သွေးများဖြင့် ပေရေနေသည်။\n'
            'သွေးများဖြင့် ပေကြံနေသာ ဝတ်ရုံရှည်ကြီးမှာ\n'
            'တောင်လေပြထဲတွင် စစ်အလံတစ်ခု ထောင်ထားသလို တစ်လူလူ လွင့်နေသည်။'
        ),

        "error_analysis": {
            "error_1": {
                "cn":   "妖孽 → 你 (enemy address)",
                "issue": "Wrong vocabulary + wrong pronoun",
                "bad":   "နတ်ဆိုး + မင်း (neutral, no contempt)",
                "good":  "မိစ္ဆာကောင် + နင် (contemptuous + enemy pronoun)",
                "rule":  "妖孽 = contemptuous evil term → မိစ္ဆာကောင်; 你 to enemy → နင်",
            },
            "error_2": {
                "cn":   "纯洁 (purity/chastity)",
                "issue": "Wrong vocabulary — cleanliness instead of chastity",
                "bad":   "သန့်ရှင်းမှု (physical cleanliness)",
                "good":  "ဖြူစင်မှု (moral purity/chastity)",
                "rule":  "纯洁 in cultivation novel = chastity → ဖြူစင်မှု",
            },
            "error_3": {
                "cn":   "诛九族 (exterminate nine clans)",
                "issue": "Legalistic flat translation",
                "bad":   "မျိုးဆက်ကို ကိုးဆက်အထိ သေဒဏ်ပေးခဲ့တယ်",
                "good":  "မျိုးဆက် ကိုးဆက်လုံးကို အမြစ်ဖြတ် သုတ်သင်သွားတယ်",
                "rule":  "အမြစ်ဖြတ် + သုတ်သင် = powerful annihilation idiom",
            },
            "error_4": {
                "cn":   "Aspect marker 了 in accusation",
                "issue": "了 → ခဲ့ kills vivid intensity of accusation",
                "bad":   "စော်ကားခဲ့တယ် / ယူသွားခဲ့တယ် / သတ်ခဲ့ပြီး",
                "good":  "စော်ကားတယ် / ဖျက်ဆီးတယ် / သုတ်သင်သွားတယ်",
                "rule":  "Accusation speech: drop ခဲ့ for burning present-vivid intensity",
            },
            "error_5": {
                "cn":   "Comma-chained long sentence",
                "issue": "One long sentence — should be split",
                "bad":   "...စော်ကားခဲ့တယ်၊ ...ယူသွားခဲ့တယ်၊ ...သတ်ခဲ့ပြီး...",
                "good":  "One accusation per sentence, ending with ။",
                "rule":  "Confrontation: one accusation = one sentence",
            },
            "error_6": {
                "cn":   "恨之入骨 (hate to the bone)",
                "issue": "Literal English-influenced translation",
                "bad":   "မင်းကို မီးလို မုန်းတီးခဲ့တယ်",
                "good":  "နင့်ကို အရိုးစွဲအောင် မုန်းသွားတာ",
                "rule":  "恨之入骨 = bone-deep hatred → Myanmar idiom: အရိုးစွဲ",
            },
            "error_7": {
                "cn":   "要你死 (want you to die)",
                "issue": "Expressed as wish — should be declarative fate",
                "bad":   "မင်းသေစေချင်တယ်",
                "good":  "နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ",
                "rule":  "死 declaration = fate statement, not wish",
            },
            "error_8": {
                "cn":   "深绿色 (deep green)",
                "issue": "Bengali script গাঢ় leaked in",
                "bad":   "গাঢ়အစိမ်းရောင် (Bengali word gāḍha in Myanmar output)",
                "good":  "အစိမ်းရောင်တောက်တောက်",
                "rule":  "U+0980-U+09FF Bengali = FORBIDDEN in Myanmar output",
            },
            "error_9": {
                "cn":   "穿着...长袍 (wearing robes)",
                "issue": "Casual register for epic scene narration",
                "bad":   "ဝတ်ရုံတွေနဲ့ ရှိနေခဲ့တယ် (casual တယ်)",
                "good":  "ဝတ်ရုံကြီးကို ဝတ်ထားသည် (literary သည်)",
                "rule":  "Battle aftermath narration → literary သည် register",
            },
            "error_10": {
                "cn":   "像战旗一样飘动 (waved like war flag)",
                "issue": "Wrong motion word — trivial instead of dignified",
                "bad":   "ပေါ့ပေါ့ပါးပါး လွှဲယမ်းနေတယ်",
                "good":  "တစ်လူလူ လွင့်နေသည်",
                "rule":  "Epic simile → dignified motion တစ်လူလူ, literary register",
            },
        },
    },

    "confrontation_checklist": [
        "① 妖/魔: မိစ္ဆာကောင် (not နတ်ဆိုး) — contemptuous address",
        "② 你 to enemy: နင် (NEVER မင်း in enemy address)",
        "③ 了 aspect in accusation: drop ခဲ့ → vivid present intensity",
        "④ Comma-chain: split into one-accusation-per-sentence",
        "⑤ 纯洁/清白: ဖြူစင်မှု (not သန့်ရှင်းမှု)",
        "⑥ 诛九族: အမြစ်ဖြတ် သုတ်သင် (not သေဒဏ်ပေး)",
        "⑦ 恨之入骨: အရိုးစွဲအောင် မုန်း (not မီးလို မုန်း)",
        "⑧ 要你死: declarative fate — '...အသေသစ်ရမယ့် နေ့ပဲ'",
        "⑨ 深色: အစိမ်းရောင်တောက်တောက် (NO Bengali গাঢ়)",
        "⑩ Narration: literary သည်/ဖြင့်/တွင် (not casual တယ်/မှာ)",
        "⑪ Epic simile: တစ်လူလူ လွင့် (not ပေါ့ပေါ့ပါးပါး လွှဲ)",
    ],
}


# ===========================================================================
# SECTION 11: FORMATTING RULES
# ===========================================================================

FORMATTING_RULES = {
    "markdown_preservation": {
        "rule": "Preserve ALL original Markdown formatting exactly",
        "preserve": ["*italic*", "**bold**", "# headings", "> blockquotes", "---", "......"],
        "example": (
            "CN: 他*难以置信地*快\n"
            "MM: သူ *မယုံနိုင်လောက်အောင်* မြန်တယ်"
        ),
    },

    "chapter_heading_format": {
        "rule": "Chapter headings must follow exact two-line format",
        "format": (
            "# [Chapter Number]\n"
            "\n"
            "## [Chapter Title in Myanmar]"
        ),
        "example": (
            "# 第一章\n"
            "\n"
            "## ကျင့်ကြံသူငယ်"
        ),
    },

    "ellipsis": {
        "chinese": "……",
        "myanmar": "......  (convert to 6-dot ASCII ellipsis)",
        "rule": "Preserve ellipsis as ...... — do not drop",
    },

    "output_cleanliness": {
        "forbidden_prefix": [
            "以下是翻译：",
            "这是缅甸语翻译：",
            "ဘာသာပြန်ချက်:",
            "Here is the translation:",
        ],
        "forbidden_suffix": [
            "[注：...]",
            "[译者注：...]",
            "Translator's note:",
        ],
        "rule": "Output ONLY Myanmar text. Zero meta-commentary. Zero Chinese.",
    },

    "translators_notes": {
        "rule": (
            "Include 'Translator's Notes:' ONLY at END of chapter when:\n"
            "  - Cultural term needs Burmese reader explanation\n"
            "  - Wordplay (双关语) cannot be preserved\n"
            "  - Significant cultural adaptation was made"
        ),
    },
}


# ===========================================================================
# SECTION 12: PIPELINE INTEGRATION
# ===========================================================================

PIPELINE_SETTINGS = {
    "recommended_temperature": {
        "stage1_translation": 0.2,
        "stage2_rewrite":     0.4,
        "note": (
            "Stage 1 (literal accuracy):  0.2 — deterministic, complete\n"
            "Stage 2 (literary rewrite):  0.4 — natural variation\n"
            "NEVER below 0.15 — produces robotic, formal output\n"
            "NEVER above 0.6  — may drift from source meaning"
        ),
    },

    "recommended_models": {
        "stage1_chinese_to_burmese_direct": [
            "Hunyuan-MT-7B  — Chinese→Any, specifically trained",
            "qwen2.5:14b   — Best overall quality (needs 10GB RAM)",
            "qwen:7b        — Balanced quality/speed",
        ],
        "stage2_burmese_rewrite": [
            "SeaLLMs-v3-7B  — SEA language fluency",
            "Aya-expanse:8b — Multilingual rewrite",
            "qwen:7b        — Acceptable rewriter",
        ],
        "single_stage_fallback": [
            "translategemma — If RAM limited to 5GB",
        ],
    },

    "stage1_goal": (
        "COMPLETE and ACCURATE translation from Chinese.\n"
        "Literal is acceptable — style fixed in Stage 2.\n"
        "Priority: nothing skipped, nothing added, all names consistent."
    ),

    "stage2_goal": (
        "REWRITE for natural Myanmar literary quality.\n"
        "Fix: dialogue tags → လို့ format\n"
        "     pronouns → နင်/မင်း/ငါ correct register\n"
        "     accusation tense → drop ခဲ့ for vivid intensity\n"
        "     sentence rhythm → one idea per sentence in confrontation\n"
        "     vocabulary → မိစ္ဆာကောင်/ဖြူစင်မှု/အမြစ်ဖြတ် precision\n"
        "     emotion → physical sensation over abstract labels\n"
        "     narration register → သည် for epic, တယ် for casual\n"
        "DO NOT change story content."
    ),

    "chunk_size": {
        "recommended":  900,
        "max":          1000,
        "overlap":      150,
        "note": (
            "900 char chunks optimal for 7B models on 16GB RAM.\n"
            "150 char overlap ensures narrative continuity between chunks.\n"
            "Always split at paragraph boundaries — NEVER mid-sentence."
        ),
    },
}


# ===========================================================================
# SECTION 13: PROMPT BUILDERS
# ===========================================================================

def build_linguistic_context(
    scene_type: str = "narration",
    include_unicode_warning: bool = True,
    include_confrontation_rules: bool = False,
) -> str:
    """
    Generate a CH→MM linguistic rules prompt snippet for LLM injection.

    Args:
        scene_type:                 "narration" | "dialogue" | "action" | "confrontation"
        include_unicode_warning:    Include unicode safety block
        include_confrontation_rules: Include confrontation-specific rules

    Returns:
        str: Formatted prompt block for system prompt injection
    """

    scene_sentence_rule = {
        "narration":      "Medium sentences (10-18 words). Literary သည်/ဖြင့်/တွင် particles.",
        "dialogue":       "Short natural sentences. တယ်/ဘူး particles. Real speech rhythm.",
        "action":         "SHORT sentences (3-7 words). Fast rhythm. Active verbs.",
        "confrontation":  "SHORT, ONE ACCUSATION PER SENTENCE. Drop ခဲ့. Vivid intensity.",
    }.get(scene_type, "Adapt sentence length to match scene intensity.")

    unicode_block = ""
    if include_unicode_warning:
        unicode_block = """
UNICODE SAFETY (CRITICAL):
  ❌ Korean Hangul (봐 봤자): FORBIDDEN — U+AC00-U+D7FF
  ❌ Bengali script (গাঢ় ক): FORBIDDEN — U+0980-U+09FF
  ❌ Arabic ? (؟): use ? instead
  ❌ Chinese chars in output: FORBIDDEN
  ✅ Myanmar only: U+1000-U+109F, U+AA60-U+AA7F
  EXAMPLE WRONG: গাঢ়အစိမ်းရောင် → RIGHT: အစိမ်းရောင်တောက်တောက်
"""

    confrontation_block = ""
    if include_confrontation_rules:
        confrontation_block = """
CONFRONTATION SPEECH RULES:
  ① 妖/魔 enemy address → မိစ္ဆာကောင် (NOT နတ်ဆိုး)
  ② 你 to enemy        → နင် (NEVER မင်း)
  ③ 了 in accusation   → DROP ခဲ့ for vivid intensity
     WRONG: နင် ငါ့ကို စော်ကားခဲ့တယ်
     RIGHT: နင် ငါ့ကို စော်ကားတယ်
  ④ Comma chains       → split to ONE ACCUSATION PER SENTENCE
  ⑤ 纯洁              → ဖြူစင်မှု (NOT သန့်ရှင်းမှု)
  ⑥ 诛九族            → အမြစ်ဖြတ် သုတ်သင် (NOT သေဒဏ်ပေး)
  ⑦ 恨之入骨          → အရိုးစွဲအောင် မုန်း
  ⑧ 要你死            → နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ (declarative fate)
"""

    return f"""
[LINGUISTIC RULES — Chinese → Myanmar]

1. STRUCTURE: Chinese SVO → Myanmar SOV
   CN: 他(S) + 打(V) + 他(O)  →  MM: သူ(S) + သူ့ကို(O) + ထိုးလိုက်တယ်(V)
   Time phrases (三百年前) → SENTENCE START

2. ASPECT MARKERS:
   了 completion   → ပြီ / လိုက်တယ်
   着 ongoing      → နေတယ် / ထားတယ်
   过 experience   → ဖူးတယ် / ဖူးသည်

3. DIALOGUE FORMAT (MANDATORY):
   ✅ "..." လို့ [name] [verb]တယ်
   ❌ "..." ဟု [name] မေးမြန်းလေသည်

4. PRONOUNS:
   你 to enemy     → နင် (MANDATORY)
   你 to equal     → မင်း
   我 casual       → ငါ
   我 formal       → ကျွန်တော် / ကျွန်မ
   他/她           → သူ / သူမ

5. SENTENCE RHYTHM: {scene_sentence_rule}

6. EMOTIONS — PHYSICAL ONLY:
   ❌ သူ ဝမ်းနည်းတယ် (label)
   ✅ သူ့ ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလို (physical)

7. NARRATION REGISTER:
   Epic/battle/death → သည်/ဖြင့်/တွင် (literary)
   POV/casual/daily  → တယ်/နဲ့/မှာ  (conversational)
{unicode_block}{confrontation_block}
OUTPUT: Myanmar text ONLY. No Chinese. No notes. Preserve Markdown.
"""


def build_rewriter_prompt(
    glossary_text: str = "",
    context: str = "",
    scene_type: str = "narration",
) -> str:
    """
    Generate Stage 2 CH→MM literary rewriter system prompt.

    Args:
        glossary_text: Character/term glossary block
        context:       Previous chunk Burmese output (for continuity)
        scene_type:    "narration" | "confrontation" | "action" | "dialogue"

    Returns:
        str: Complete Stage 2 system prompt
    """

    context_section = ""
    if context:
        ctx = context[-500:] if len(context) > 500 else context
        context_section = f"\nPREVIOUS CONTEXT (for continuity):\n{ctx}\n---\n"

    glossary_section = ""
    if glossary_text:
        glossary_section = f"\n{glossary_text}\n"

    confrontation_extra = ""
    if scene_type == "confrontation":
        confrontation_extra = """
CONFRONTATION-SPECIFIC RULES:
  ① Enemy (妖/魔) → မိစ္ဆာကောင် (NOT နတ်ဆိုး)
  ② 你 to enemy  → နင် without exception
  ③ 了 aspect    → DROP ခဲ့ for all accusation verbs
  ④ Split every comma-chained accusation into separate sentences
  ⑤ 纯洁        → ဖြူစင်မှု (NOT သန့်ရှင်းမှု)
  ⑥ 诛九族      → အမြစ်ဖြတ် သုတ်သင်
  ⑦ Hatred idiom → အရိုးစွဲအောင် မုန်း
  ⑧ Death decl  → '...အသေသစ်ရမယ့် နေ့ပဲ' (fate, not wish)
  ⑨ Scene narration → literary သည်/ဖြင့်/တွင် (NOT casual တယ်)
  ⑩ Epic motion → တစ်လူလူ လွင့် (NOT ပေါ့ပေါ့ပါးပါး)
"""

    return f"""You are an expert Myanmar literary editor rewriting a rough Chinese→Myanmar translation.
{context_section}{glossary_section}
YOUR TASK: Rewrite into natural, literary Myanmar. NOT re-translating — REWRITING.

MANDATORY RULES:

RULE 1 — DIALOGUE TAGS
  ✅ "..." လို့ [character] [verb]တယ်
  ❌ "..." ဟု [character] မေးမြန်းလေသည် — NEVER USE

RULE 2 — PRONOUNS
  你 to enemy/hostile → နင် (NEVER မင်း)
  你 equal/casual    → မင်း
  我 casual          → ငါ
  我 formal          → ကျွန်တော်/ကျွန်မ

RULE 3 — ACCUSATION TENSE
  Drop ခဲ့ in anger/accusation speech for vivid intensity:
  WRONG: နင် ငါ့ကို ထိုးခဲ့တယ်
  RIGHT: နင် ငါ့ကို ထိုးတယ်

RULE 4 — SENTENCE STRUCTURE
  Confrontation: ONE accusation per sentence
  Action:        3-7 words max per sentence
  Narration:     10-18 words, flowing

RULE 5 — VOCABULARY PRECISION
  妖/魔 enemy address  → မိစ္ဆာကောင် (not နတ်ဆိုး)
  纯洁/清白 chastity   → ဖြူစင်မှု  (not သန့်ရှင်းမှု)
  诛九族 exterminate   → အမြစ်ဖြတ် သုတ်သင်
  恨之入骨 deep hatred → အရိုးစွဲအောင် မုန်း
  深色 deep color      → တောက်တောက် / ရင့် (NOT Bengali গাঢ়)

RULE 6 — EMOTIONS
  Physical sensation — NOT abstract label:
  WRONG: သူ ဝမ်းနည်းတယ်
  RIGHT: သူ့ ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလို ဖြစ်မိတယ်

RULE 7 — REGISTER
  Epic/battle narration → သည် / ဖြင့် / တွင် (literary)
  Dialogue / close-POV  → တယ် / နဲ့ / မှာ  (casual)
{confrontation_extra}
RULE 8 — UNICODE SAFETY
  ❌ Bengali (গাঢ়) U+0980-U+09FF: FORBIDDEN
  ❌ Korean  (봐)   U+AC00-U+D7FF: FORBIDDEN
  ❌ Arabic  (؟)   U+061F:         use ? instead
  ❌ Chinese chars in output:       FORBIDDEN

RULE 9 — CONTENT
  Do NOT add or remove any story events.
  Only improve language, register, vocabulary.

OUTPUT: ONLY the rewritten Myanmar text. Nothing else.
"""
