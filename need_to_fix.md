ာမည်တွေ (လူအမည်၊ နေရာအမည်၊ အရာဝတ္ထုအမည်) ကို ဖတ်လို့လွယ်ပြီး တစ်လျှောက်တည်းတူညီအောင် ထိန်းချင်ရင်
model တစ်ခုတည်းမဟုတ်ဘဲ systematic handling လုပ်ရမယ်။
Novel-v1 လို pipeline ထဲမှာ ဒီဟာကို module တစ်ခုလို သတ်မှတ်ပြီး ထိန်း သင့်တယ်။

၁။ အခြေခံ Principle

နာမည်အတွက် မူလစည်းကမ်း ၃ခု

Consistency (တစ်နေရာတည်း)
Pronounceable (ဖတ်လို့လွယ်)
Non-translation (မဘာသာပြန်ဘူး)

၂။ မလုပ်သင့်တာ
张三 → “ဇန်သုံး” (meaning translate) ❌
Phoenix City → “ဖီးနစ်မြို့” (sometimes OK, but inconsistent) ❌


၃။ လုပ်သင့်တဲ့နည်း (အရေးကြီး)
(A) Name Mapping System (must)

glossary_manager.py ကို upgrade လုပ်

{
  "张三": "ဇန်းဆန်း",
  "李四": "လီစီ",
  "青云宗": "ချင်းယွင်ဇုံ",
  "Phoenix City": "ဖီးနစ်မြို့"
}

Rules
	Chinese → phonetic Myanmar
	English → transliteration
	Cultivation terms → meaning translation OK

(B) Auto Detect + Replace

translator.py မထဲမှာ
translate မလုပ်ခင်
```
def apply_name_mapping(text, mapping):
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text
```
👉 model ကို မပေးခင် replace လုပ်

(C) Prompt Control
```
Do NOT translate names.
Use provided name mappings.
Keep all names consistent.
```
၄။ Chinese → Myanmar phonetic rule

တစ်ခါတည်း rule တစ်ခုထား

Chinese	Myanmar
张 (Zhang)	ဇန်း
李 (Li)	လီ
王 (Wang)	ဝမ်
陈 (Chen)	ချန်

👉 pinyin → Myanmar mapping table လုပ်ထားရင် ပိုကောင်း

၅။ Place Names
Option 1 (recommended)
青云宗 → ချင်းယွင်ဇုံ
天龙城 → ထျန်လုံမြို့
Option 2 (hybrid)
Phoenix City → ဖီးနစ်မြို့
Dragon Sect → ဒရဂွန်ဇုံ


၆။ Title / Cultivation Terms

ဒီဟာတွေ translate လုပ်ရမယ်

English	Myanmar
Spirit Energy	ဝိညာဉ်စွမ်းအား
Cultivation	ကျင့်ကြံခြင်း
Sect	ဇုံ


Final Best Practice

လုပ်ရမယ့်အရာ ၅ခု

name mapping file တစ်ခုလုပ်
translate မလုပ်ခင် replace
prompt ထဲ rule ထည့်
context ထဲ inject
pipeline ထဲ integrate
