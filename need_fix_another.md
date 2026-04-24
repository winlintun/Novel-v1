# Bug 1 — glossary မှာ Wrong Character (အဓိကပြဿနာ)
ဟောင်းတဲ့ glossary မှာ 李小龙 → လီရှောင်လုံ ဆိုတဲ့ test data ရှိနေတာကြောင့် model က 罗青 ကို ဘာသာပြန်တဲ့အခါ လီရှောင်လုံ ဆိုပြီး ပြောင်းသွားတယ်။ ခုဆိုရင် novel ရဲ့ အစစ်အမှန် characters 8 ဦး ထည့်ပြီးပြီ —

```json
{
  "glossary_version": "3.0",
  "novel_name": "古道仙鸿",
  "source_language": "Chinese",
  "target_language": "Myanmar",
  "last_updated": "2026-04-24",
  "total_terms": 8,
  "terms": [
    {
      "id": "term_001",
      "source_term": "罗青",
      "target_term": "လူချင်း",
      "aliases_cn": ["罗青", "小孩童", "放牛娃", "小施主"],
      "aliases_mm": ["လူချင်း"],
      "category": "person_character",
      "translation_rule": "transliterate",
      "pronunciation_guide": "လူ-ချင်း",
      "do_not_translate": true,
      "priority": 1,
      "gender": "male",
      "usage_frequency": "very_high",
      "semantic_tags": ["protagonist", "child", "poor", "male"],
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "dialogue_register": {
        "to_adults": "humble_informal",
        "inner_monologue": "first_person_casual"
      },
      "exceptions": [],
      "examples": [
        {
          "context_type": "narrative",
          "cn_sentence": "罗青，十二岁，小戎镇罗家村村民。",
          "mm_sentence": "လူချင်းသည် ဆယ်နှစ်ရှိသော ရွာသူကလေးတစ်ဦးဖြစ်သည်။"
        }
      ],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "罗青",
      "target": "လူချင်း"
    },
    {
      "id": "term_002",
      "source_term": "黄牛",
      "target_term": "နွားဖော်ကြီး",
      "aliases_cn": ["牛哥", "那头黄牛"],
      "aliases_mm": ["နွားဖော်ကြီး", "နွားကြီး"],
      "category": "character_animal",
      "translation_rule": "translate",
      "do_not_translate": false,
      "priority": 2,
      "gender": "male",
      "usage_frequency": "high",
      "semantic_tags": ["companion", "ox", "animal"],
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "exceptions": [
        {
          "condition": "罗青_addressing_affectionately",
          "use_term": "နွားကြီးဆေး",
          "note": "When 罗青 calls him '牛哥' (Ox Brother) in casual speech"
        }
      ],
      "examples": [
        {
          "context_type": "narrative",
          "cn_sentence": "身旁的那头黄牛依旧咀嚼着青草。",
          "mm_sentence": "ဘေးမှ နွားဖော်ကြီးက မြက်ကိုဆက်လက်ပွေ့နေသေးသည်။"
        }
      ],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "黄牛",
      "target": "နွားဖော်ကြီး"
    },
    {
      "id": "term_003",
      "source_term": "方宗主",
      "target_term": "ဖန်ဇုံပိုင်",
      "aliases_cn": ["中年汉子", "方宗主", "宗主"],
      "aliases_mm": ["ဖန်ဇုံပိုင်", "ဂိုဏ်းချုပ်ကြီး"],
      "category": "person_character",
      "translation_rule": "transliterate",
      "pronunciation_guide": "ဖန်-ဇုံ-ပိုင်",
      "do_not_translate": true,
      "priority": 1,
      "gender": "male",
      "usage_frequency": "high",
      "semantic_tags": ["antagonist", "sect_leader", "demon_sect", "powerful"],
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "dialogue_register": {
        "to_subordinates": "calm_authoritative",
        "to_enemies": "mocking_confident"
      },
      "exceptions": [],
      "examples": [],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "方宗主",
      "target": "ဖန်ဇုံပိုင်"
    },
    {
      "id": "term_004",
      "source_term": "古堂主",
      "target_term": "ဂူတန်မင်း",
      "aliases_cn": ["绝艳女子", "古堂主", "中年女子"],
      "aliases_mm": ["ဂူတန်မင်း", "လှပတဲ့မိန်းမ"],
      "category": "person_character",
      "translation_rule": "transliterate",
      "pronunciation_guide": "ဂူ-တန်-မင်း",
      "do_not_translate": true,
      "priority": 1,
      "gender": "female",
      "usage_frequency": "high",
      "semantic_tags": ["antagonist", "hall_master", "beautiful", "fierce", "female"],
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "dialogue_register": {
        "to_sect_leader": "respectful_formal",
        "to_enemies": "fierce_threatening"
      },
      "exceptions": [],
      "examples": [],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "古堂主",
      "target": "ဂူတန်မင်း"
    },
    {
      "id": "term_005",
      "source_term": "尊儿",
      "target_term": "ဇွန်ရဲ",
      "aliases_cn": ["孩童", "儿子"],
      "aliases_mm": ["ဇွန်ရဲ", "ကလေးသား"],
      "category": "person_character",
      "translation_rule": "transliterate",
      "pronunciation_guide": "ဇွန်-ရဲ",
      "do_not_translate": true,
      "priority": 2,
      "gender": "male",
      "usage_frequency": "medium",
      "semantic_tags": ["child", "demon_sect", "son_of_fang"],
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "dialogue_register": { "to_father": "casual_respectful" },
      "exceptions": [],
      "examples": [],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "尊儿",
      "target": "ဇွန်ရဲ"
    },
    {
      "id": "term_006",
      "source_term": "小戎镇",
      "target_term": "ရှောင်ရုံးမြို့",
      "aliases_cn": ["小戎山", "小戎镇"],
      "aliases_mm": ["ရှောင်ရုံးမြို့", "ရှောင်ရုံးတောင်"],
      "category": "place",
      "translation_rule": "transliterate",
      "do_not_translate": true,
      "priority": 2,
      "gender": "none",
      "usage_frequency": "medium",
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "exceptions": [],
      "examples": [],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "小戎镇",
      "target": "ရှောင်ရုံးမြို့"
    },
    {
      "id": "term_007",
      "source_term": "魔教",
      "target_term": "မာရ်ဂိုဏ်း",
      "aliases_cn": ["魔宗", "圣教", "魔教北宗"],
      "aliases_mm": ["မာရ်ဂိုဏ်း", "မာရ်နတ်ဂိုဏ်း"],
      "category": "organization",
      "translation_rule": "translate",
      "do_not_translate": false,
      "priority": 2,
      "usage_frequency": "medium",
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "exceptions": [
        {
          "condition": "self_reference_by_members",
          "use_term": "ကျွန်တော်တို့ သန့်ရှင်းသောဂိုဏ်း",
          "note": "Members call it '圣教' respectfully"
        }
      ],
      "examples": [],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "魔教",
      "target": "မာရ်ဂိုဏ်း"
    },
    {
      "id": "term_008",
      "source_term": "道士",
      "target_term": "တာအိုဆရာတော်",
      "aliases_cn": ["道长", "道人", "毛头小道士", "翩翩少年"],
      "aliases_mm": ["တာအိုဆရာတော်", "တာအိုဆရာ"],
      "category": "title_role",
      "translation_rule": "translate",
      "do_not_translate": false,
      "priority": 3,
      "usage_frequency": "medium",
      "chapter_range": { "first_seen": 1, "last_seen": null },
      "exceptions": [
        {
          "condition": "spoken_by_demon_sect_mockingly",
          "use_term": "ဆရာတော်ငပျော်",
          "note": "Demon sect members mock them"
        }
      ],
      "examples": [],
      "verified": true,
      "last_updated_chapter": 1,
      "source": "道士",
      "target": "တာအိုဆရာတော်"
    }
  ]
}
```
# Bug 2 — repeat_penalty မပါ (repetition loop ဖြစ်ရတဲ့ အကြောင်း)
`repeat_penalty` မပါတဲ့ Ollama call က output loop ဖြစ်သွားတာ — "လူထုအဖွဲ့ဝင်များ" ၅၀ ကြိမ်ထပ်သလို ဖြစ်သွားတယ်။ 1.3 ဆိုတာ aggressive penalty ဖြစ်လို့ ဒါနဲ့ loop ပပြောက်မယ်။
Bug 3 — chunk_size 3000 → 1200
7B model + 3000 char chunk = context overflow → repetition loop ထပ်ဖြစ်တယ်။ 1200 char ဆိုတာ 7B model အတွက် safe range ဖြစ်တယ်။
Files ဘယ်နေရာ ထားရမလဲ


```
data/glossary.json    ← glossary.json ကို replace လုပ်
src/main_fast.py      ← main_fast.py ကို replace လုပ်
```

