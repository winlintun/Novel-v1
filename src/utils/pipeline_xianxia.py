"""
Novel Translation Pipeline for Chinese Xianxia to Myanmar
Following the architecture from write_code.md
"""

import json
import re
import os
import logging
import time
from typing import Dict, List, Optional, Iterator, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import ollama

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PipelineConfig:
    """Configuration for the translation pipeline."""
    model_name: str = "qwen2.5:14b"
    fallback_model: str = "qwen:7b"
    chunk_size: int = 1200  # tokens
    chunk_overlap: int = 2  # sentences
    context_buffer_size: int = 5  # paragraphs
    max_retries: int = 3
    retry_delay: float = 2.0
    temperature: float = 0.3
    
    # File paths
    data_dir: str = "data_file"
    output_dir: str = "books"
    memory_dir: str = "memory_management"
    glossary_file: str = "glossary.json"
    character_profiles_file: str = "character_profiles.json"
    session_memory_file: str = "session_memory.json"
    extracted_data_file: str = "extracted_data.json"
    
    def __post_init__(self):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)


# ============================================================================
# STEP 1: SEMANTIC TEXT CHUNKING
# ============================================================================

class TextChunker:
    """
    Splits raw Chinese text into logical chunks with sliding window overlap.
    Preserves Markdown formatting and never splits mid-sentence.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.chapter_pattern = re.compile(r'第[\d零一二三四五六七八九十百千]+章.*')
        
    def split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs preserving chapter markers."""
        # Split on double newlines
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return paragraphs
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (Chinese ~ 1.5 chars per token, Myanmar ~ 2 chars)."""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.5)
    
    def split_into_chunks(self, paragraphs: List[str]) -> List[List[str]]:
        """
        Split paragraphs into chunks of ~chunk_size tokens.
        Uses sliding window overlap of last N sentences.
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for i, para in enumerate(paragraphs):
            para_tokens = self.estimate_tokens(para)
            
            # Check if adding this paragraph exceeds chunk size
            if current_tokens + para_tokens > self.config.chunk_size and current_chunk:
                # Finalize current chunk
                chunks.append(current_chunk)
                
                # Create overlap: take last N sentences from previous chunk
                overlap_text = ' '.join(current_chunk[-self.config.chunk_overlap:])
                current_chunk = [overlap_text] if overlap_text else []
                current_tokens = self.estimate_tokens(overlap_text) if overlap_text else 0
            
            current_chunk.append(para)
            current_tokens += para_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"Created {len(chunks)} chunks from {len(paragraphs)} paragraphs")
        return chunks
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Main entry point: chunk text and return structured data.
        Returns list of dicts with 'chunk_id', 'paragraphs', 'text', 'overlap_from_previous'.
        """
        paragraphs = self.split_into_paragraphs(text)
        chunks = self.split_into_chunks(paragraphs)
        
        results = []
        for i, chunk_paras in enumerate(chunks):
            chunk_text = '\n\n'.join(chunk_paras)
            overlap = ''
            if i > 0 and len(chunk_paras) > self.config.chunk_overlap:
                overlap = '\n\n'.join(chunk_paras[:self.config.chunk_overlap])
            
            results.append({
                'chunk_id': i + 1,
                'paragraphs': chunk_paras,
                'text': chunk_text,
                'overlap_from_previous': overlap,
                'token_estimate': self.estimate_tokens(chunk_text)
            })
        
        return results


# ============================================================================
# STEP 2: STRICT DATA EXTRACTION PIPELINE
# ============================================================================

EXTRACTION_SCHEMA = {
    "characters": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
    "cultivation_realms": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
    "sects_organizations": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
    "items_artifacts": [{"source_term": "", "description": "", "first_seen_chapter": 0}]
}

EXTRACTION_SYSTEM_PROMPT = """You are an expert Data Extraction AI specializing in Chinese Xianxia/Cultivation novels. Extract ONLY the following entities from the provided text chunk: characters, cultivation_realms, sects_organizations, items_artifacts.

CRITICAL RULES:
1. If a category has no data, return an empty list [].
2. DO NOT guess, invent, or hallucinate entities.
3. Output ONLY valid JSON matching the exact schema.
4. No explanations, no markdown code blocks, no conversational filler.

