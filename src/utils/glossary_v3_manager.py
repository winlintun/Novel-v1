"""
Glossary v3.0 Manager - Rich Metadata Support for CN→MM Translation
Compatible with Novel-v1 architecture. Non-breaking addition.
"""
from typing import Optional, Literal, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


# === ENUMS FOR TYPE SAFETY ===
class TermCategory(str, Enum):
    """Categories for glossary terms."""
    PERSON_CHARACTER = "person_character"
    CULTIVATION_CONCEPT = "cultivation_concept"
    ORGANIZATION = "organization"
    LOCATION = "location"
    ITEM_ARTIFACT = "item_artifact"
    TECHNIQUE_SKILL = "technique_skill"
    IDIOM_PROVERB = "idiom_proverb"
    TITLE_HONORIFIC = "title_honorific"
    OTHER = "other"


class TranslationRule(str, Enum):
    """Rules for how to translate a term."""
    TRANSLITERATE = "transliterate"  # Phonetic: 李→လီ
    TRANSLATE = "translate"          # Semantic: 宗门→ဂိုဏ်း
    HYBRID = "hybrid"                # Both: 金丹→ကျင့်ဒန် (Golden Core)
    KEEP_ORIGINAL = "keep_original"  # Never translate


class DialogueRegister(str, Enum):
    """Dialogue tone/register for character speech."""
    POLITE_FORMAL = "polite_formal"
    CASUAL_FRIENDLY = "casual_friendly"
    COLD_DISMISSIVE = "cold_dismissive"
    INTIMATE = "intimate"
    FIRST_PERSON_INTIMATE = "first_person_intimate"
    ARCHAIC_POETIC = "archaic_poetic"


# === CORE DATACLASS ===
@dataclass
class GlossaryTerm:
    """Rich glossary entry matching user's v3.0 JSON schema."""
    
    # --- Mandatory Fields ---
    id: str
    source_term: str
    target_term: str
    category: TermCategory
    translation_rule: TranslationRule
    priority: int  # 1 = highest
    
    # --- Alias Support ---
    aliases_cn: list[str] = field(default_factory=list)
    aliases_mm: list[str] = field(default_factory=list)
    
    # --- Translation Metadata ---
    pronunciation_guide: Optional[str] = None
    do_not_translate: bool = False
    usage_frequency: Literal["very_low", "low", "medium", "high", "very_high"] = "medium"
    semantic_tags: list[str] = field(default_factory=list)
    
    # --- Character/Entity State ---
    gender: Optional[Literal["male", "female", "none", "plural"]] = None
    status: dict = field(default_factory=lambda: {
        "active": True, "alive": None, "current_arc": None, "last_known_location": None
    })
    
    # --- Chapter Tracking ---
    chapter_range: dict = field(default_factory=lambda: {"first_seen": 1, "last_seen": None})
    
    # --- Relationships & Context ---
    relationships: list[dict] = field(default_factory=list)
    dialogue_register: Optional[dict[str, DialogueRegister]] = None
    exceptions: list[dict] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)
    
    # --- Validation ---
    verified: bool = False
    last_updated_chapter: Optional[int] = None
    
    # === METHODS ===
    
    def get_primary_key(self) -> str:
        """Unique lookup key: source_term + category."""
        return f"{self.source_term}:{self.category.value}"
    
    def get_all_source_variants(self) -> list[str]:
        """Return source_term + all CN aliases for regex matching."""
        return [self.source_term] + self.aliases_cn
    
    def get_target_for_context(
        self, 
        speaker_role: Optional[str] = None,
        listener_role: Optional[str] = None,
        narrative_context: Optional[str] = None
    ) -> str:
        """
        Apply exception rules to select appropriate Myanmar term.
        Fallback: target_term
        
        Args:
            speaker_role: Role of the speaker (e.g., 'enemy', 'friend')
            listener_role: Role of the listener
            narrative_context: Context type (e.g., 'formal_public', 'poetry')
            
        Returns:
            The appropriate Myanmar translation for the context
        """
        # Check exceptions in order
        for exc in self.exceptions:
            condition = exc.get("condition")
            
            if condition == "spoken_by_enemies" and speaker_role == "enemy":
                return exc["use_term"]
            elif condition == "formal_sect_announcement" and narrative_context == "formal_public":
                return exc["use_term"]
            elif condition == "possessive_own_sect" and narrative_context == "own_organization":
                return exc["use_term"]
            elif condition == "small_group" and narrative_context == "informal_small":
                return exc["use_term"]
            elif condition == "in_poetic_verse" and narrative_context == "poetry":
                return exc["use_term"]
        
        # Check dialogue register adaptation
        if self.dialogue_register and speaker_role and listener_role:
            register_key = f"{speaker_role}_to_{listener_role}"
            if register_key in self.dialogue_register:
                # Could apply tone modification here (future enhancement)
                pass
        
        return self.target_term
    
    def to_prompt_snippet(self, include_examples: bool = False) -> str:
        """
        Generate compact representation for AI prompt injection.
        
        Args:
            include_examples: Whether to include example sentences
            
        Returns:
            Formatted prompt snippet string
        """
        lines = [f"• {self.source_term} → {self.target_term} [{self.category.value}]"]
        
        if self.aliases_cn:
            lines.append(f"  CN aliases: {', '.join(self.aliases_cn[:3])}")
        if self.pronunciation_guide:
            lines.append(f"  Pronunciation: {self.pronunciation_guide}")
        if self.exceptions:
            lines.append(f"  Exceptions: {len(self.exceptions)} rules")
        if include_examples and self.examples:
            ex = self.examples[0]
            lines.append(f"  Example: {ex['cn_sentence']} → {ex['mm_sentence']}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert enum values to strings
        result['category'] = self.category.value
        result['translation_rule'] = self.translation_rule.value
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GlossaryTerm':
        """Create GlossaryTerm from dictionary."""
        # Convert string values to enums
        if 'category' in data and isinstance(data['category'], str):
            data['category'] = TermCategory(data['category'])
        if 'translation_rule' in data and isinstance(data['translation_rule'], str):
            data['translation_rule'] = TranslationRule(data['translation_rule'])
        return cls(**data)
