"""Extract candidate glossary terms from aligned sentence pairs."""

import logging
import re
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

EN_TERM_PATTERN = re.compile(r"\b[A-Z][a-z]*(?:\s+[A-Z][a-z]+)*\b")
STOP_WORDS = {
    "the", "a", "an", "this", "that", "these", "those",
    "he", "she", "it", "they", "we", "you",
    "his", "her", "its", "their", "our", "your",
    "is", "was", "were", "are", "be", "been",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might",
    "can", "could", "must", "need", "dare",
    "and", "or", "but", "nor", "yet", "so",
    "for", "with", "in", "on", "at", "to", "by",
    "of", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between",
    "not", "no", "nor", "neither", "never",
    "very", "quite", "rather", "somewhat",
    "one", "two", "three", "first", "second", "last",
    "then", "now", "here", "there", "where", "when",
    "all", "each", "every", "both", "few", "many", "much",
    "some", "any", "no", "nothing", "anything", "everything",
    "said", "says", "tell", "told", "speak", "spoke",
    "look", "see", "saw", "watch", "show",
    "go", "went", "come", "came", "take", "took",
    "make", "made", "know", "knew", "think", "thought",
    "want", "need", "let", "get", "got", "give", "gave",
    "find", "found", "keep", "kept", "leave", "left",
    "also", "even", "still", "just", "only",
}

COMMON_ENGLISH_WORDS = {
    "about", "above", "across", "actually", "almost", "along", "already",
    "although", "among", "another", "around", "because", "become", "becomes",
    "became", "been", "being", "behind", "below", "beneath", "beside",
    "besides", "between", "beyond", "cannot", "cause", "causes", "caused",
    "certain", "changes", "clearly", "closely", "coming", "could", "course",
    "current", "currently", "deeply", "definitely", "describe", "despite",
    "during", "easily", "either", "enough", "entire", "entirely", "especially",
    "eventually", "ever", "everyone", "everything", "exactly", "example",
    "expect", "expected", "explain", "extremely", "fairly", "finally",
    "follow", "follows", "following", "forever", "former", "further",
    "generally", "getting", "given", "giving", "greatly", "growing",
    "happened", "happening", "happens", "hardly", "having", "hence",
    "highly", "however", "imagine", "immediately", "important", "indeed",
    "inside", "instead", "itself", "keeping", "largely", "lately",
    "latter", "leading", "leaves", "less", "likely", "little",
    "living", "longer", "mainly", "making", "matter", "matters",
    "maybe", "meaning", "merely", "might", "mostly", "namely",
    "nearly", "necessarily", "neither", "nevertheless", "nonetheless",
    "normally", "nothing", "nowhere", "obviously", "often", "openly",
    "otherwise", "outside", "partly", "perfectly", "perhaps", "placed",
    "please", "poorly", "possible", "possibly", "precisely", "prefer",
    "prepared", "present", "prevent", "previous", "primarily", "probably",
    "promptly", "properly", "propose", "provides", "purely", "putting",
    "quickly", "quietly", "quite", "rather", "readily", "really",
    "recently", "regarding", "relatively", "remains", "repeatedly",
    "reportedly", "represent", "requires", "respect", "resulting",
    "reveals", "roughly", "seemingly", "sensible", "seriously", "several",
    "sharply", "shortly", "showing", "significantly", "similar",
    "similarly", "simply", "slightly", "slowly", "smoothly", "solely",
    "somehow", "someone", "something", "sometimes", "somewhat",
    "somewhere", "soon", "specifically", "strongly", "subject",
    "substantially", "successfully", "suddenly", "sufficiently",
    "suggests", "surely", "telling", "tending", "thoroughly",
    "though", "throughout", "together", "totally", "toward", "towards",
    "truly", "trying", "turned", "turning", "typically", "unless",
    "unlikely", "unusually", "usually", "utterly", "various",
    "virtually", "whatever", "whenever", "whereas", "wherever",
    "whether", "wholly", "widely", "willing", "within", "without",
    "wondering", "worse", "worst", "worth", "wrong", "younger",
}


