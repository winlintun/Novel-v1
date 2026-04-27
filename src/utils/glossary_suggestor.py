"""
Glossary Suggestor with Confidence Scoring
Per need_fix.md Phase 2.1 - Auto-Glossary Suggestion with Confidence Scoring
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


class GlossarySuggestor:
    """Suggest new terms with confidence scores for human review."""
    
    def __init__(self, glossary_path: str = "data/glossary.json"):
        self.glossary_path = Path(glossary_path)
        self.existing_terms: Dict[str, str] = {}
        self._load_existing_terms()
    
    def _load_existing_terms(self) -> None:
        """Load existing glossary terms."""
        if self.glossary_path.exists():
            with open(self.glossary_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            for term in data.get("terms", []):
                source = term.get("source", "").lower()
                target = term.get("target", "")
                if source and target:
                    self.existing_terms[source] = target
    
    def suggest_term(
        self, 
        source_term: str, 
        context: str = "", 
        similar_terms: List[str] = None
    ) -> Dict[str, Any]:
        """
        Suggest a term translation with confidence score.
        
        Returns:
            {
                "source": "term",
                "suggested_target": "မြန်မာဘာသာ",
                "confidence": 0.92,  # 0.0-1.0
                "similar_terms": ["term1", "term2"],
                "usage_count": 15,
                "requires_review": True  # if confidence < 0.85
            }
        """
        source_lower = source_term.lower()
        
        # Check if term already exists (confidence = 1.0)
        if source_lower in self.existing_terms:
            return {
                "source": source_term,
                "target": self.existing_terms[source_lower],
                "confidence": 1.0,
                "similar_terms": [],
                "usage_count": 0,
                "requires_review": False,
                "status": "exists"
            }
        
        # Calculate confidence based on various factors
        confidence = 0.5  # Base confidence
        requires_review = True
        
        # Check for similar terms (partial match)
        similar = []
        for existing in self.existing_terms:
            if source_lower in existing or existing in source_lower:
                similar.append(existing)
        
        if similar:
            confidence = 0.75
            if similar_terms:
                confidence = 0.85
        
        # Check if term looks like a proper noun (lowercase = name/place)
        if source_term[0].isupper() and source_term.lower() == source_term:
            confidence += 0.1
        
        # Check for cultivation terms patterns
        cultivation_patterns = ["境界", "金丹", "元婴", "筑基", "功法", "灵气", "真元"]
        if any(p in source_term for p in cultivation_patterns):
            confidence += 0.05
            requires_review = True
        
        # Clamp confidence
        confidence = min(confidence, 0.95)
        
        # Determine if review is needed
        if confidence < 0.85:
            requires_review = True
        
        return {
            "source": source_term,
            "suggested_target": f"【?{source_term}?】",  # Placeholder until approved
            "confidence": round(confidence, 2),
            "similar_terms": similar[:5],
            "usage_count": 0,
            "requires_review": requires_review,
            "status": "pending"
        }
    
    def get_pending_suggestions(self) -> List[Dict[str, Any]]:
        """Get all pending term suggestions."""
        pending_path = Path("data/glossary_pending.json")
        if pending_path.exists():
            with open(pending_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            return data.get("pending_terms", [])
        return []
    
    def export_for_review(self, suggestions: List[Dict[str, Any]]) -> str:
        """Export suggestions as JSON string for UI display."""
        return json.dumps({"new_terms": suggestions}, ensure_ascii=False, indent=2)


def suggest_new_terms(
    text: str, 
    glossary_path: str = "data/glossary.json"
) -> List[Dict[str, Any]]:
    """
    Scan text for new terms and suggest translations.
    
    Returns list of term suggestions with confidence scores.
    """
    suggestor = GlossarySuggestor(glossary_path)
    
    # Extract potential terms (Chinese characters + common patterns)
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    terms = chinese_pattern.findall(text)
    
    # Get unique terms
    unique_terms = list(set(terms))
    
    suggestions = []
    for term in unique_terms[:50]:  # Limit to 50 terms
        suggestion = suggestor.suggest_term(term)
        if suggestion.get("status") == "pending":
            suggestions.append(suggestion)
    
    return suggestions