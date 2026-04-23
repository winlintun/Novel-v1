"""
Chinese-to-Myanmar Linguistic Transformation Rules
- SVO (Chinese) → SOV (Myanmar) structural conversion
- Particle usage guidelines
- Pronoun resolution based on hierarchy
"""

# SVO → SOV Conversion Patterns
SVO_TO_SOV_RULES = {
    "basic_structure": "Subject + Object + Verb (Myanmar) vs Subject + Verb + Object (Chinese)",
    "time_location": "Time/Location phrases move to sentence START in Myanmar",
    "negation": "Negation (မ/မဟုတ်) precedes verb in Myanmar",
    "question_particles": "Question markers (လား/နည်း) at sentence END",
}

# Myanmar Particle Guidelines
PARTICLE_GUIDELINES = {
    "subject_markers": ["သည်", "က", "မှာ"],  # Use based on emphasis
    "object_markers": ["ကို", "အား", "သို့"],  # ကို = direct object, သို့ = direction
    "location_markers": ["မှာ", "တွင်", "၌"],  # မှာ = colloquial, တွင် = formal
    "conjunctive": ["ပြီး", "ကာ", "လျှင်"],  # Sequence/condition markers
}

# Pronoun Resolution by Character Hierarchy
PRONOUN_HIERARCHY = {
    "superior_to_inferior": "မင်း/နင် (informal), သင် (formal)",
    "equal_status": "မင်း/ခင်ဗျား (male), မင်း/ရှင် (female)",
    "inferior_to_superior": "ကျွန်တော် (male speaker), ကျွန်မ (female speaker)",
    "third_person": "သူ (neutral), သူမ (female), သူတို့ (plural)",
}

# Cultural Adaptation Rules
CULTURAL_RULES = {
    "idioms": "Convert Chinese idioms to Myanmar equivalents (not literal)",
    "honorifics": "Add ဦး/ဒေါ်/ကုိ/မာံ based on age/status context",
    "cultivation_terms": "Keep Pinyin + Myanmar gloss: 金丹 (ကျင့်ဒန် - Golden Core)",
    "measure_words": "Use Myanmar classifiers: ဦး (animals), ယောက် (people), ခု (objects)",
}

def build_linguistic_context() -> str:
    """Generate prompt snippet with linguistic rules."""
    return f"""
[LINGUISTIC RULES - CN→MM]
1. STRUCTURE: Convert Chinese SVO → Myanmar SOV. Example:
   CN: 他(主) + 吃(动) + 饭(宾) → MM: သူ(သည်) + ထမင်း(ကို) + စား(သည်)

2. PARTICLES: Use appropriate markers:
   - Subject: သည် (formal), က (emphasis), မှာ (topic)
   - Object: ကို (direct), သို့ (direction), အတွက် (purpose)

3. PRONOUNS: Resolve based on hierarchy:
   - Superior speaking: Use ကျွန်တော်/ကျွန်မ
   - Equal status: Use မင်း/ခင်ဗျား
   - Referring to third person: Use သူ/သူမ

4. CULTURAL: 
   - Idioms: Adapt meaning, not literal translation
   - Names: Phonetic transliteration (李云龙 → လီယွန်လုံ)
   - Terms: Keep Pinyin + Myanmar: 元婴(ယွမ်ယင့် - Nascent Soul)

5. OUTPUT: ONLY Myanmar text. Zero explanations. Preserve Markdown.
"""