def is_valid_english_term(term: str) -> bool:
    if not term or len(term) < 3:
        return False
    words = term.strip().split()
    if not words:
        return False
    for w in words:
        if w.lower() in STOP_WORDS or w.lower() in COMMON_ENGLISH_WORDS:
            if len(words) == 1:
                return False
    return True


class CandidateExtractor:
    """Extracts candidate glossary terms from aligned EN/MM sentence pairs."""

    def __init__(self, min_occurrences: int = 2, min_length: int = 3):
        self.min_occurrences = min_occurrences
        self.min_length = min_length

    def extract_candidates(self, aligned_pairs: list[tuple[str, str]]) -> list[dict]:
        term_counter: Counter = Counter()
        term_pairs: dict[str, list[str]] = {}

        for en_sent, my_sent in aligned_pairs:
            for match in EN_TERM_PATTERN.finditer(en_sent):
                term = match.group(0).strip()
                if not is_valid_english_term(term):
                    continue
                if len(term) < self.min_length:
                    continue
                term_counter[term] += 1
                if term not in term_pairs:
                    term_pairs[term] = []
                term_pairs[term].append(my_sent)

        candidates = []
        for term, count in term_counter.items():
            if count < self.min_occurrences:
                continue
            my_contexts = term_pairs.get(term, [])
            candidates.append({
                "source_term": term,
                "frequency": count,
                "contexts": my_contexts[:3],
                "category": self._guess_category(term),
                "confidence": min(0.9, 0.3 + count * 0.1),
            })

        candidates.sort(key=lambda c: c["frequency"], reverse=True)
        return candidates

    @staticmethod
    def _guess_category(term: str) -> str:
        term_lower = term.lower()
        title_keywords = ["master", "elder", "sister", "brother", "sir", "lord",
                          "lady", "prince", "princess", "king", "queen", "emperor",
                          "saint", "venerable", "honorable", "daoist", "patriarch"]
        location_keywords = ["city", "town", "village", "mountain", "river", "lake",
                            "sea", "ocean", "forest", "valley", "plain", "desert",
                            "realm", "world", "heaven", "hell", "pavilion", "hall",
                            "palace", "temple", "shrine", "island", "continent",
                            "kingdom", "empire", "province", "district", "gate"]
        technique_keywords = ["technique", "skill", "art", "method", "way", "dao",
                              "saber", "sword", "blade", "fist", "palm", "kick",
                              "step", "stance", "form", "style", "cultivation",
                              "refining", "alchemy", "array", "formation",
                              "spell", "magic", "divine", "secret", "ancient"]
        cultivation_keywords = ["cultivation", "realm", "stage", "level", "grade",
                                "rank", "class", "tier", "heavenly", "earthly",
                                "mortal", "immortal", "divine", "demonic",
                                "qi", "spirit", "soul", "essence", "power",
                                "energy", "force", "breakthrough", "enlightenment",
                                "tribulation", "karma", "fate", "destiny",
                                "way", "path", "truth", "law", "principle"]

        if any(kw in term_lower for kw in title_keywords):
            return "title_honorific"
        if any(kw in term_lower for kw in location_keywords):
            return "location"
        if any(kw in term_lower for kw in technique_keywords):
            return "technique"
        if any(kw in term_lower for kw in cultivation_keywords):
            return "cultivation_concept"
        return "general"


def deduplicate_candidates(
    candidates: list[dict],
    existing_sources: set[str],
    max_candidates: int = 200,
) -> list[dict]:
    seen: set[str] = set()
    result = []
    for c in candidates:
        source = c["source_term"].strip()
        if not source or source.lower() in existing_sources:
            continue
        if source.lower() in seen:
            continue
        seen.add(source.lower())
        result.append(c)
        if len(result) >= max_candidates:
            break
    return result