JSON Schema:
{
  "characters": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "cultivation_realms": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "sects_organizations": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "items_artifacts": [{"source_term": "", "description": "", "first_seen_chapter": 0}]
}"""


class DataExtractor:
    """
    Extracts structured data (characters, realms, sects, items) from text chunks.
    Uses strict validation and retry logic.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.model = config.model_name
        
    def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """Call Ollama with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    options={
                        "temperature": self.config.temperature,
                        "num_predict": 2048
                    }
                )
                return response['message']['content']
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise
        return ""
    
    def _clean_json_response(self, text: str) -> str:
        """Remove markdown code blocks if present."""
        # Remove ```json and ```
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text.strip()
    
    def _validate_extraction(self, data: Dict) -> Tuple[bool, str]:
        """Validate extraction result has all required keys."""
        required_keys = ["characters", "cultivation_realms", "sects_organizations", "items_artifacts"]
        
        for key in required_keys:
            if key not in data:
                return False, f"Missing required key: {key}"
            if not isinstance(data[key], list):
                return False, f"Key {key} must be a list"
        
        return True, "Valid"
    
    def extract_from_chunk(self, chunk_text: str, chapter_num: int = 1) -> Dict[str, List]:
        """
        Extract entities from a text chunk with validation and retries.
        Returns dict with 4 categories or empty lists on failure.
        """
        prompt = f"Extract entities from this Chinese Xianxia text:\n\n{chunk_text}"
        
        for attempt in range(self.config.max_retries):
            try:
                response = self._call_llm(prompt, EXTRACTION_SYSTEM_PROMPT)
                cleaned = self._clean_json_response(response)
                
                # Parse JSON
                data = json.loads(cleaned)
                
                # Validate structure
                is_valid, message = self._validate_extraction(data)
                if not is_valid:
                    logger.warning(f"Validation failed: {message}")
                    continue
                
                # Add chapter number to each entity
                for category in data:
                    for entity in data[category]:
                        entity['first_seen_chapter'] = chapter_num
                
                logger.info(f"Extracted: {len(data['characters'])} chars, {len(data['cultivation_realms'])} realms, "
                          f"{len(data['sects_organizations'])} sects, {len(data['items_artifacts'])} items")
                return data
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
            except Exception as e:
                logger.warning(f"Extraction error (attempt {attempt + 1}): {e}")
        
        # Return empty structure on failure
        logger.error("Extraction failed after all retries, returning empty structure")
        return {
            "characters": [],
            "cultivation_realms": [],
            "sects_organizations": [],
            "items_artifacts": []
        }


# ============================================================================
# STEP 3: 3-TIER MEMORY MANAGEMENT
# ============================================================================

class MemoryManager:
    """
    Manages 3-tier memory system:
    - Tier 1: Global Memory (glossary.json, character_profiles.json)
    - Tier 2: Chapter Context Memory (FIFO sliding window)
    - Tier 3: Session Memory (dynamic user corrections)
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.memory_dir = Path(config.memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Tier 1: Global Memory
        self.glossary: Dict[str, Any] = {}
        self.character_profiles: Dict[str, Any] = {}
        
        # Tier 2: Chapter Context (FIFO queue)
        self.context_buffer: List[str] = []
        
        # Tier 3: Session Memory
        self.session_rules: Dict[str, str] = {}
        
        # Load persistent data
        self._load_tier1_memory()
        self._load_session_memory()
    
    # -------------------------------------------------------------------------
    # TIER 1: Global Memory (Persistent)
    # -------------------------------------------------------------------------
    
    def _get_tier1_path(self, filename: str) -> Path:
        """Get full path for Tier 1 memory files."""
        return self.memory_dir / filename
    
    def _load_tier1_memory(self):
        """Load glossary and character profiles."""
        glossary_path = self._get_tier1_path(self.config.glossary_file)
        if glossary_path.exists():
            with open(glossary_path, 'r', encoding='utf-8') as f:
                self.glossary = json.load(f)
            logger.info(f"Loaded glossary with {len(self.glossary)} entries")
        
        profiles_path = self._get_tier1_path(self.config.character_profiles_file)
        if profiles_path.exists():
            with open(profiles_path, 'r', encoding='utf-8') as f:
                self.character_profiles = json.load(f)
            logger.info(f"Loaded {len(self.character_profiles)} character profiles")
    
    def _save_tier1_memory(self):
        """Save glossary and character profiles atomically."""
        glossary_path = self._get_tier1_path(self.config.glossary_file)
        temp_path = glossary_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(self.glossary, f, ensure_ascii=False, indent=2)
        temp_path.replace(glossary_path)
        
        profiles_path = self._get_tier1_path(self.config.character_profiles_file)
        temp_path = profiles_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(self.character_profiles, f, ensure_ascii=False, indent=2)
        temp_path.replace(profiles_path)
        
        logger.info("Tier 1 memory saved")
    
    def add_to_glossary(self, source_term: str, myanmar_term: str, category: str = "general"):
        """Add a new term to the glossary."""
        self.glossary[source_term] = {
            "myanmar": myanmar_term,
            "category": category,
            "added_at": datetime.now().isoformat()
        }
        self._save_tier1_memory()
        logger.info(f"Added to glossary: {source_term} -> {myanmar_term}")
    
    def add_character_profile(self, name: str, description: str, aliases: List[str] = None):
        """Add or update a character profile."""
        self.character_profiles[name] = {
            "description": description,
            "aliases": aliases or [],
            "updated_at": datetime.now().isoformat()
        }
        self._save_tier1_memory()
        logger.info(f"Updated character profile: {name}")
    
    def get_tier1_context(self) -> str:
        """Get formatted Tier 1 context for injection into prompts."""
        context_parts = []
        
        if self.glossary:
            context_parts.append("GLOSSARY (strictly use these terms):")
            for source, data in self.glossary.items():
                context_parts.append(f"  {source} = {data['myanmar']} ({data.get('category', 'general')})")
        
        if self.character_profiles:
            context_parts.append("\nCHARACTER PROFILES:")
            for name, data in self.character_profiles.items():
                context_parts.append(f"  {name}: {data['description']}")
                if data.get('aliases'):
                    context_parts.append(f"    Aliases: {', '.join(data['aliases'])}")
        
        return '\n'.join(context_parts) if context_parts else "No glossary data available."
    
    # -------------------------------------------------------------------------
    # TIER 2: Chapter Context (FIFO Sliding Window)
    # -------------------------------------------------------------------------
    
    def push_to_context_buffer(self, translated_paragraph: str):
        """Add translated paragraph to context buffer, maintaining FIFO."""
        self.context_buffer.append(translated_paragraph)
        if len(self.context_buffer) > self.config.context_buffer_size:
            self.context_buffer.pop(0)  # Remove oldest
        logger.debug(f"Context buffer: {len(self.context_buffer)}/{self.config.context_buffer_size}")
    
    def get_tier2_context(self) -> str:
        """Get formatted Tier 2 context (recent translations)."""
        if not self.context_buffer:
            return "No previous context."
        return "PREVIOUS CONTEXT:\n" + '\n'.join(self.context_buffer)
    
    def clear_context_buffer(self):
        """Clear the context buffer (e.g., at chapter end)."""
        self.context_buffer.clear()
        logger.info("Context buffer cleared")
    
    # -------------------------------------------------------------------------
    # TIER 3: Session Memory (Dynamic User Corrections)
    # -------------------------------------------------------------------------
    
    def _get_session_path(self) -> Path:
        return self._get_tier1_path(self.config.session_memory_file)
    
    def _load_session_memory(self):
        """Load session rules from disk."""
        session_path = self._get_session_path()
        if session_path.exists():
            with open(session_path, 'r', encoding='utf-8') as f:
                self.session_rules = json.load(f)
            logger.info(f"Loaded {len(self.session_rules)} session rules")
    
    def _save_session_memory(self):
        """Save session rules to disk."""
        session_path = self._get_session_path()
        temp_path = session_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(self.session_rules, f, ensure_ascii=False, indent=2)
        temp_path.replace(session_path)
    
    def add_session_rule(self, incorrect_term: str, correct_term: str, permanent: bool = False):
        """Add a correction rule. If permanent, also update Tier 1."""
        self.session_rules[incorrect_term] = correct_term
        self._save_session_memory()
        logger.info(f"Session rule added: {incorrect_term} -> {correct_term}")
        
        if permanent:
            self.add_to_glossary(incorrect_term, correct_term, category="user_correction")
            self._log_change(f"PERMANENT: {incorrect_term} -> {correct_term}")
    
    def get_tier3_context(self) -> str:
        """Get formatted Tier 3 context (session rules)."""
        if not self.session_rules:
            return "No session rules."
        return "CORRECTION RULES:\n" + '\n'.join([f"  {k} -> {v}" for k, v in self.session_rules.items()])
    
    def _log_change(self, message: str):
        """Log changes to session log file."""
        log_path = self.memory_dir / "session_log.txt"
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")


# ============================================================================
# STEP 4: CHAPTER-BY-CHAPTER TRANSLATION ENGINE
# ============================================================================

TRANSLATION_SYSTEM_PROMPT_TEMPLATE = """You are an expert Chinese-to-Myanmar literary translator specializing in Xianxia novels. Translate the following text naturally into Myanmar.

CRITICAL TRANSLATION RULES:
1. Myanmar SOV Structure: Use Subject-Object-Verb order. Break long Chinese sentences into readable Myanmar clauses.
2. Tone Control: Narrative = formal literary tone. Dialogue = natural spoken tone matching character status.
3. Glossary Compliance: STRICTLY use the provided Glossary for names/terms. Never transliterate unless specified.
4. Markdown Preservation: Preserve ALL Markdown formatting (#, **, *, etc.).
5. Pronoun Resolution: Use the Context Buffer for accurate pronoun resolution (he/she/it).
6. Literary Quality: Make it read like a Myanmar novel, not a translation. Use idioms where appropriate.

{TIER1_CONTEXT}

{TIER2_CONTEXT}

{TIER3_CONTEXT}

SOURCE TEXT TO TRANSLATE:
{SOURCE_TEXT}

OUTPUT ONLY THE TRANSLATED MYANMAR TEXT. No explanations, no notes, no original Chinese."""


class Translator:
    """
    Translates text from Chinese to Myanmar using Ollama.
    Integrates 3-tier memory system into prompts.
    """
    
    def __init__(self, config: PipelineConfig, memory_manager: MemoryManager):
        self.config = config
        self.memory = memory_manager
        self.model = config.model_name
        
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama with retry logic and error handling."""
        for attempt in range(self.config.max_retries):
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt}
                    ],
                    options={
                        "temperature": self.config.temperature,
                        "num_predict": 4096,
                        "top_p": 0.92,
                        "top_k": 50,
                        "repeat_penalty": 1.1
                    }
                )
                return response['message']['content']
            except Exception as e:
                logger.warning(f"Translation failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    # Try fallback model
                    if self.model != self.config.fallback_model:
                        logger.info(f"Trying fallback model: {self.config.fallback_model}")
                        self.model = self.config.fallback_model
                        return self._call_ollama(prompt)
                    raise
        return ""
    
    def translate_paragraph(self, paragraph: str) -> str:
        """
        Translate a single paragraph with full memory injection.
        """
        # Build prompt with all 3 tiers
        tier1 = self.memory.get_tier1_context()
        tier2 = self.memory.get_tier2_context()
        tier3 = self.memory.get_tier3_context()
        
        prompt = TRANSLATION_SYSTEM_PROMPT_TEMPLATE.format(
            TIER1_CONTEXT=tier1,
            TIER2_CONTEXT=tier2,
            TIER3_CONTEXT=tier3,
            SOURCE_TEXT=paragraph
        )
        
        translated = self._call_ollama(prompt)
        
        # Push to Tier 2 context buffer
        self.memory.push_to_context_buffer(translated)
        
        return translated
    
    def translate_chapter(self, chapter_text: str, chapter_num: int) -> str:
        """
        Translate an entire chapter paragraph by paragraph.
        Returns the full translated chapter.
        """
        logger.info(f"Starting translation of Chapter {chapter_num}")
        
        # Clear context buffer for new chapter
        self.memory.clear_context_buffer()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in chapter_text.split('\n\n') if p.strip()]
        
        translated_paragraphs = []
        for i, para in enumerate(paragraphs, 1):
            logger.info(f"Translating paragraph {i}/{len(paragraphs)}...")
            try:
                translated = self.translate_paragraph(para)
                translated_paragraphs.append(translated)
            except Exception as e:
                logger.error(f"Failed to translate paragraph {i}: {e}")
                translated_paragraphs.append(f"[TRANSLATION ERROR: {e}]")
        
        return '\n\n'.join(translated_paragraphs)


# ============================================================================
# HUMAN-IN-THE-LOOP (HITL) FEEDBACK LOOP
# ============================================================================

class HumanInTheLoop:
    """
    Handles user feedback after each chapter translation.
    Parses corrections and updates memory tiers.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        
    def prompt_for_feedback(self, chapter_num: int) -> bool:
        """
        Prompt user for feedback. Returns True to continue, False to stop.
        """
        print(f"\n{'='*60}")
        print(f"Chapter {chapter_num} translation complete!")
        print(f"{'='*60}")
        print("\nEnter feedback in format:")
        print("  CORRECT: [CN_TERM] -> [MM_TERM] | NOTE: [context]")
        print("  Or type 'PERMANENT: [CN_TERM] -> [MM_TERM]' to save to glossary")
        print("  Or type 'skip' to continue without changes")
        print("  Or type 'stop' to halt the pipeline")
        print("-" * 60)
        
        while True:
            feedback = input("> ").strip()
            
            if feedback.lower() == 'skip':
                return True
            
            if feedback.lower() == 'stop':
                return False
            
            if feedback.lower().startswith('permanent:'):
                # Parse permanent correction
                match = re.search(r'permanent:\s*(\S+)\s*->\s*(\S+)', feedback, re.IGNORECASE)
                if match:
                    cn_term, mm_term = match.groups()
                    self.memory.add_session_rule(cn_term, mm_term, permanent=True)
                    print(f"✓ Permanent rule added: {cn_term} -> {mm_term}")
                continue
            
            if feedback.lower().startswith('correct:'):
                # Parse correction
                match = re.search(r'correct:\s*(\S+)\s*->\s*(\S+)', feedback, re.IGNORECASE)
                if match:
                    cn_term, mm_term = match.groups()
                    self.memory.add_session_rule(cn_term, mm_term, permanent=False)
                    print(f"✓ Session rule added: {cn_term} -> {mm_term}")
                continue
            
            if feedback:
                print("Unrecognized format. Please use 'CORRECT:', 'PERMANENT:', 'skip', or 'stop'")
                continue
            
            # Empty input = continue
            return True


# ============================================================================
# PIPELINE ORCHESTRATOR
# ============================================================================

class PipelineOrchestrator:
    """
    Orchestrates the complete translation pipeline:
    1. Load novel text
    2. Chunk text
    3. Extract entities
    4. Translate chapter-by-chapter
    5. Handle HITL feedback
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.chunker = TextChunker(config)
        self.extractor = DataExtractor(config)
        self.memory = MemoryManager(config)
        self.translator = Translator(config, self.memory)
        self.hitl = HumanInTheLoop(self.memory)
        
    def load_novel_text(self, file_path: str) -> str:
        """Load novel text from file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def save_chapter(self, novel_name: str, chapter_num: int, content: str):
        """Save translated chapter to output directory."""
        output_dir = Path(self.config.output_dir) / novel_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{novel_name}_{chapter_num:03d}_mm.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Saved chapter to: {output_file}")
        return output_file
    
    def run_extraction_phase(self, chunks: List[Dict], chapter_num: int = 1) -> Dict:
        """
        Run data extraction on all chunks and merge results.
        """
        logger.info("Starting extraction phase...")
        
        all_data = {
            "characters": [],
            "cultivation_realms": [],
            "sects_organizations": [],
            "items_artifacts": []
        }
        
        for chunk in chunks:
            logger.info(f"Extracting from chunk {chunk['chunk_id']}/{len(chunks)}...")
            data = self.extractor.extract_from_chunk(chunk['text'], chapter_num)
            
            # Merge with existing data (deduplication by source_term)
            for category in all_data:
                existing_terms = {e['source_term'] for e in all_data[category]}
                for entity in data[category]:
                    if entity['source_term'] not in existing_terms:
                        all_data[category].append(entity)
        
        # Save extracted data
        extracted_path = Path(self.config.memory_dir) / self.config.extracted_data_file
        with open(extracted_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Extraction complete. Data saved to: {extracted_path}")
        return all_data
    
    def run_translation_phase(self, chunks: List[Dict], novel_name: str, chapter_num: int = 1) -> str:
        """
        Translate all chunks and assemble into a chapter.
        """
        logger.info(f"Starting translation phase for Chapter {chapter_num}...")
        
        # Combine all chunk texts into chapter
        full_text = '\n\n'.join([chunk['text'] for chunk in chunks])
        
        # Translate the chapter
        translated = self.translator.translate_chapter(full_text, chapter_num)
        
        # Save the chapter
        output_file = self.save_chapter(novel_name, chapter_num, translated)
        
        return str(output_file)
    
    def run_pipeline(self, novel_file: str, start_chapter: int = 1, max_chapters: int = None):
        """
        Run the complete pipeline on a novel file.
        
        Args:
            novel_file: Path to the novel text file
            start_chapter: Chapter number to start from
            max_chapters: Maximum chapters to process (None for all)
        """
        novel_name = Path(novel_file).stem
        logger.info(f"Starting pipeline for: {novel_name}")
        
        # Load text
        text = self.load_novel_text(novel_file)
        
        # For this implementation, we'll treat the entire text as Chapter 1
        # In a production system, you'd split by chapter markers first
        logger.info(f"Loaded {len(text)} characters")
        
        # Chunk the text
        chunks = self.chunker.chunk_text(text)
        
        # Phase 1: Extraction
        extracted_data = self.run_extraction_phase(chunks, start_chapter)
        
        # Display extracted entities
        print(f"\n{'='*60}")
        print("EXTRACTED ENTITIES:")
        print(f"{'='*60}")
        for category, entities in extracted_data.items():
            print(f"\n{category.upper()}:")
            for entity in entities[:10]:  # Show first 10
                print(f"  - {entity['source_term']}: {entity.get('description', 'N/A')[:50]}...")
        print(f"\n{'='*60}")
        
        # Phase 2: Translation
        output_file = self.run_translation_phase(chunks, novel_name, start_chapter)
        
        # Phase 3: HITL Feedback
        should_continue = self.hitl.prompt_for_feedback(start_chapter)
        
        if should_continue and (max_chapters is None or start_chapter < max_chapters):
            logger.info("Pipeline continuing to next chapter...")
        else:
            logger.info("Pipeline completed.")
        
        return output_file


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point for the translation pipeline."""
    print("=" * 60)
    print("Chinese Xianxia to Myanmar Translation Pipeline")
    print("=" * 60)
    print()
    
    # Initialize configuration
    config = PipelineConfig()
    
    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(config)
    
    # Find novel file
    novel_file = "data_file/古道仙鸿.txt"
    
    if not Path(novel_file).exists():
        print(f"Error: Novel file not found: {novel_file}")
        print("Please ensure the file exists at data_file/古道仙鸿.txt")
        return
    
    print(f"Found novel file: {novel_file}")
    print(f"Model: {config.model_name}")
    print(f"Output directory: {config.output_dir}")
    print(f"Memory directory: {config.memory_dir}")
    print()
    
    # Run pipeline
    try:
        output_file = orchestrator.run_pipeline(novel_file, start_chapter=1)
        print(f"\n{'='*60}")
        print("✓ Pipeline completed successfully!")
        print(f"✓ Output saved to: {output_file}")
        print(f"{'='*60}")
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user. Progress has been saved.")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\n✗ Pipeline failed: {e}")


if __name__ == "__main__":
    main()
