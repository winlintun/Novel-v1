#!/usr/bin/env python3
"""
Novel Translation Pipeline - Chinese Xianxia to Myanmar
Updated to work with chines_chapters/novel_name_XXX.md structure
Integrates with memory_management/ YAML and JSON files

Usage:
    python3 translate_chapters.py --novel 古道仙鸿 --chapter 1
    python3 translate_chapters.py --novel 古道仙鸿 --all
"""

import json
import yaml
import re
import os
import logging
import time
import argparse
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from collections import deque

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

# Try to import ollama
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not installed. Translation will not work.")


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================

class ConfigLoader:
    """Loads configuration from memory_management/config.yaml"""
    
    def __init__(self, config_path: str = "memory_management/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load YAML config file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8-sig') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            "project": {
                "name": "my_story_translation",
                "source_language": "zh-CN",
                "target_language": "my-MM",
                "novel_genre": "Xianxia/Cultivation"
            },
            "models": {
                "translator": "qwen2.5:14b",
                "editor": "qwen2.5:14b",
                "checker": "qwen:7b",
                "ollama_base_url": "http://localhost:11434"
            },
            "processing": {
                "chunk_size": 500,
                "overlap_size": 50,
                "max_retries": 3,
                "temperature": 0.3
            },
            "output": {
                "format": "markdown",
                "preserve_formatting": True,
                "add_translator_notes": False
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'models.translator')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value


# ============================================================================
# MEMORY MANAGEMENT - 3 TIER SYSTEM
# ============================================================================

class MemoryManager:
    """
    3-Tier Memory Management System:
    - Tier 1: Global Memory (glossary_memory.json, character_profiles.json)
    - Tier 2: Chapter Context (chapter_context_cache.json - FIFO sliding window)
    - Tier 3: Session Memory (human_feedback_queue.json - dynamic corrections)
    """
    
    def __init__(self, memory_dir: str = "memory_management"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Tier 1: Global Persistent Memory
        self.glossary: Dict = {"terms": []}
        self.character_profiles: Dict = {"characters": []}
        
        # Tier 2: Chapter Context (FIFO queue)
        self.context_cache: Dict = {}
        self.paragraph_buffer: deque = deque(maxlen=10)
        
        # Tier 3: Session/Fedback Memory
        self.feedback_queue: List = []
        self.session_rules: Dict = {}
        
        # Load all memory tiers
        self._load_all_memory()
    
    # -------------------------------------------------------------------------
    # TIER 1: Global Memory (Persistent JSON Files)
    # -------------------------------------------------------------------------
    
    def _load_all_memory(self):
        """Load all memory files."""
        self._load_glossary()
        self._load_character_profiles()
        self._load_context_cache()
        self._load_feedback_queue()
    
    def _load_glossary(self):
        """Load glossary_memory.json"""
        path = self.memory_dir / "glossary_memory.json"
        if path.exists():
            with open(path, 'r', encoding='utf-8-sig') as f:
                self.glossary = json.load(f)
            logger.info(f"Loaded glossary with {len(self.glossary.get('terms', []))} terms")
    
    def _save_glossary(self):
        """Save glossary_memory.json atomically"""
        path = self.memory_dir / "glossary_memory.json"
        temp_path = path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(self.glossary, f, ensure_ascii=False, indent=2)
        temp_path.replace(path)
    
    def _load_character_profiles(self):
        """Load character_profiles.json"""
        path = self.memory_dir / "character_profiles.json"
        if path.exists():
            with open(path, 'r', encoding='utf-8-sig') as f:
                self.character_profiles = json.load(f)
            logger.info(f"Loaded {len(self.character_profiles.get('characters', []))} character profiles")
    
    def _save_character_profiles(self):
        """Save character_profiles.json atomically"""
        path = self.memory_dir / "character_profiles.json"
        temp_path = path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(self.character_profiles, f, ensure_ascii=False, indent=2)
        temp_path.replace(path)
    
    def _load_context_cache(self):
        """Load chapter_context_cache.json"""
        path = self.memory_dir / "chapter_context_cache.json"
        if path.exists():
            with open(path, 'r', encoding='utf-8-sig') as f:
                self.context_cache = json.load(f)
    
    def _save_context_cache(self):
        """Save chapter_context_cache.json"""
        path = self.memory_dir / "chapter_context_cache.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.context_cache, f, ensure_ascii=False, indent=2)
    
    def _load_feedback_queue(self):
        """Load human_feedback_queue.json"""
        path = self.memory_dir / "human_feedback_queue.json"
        if path.exists():
            with open(path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                self.feedback_queue = data.get('feedback', [])
    
    def _save_feedback_queue(self):
        """Save human_feedback_queue.json"""
        path = self.memory_dir / "human_feedback_queue.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"feedback": self.feedback_queue}, f, ensure_ascii=False, indent=2)
    
    # -------------------------------------------------------------------------
    # Glossary Operations
    # -------------------------------------------------------------------------
    
    def add_glossary_term(self, source_term: str, target_term: str, category: str = "general", 
                         chapter: int = 0, aliases_cn: List[str] = None) -> bool:
        """Add a new term to glossary_memory.json"""
        existing_terms = {t['source_term'] for t in self.glossary.get('terms', [])}
        
        if source_term in existing_terms:
            logger.debug(f"Term already exists: {source_term}")
            return False
        
        new_term = {
            "id": f"term_{len(self.glossary.get('terms', [])) + 1:03d}",
            "source_term": source_term,
            "target_term": target_term,
            "aliases_cn": aliases_cn or [],
            "aliases_mm": [],
            "category": category,
            "translation_rule": "transliterate" if category == "person_character" else "translate",
            "priority": 1,
            "chapter_range": {
                "first_seen": chapter,
                "last_seen": chapter
            },
            "verified": False,
            "last_updated_chapter": chapter
        }
        
        self.glossary.setdefault('terms', []).append(new_term)
        self.glossary['total_terms'] = len(self.glossary['terms'])
        self.glossary['last_updated'] = datetime.now().isoformat()
        self._save_glossary()
        logger.info(f"Added glossary term: {source_term} -> {target_term}")
        return True
    
    def get_glossary_for_prompt(self) -> str:
        """Get formatted glossary for injection into prompts"""
        terms = self.glossary.get('terms', [])
        if not terms:
            return "No glossary entries yet."
        
        lines = ["GLOSSARY (Use these exact translations):"]
        for term in terms[:20]:  # Limit to first 20 for prompt size
            verified = "✓" if term.get('verified') else "○"
            lines.append(f"  [{verified}] {term['source_term']} = {term['target_term']} ({term.get('category', 'general')})")
        return '\n'.join(lines)
    
    # -------------------------------------------------------------------------
    # Character Profile Operations
    # -------------------------------------------------------------------------
    
    def add_character_profile(self, name_cn: str, name_mm: str = "", role: str = "Unknown",
                             description: str = "", chapter: int = 0) -> bool:
        """Add a new character to character_profiles.json"""
        existing = {c['name_cn'] for c in self.character_profiles.get('characters', [])}
        
        if name_cn in existing:
            return False
        
        new_char = {
            "id": f"char_{len(self.character_profiles.get('characters', [])) + 1:03d}",
            "name_cn": name_cn,
            "name_mm": name_mm or f"[TODO: translate {name_cn}]",
            "role": role,
            "description": description,
            "first_seen_chapter": chapter,
            "speech_style": {
                "formal": "polite",
                "casual": "direct"
            }
        }
        
        self.character_profiles.setdefault('characters', []).append(new_char)
        self._save_character_profiles()
        logger.info(f"Added character: {name_cn}")
        return True
    
    def get_character_context(self) -> str:
        """Get formatted character context for prompts"""
        chars = self.character_profiles.get('characters', [])
        if not chars:
            return "No character profiles yet."
        
        lines = ["CHARACTER PROFILES:"]
        for char in chars[:10]:
            lines.append(f"  {char['name_cn']} ({char['name_mm']}) - {char.get('role', 'Unknown')}")
            if char.get('description'):
                lines.append(f"    Desc: {char['description'][:50]}...")
        return '\n'.join(lines)
    
    # -------------------------------------------------------------------------
    # TIER 2: Chapter Context (FIFO Sliding Window)
    # -------------------------------------------------------------------------
    
    def update_chapter_context(self, chapter_num: int, summary: str = ""):
        """Update chapter_context_cache.json with current progress"""
        self.context_cache['current_chapter'] = chapter_num
        self.context_cache['last_translated_chapter'] = chapter_num - 1
        if summary:
            self.context_cache['summary_of_previous_chapters'] = summary
        self._save_context_cache()
    
    def push_paragraph_to_buffer(self, translated_text: str):
        """Add translated paragraph to FIFO buffer"""
        self.paragraph_buffer.append(translated_text)
    
    def get_context_buffer(self) -> str:
        """Get recent translations for context"""
        if not self.paragraph_buffer:
            return "No previous context."
        return "PREVIOUS CONTEXT (last few paragraphs):\n" + '\n'.join(list(self.paragraph_buffer)[-3:])
    
    # -------------------------------------------------------------------------
    # TIER 3: Session Memory (Feedback & Corrections)
    # -------------------------------------------------------------------------
    
    def add_feedback(self, incorrect: str, correct: str, chapter: int, permanent: bool = False):
        """Add correction to human_feedback_queue.json"""
        feedback = {
            "timestamp": datetime.now().isoformat(),
            "chapter": chapter,
            "incorrect": incorrect,
            "correct": correct,
            "permanent": permanent,
            "applied": False
        }
        
        self.feedback_queue.append(feedback)
        self._save_feedback_queue()
        
        # If permanent, also add to session rules
        if permanent:
            self.session_rules[incorrect] = correct
            # Also add to glossary if it looks like a name
            if len(incorrect) <= 4:  # Likely a name
                self.add_glossary_term(incorrect, correct, "person_character", chapter)
        
        logger.info(f"Feedback recorded: {incorrect} -> {correct}")
    
    def get_session_rules(self) -> str:
        """Get active session correction rules"""
        if not self.session_rules:
            return "No active correction rules."
        return "CORRECTION RULES:\n" + '\n'.join([f"  {k} -> {v}" for k, v in self.session_rules.items()])
    
    def get_all_memory_for_prompt(self) -> Dict[str, str]:
        """Get all 3 tiers formatted for prompt injection"""
        return {
            "tier1_glossary": self.get_glossary_for_prompt(),
            "tier1_characters": self.get_character_context(),
            "tier2_buffer": self.get_context_buffer(),
            "tier3_rules": self.get_session_rules(),
            "chapter_summary": self.context_cache.get('summary_of_previous_chapters', '')
        }


# ============================================================================
# TEXT CHUNKING
# ============================================================================

class TextChunker:
    """Splits Chinese text into logical chunks with sliding window overlap"""
    
    def __init__(self, chunk_size: int = 500, overlap_size: int = 50):
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for Chinese text"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        return int(chinese_chars * 1.5)
    
    def split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return paragraphs
    
    def create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """Create chunks with sliding window overlap"""
        paragraphs = self.split_into_paragraphs(text)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for i, para in enumerate(paragraphs):
            para_size = self.estimate_tokens(para)
            
            if current_size + para_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'chunk_id': len(chunks) + 1,
                    'text': chunk_text,
                    'size': current_size
                })
                
                # Create overlap for next chunk
                overlap_text = '\n'.join(current_chunk[-2:]) if len(current_chunk) >= 2 else current_chunk[-1]
                current_chunk = [overlap_text, para]
                current_size = self.estimate_tokens(overlap_text) + para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                'chunk_id': len(chunks) + 1,
                'text': '\n\n'.join(current_chunk),
                'size': current_size
            })
        
        return chunks


# ============================================================================
# DATA EXTRACTION
# ============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are an expert Data Extraction AI specializing in Chinese Xianxia/Cultivation novels. 

Extract ONLY the following entities from the provided text chunk:
- characters: People, protagonists, antagonists, NPCs
- cultivation_realms: Cultivation stages, levels, realms
- sects_organizations: Sects, clans, organizations, factions
- items_artifacts: Treasures, pills, weapons, artifacts

CRITICAL RULES:
1. If a category has no data, return an empty list [].
2. DO NOT guess, invent, or hallucinate entities.
3. Output ONLY valid JSON matching the exact schema below.
4. No explanations, no markdown code blocks, no conversational filler.

JSON Schema:
{
  "characters": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "cultivation_realms": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "sects_organizations": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "items_artifacts": [{"source_term": "", "description": "", "first_seen_chapter": 0}]
}"""


class DataExtractor:
    """Extracts entities from text using LLM"""
    
    def __init__(self, model: str = "qwen2.5:14b", max_retries: int = 3):
        self.model = model
        self.max_retries = max_retries
    
    def _call_ollama(self, prompt: str, system_prompt: str) -> str:
        """Call Ollama with retry logic"""
        if not OLLAMA_AVAILABLE:
            raise RuntimeError("Ollama not installed. Run: pip install ollama")
        
        for attempt in range(self.max_retries):
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    options={"temperature": 0.1, "num_predict": 2048}
                )
                return response['message']['content']
            except Exception as e:
                logger.warning(f"Extraction attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
        return ""
    
    def _clean_json(self, text: str) -> str:
        """Remove markdown code blocks from JSON response"""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text.strip()
    
    def _validate_extraction(self, data: Dict) -> Tuple[bool, str]:
        """Validate extraction has all required keys"""
        required = ["characters", "cultivation_realms", "sects_organizations", "items_artifacts"]
        for key in required:
            if key not in data:
                return False, f"Missing key: {key}"
            if not isinstance(data[key], list):
                return False, f"Key {key} must be a list"
        return True, "Valid"
    
    def extract_from_chunk(self, chunk_text: str, chapter_num: int = 1) -> Dict:
        """Extract entities from a text chunk"""
        prompt = f"Extract entities from this Chinese text:\n\n{chunk_text}"
        
        for attempt in range(self.max_retries):
            try:
                response = self._call_ollama(prompt, EXTRACTION_SYSTEM_PROMPT)
                cleaned = self._clean_json(response)
                
                data = json.loads(cleaned)
                is_valid, message = self._validate_extraction(data)
                
                if not is_valid:
                    logger.warning(f"Validation failed: {message}")
                    continue
                
                # Add chapter number
                for category in data:
                    for entity in data[category]:
                        entity['first_seen_chapter'] = chapter_num
                
                return data
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}")
            except Exception as e:
                logger.warning(f"Extraction error: {e}")
        
        # Return empty structure on failure
        return {
            "characters": [],
            "cultivation_realms": [],
            "sects_organizations": [],
            "items_artifacts": []
        }


# ============================================================================
# TRANSLATION ENGINE
# ============================================================================

TRANSLATION_PROMPT_TEMPLATE = """You are an expert Chinese-to-Myanmar literary translator specializing in Xianxia novels.

CRITICAL RULES:
1. Myanmar SOV Structure: Use Subject-Object-Verb order
2. Tone: Narrative = formal literary tone, Dialogue = natural spoken tone
3. Glossary Compliance: Use EXACT translations from glossary
4. Markdown: Preserve all formatting (#, **, *, etc.)
5. Natural Flow: Make it read like a Myanmar novel, not a translation

{GLOSSARY}

{CHARACTERS}

{CONTEXT}

{CORRECTIONS}

SOURCE TEXT TO TRANSLATE:
{SOURCE_TEXT}

OUTPUT ONLY THE TRANSLATED MYANMAR TEXT."""


class Translator:
    """Translates Chinese text to Myanmar using Ollama"""
    
    def __init__(self, model: str = "qwen2.5:14b", temperature: float = 0.3, max_retries: int = 3):
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama with retry logic"""
        if not OLLAMA_AVAILABLE:
            raise RuntimeError("Ollama not installed. Run: pip install ollama")
        
        for attempt in range(self.max_retries):
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": self.temperature,
                        "num_predict": 4096,
                        "top_p": 0.92,
                        "top_k": 50,
                        "repeat_penalty": 1.1
                    }
                )
                return response['message']['content']
            except Exception as e:
                logger.warning(f"Translation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
        return ""
    
    def translate_paragraph(self, paragraph: str, memory: MemoryManager) -> str:
        """Translate a single paragraph with full memory context"""
        mem_data = memory.get_all_memory_for_prompt()
        
        prompt = TRANSLATION_PROMPT_TEMPLATE.format(
            GLOSSARY=mem_data['tier1_glossary'],
            CHARACTERS=mem_data['tier1_characters'],
            CONTEXT=mem_data['tier2_buffer'],
            CORRECTIONS=mem_data['tier3_rules'],
            SOURCE_TEXT=paragraph
        )
        
        translated = self._call_ollama(prompt)
        
        # Push to context buffer
        memory.push_paragraph_to_buffer(translated)
        
        return translated
    
    def translate_chapter(self, chapter_text: str, chapter_num: int, memory: MemoryManager) -> str:
        """Translate entire chapter paragraph by paragraph"""
        logger.info(f"Translating Chapter {chapter_num}")
        
        # Clear context buffer for new chapter
        memory.paragraph_buffer.clear()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in chapter_text.split('\n\n') if p.strip()]
        
        translated = []
        for i, para in enumerate(paragraphs, 1):
            logger.info(f"  Paragraph {i}/{len(paragraphs)}...")
            try:
                result = self.translate_paragraph(para, memory)
                translated.append(result)
            except Exception as e:
                logger.error(f"Failed to translate paragraph {i}: {e}")
                translated.append(f"[ERROR: {e}]")
        
        return '\n\n'.join(translated)


# ============================================================================
# PIPELINE ORCHESTRATOR
# ============================================================================

class PipelineOrchestrator:
    """Orchestrates the complete translation workflow"""
    
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.memory = MemoryManager()
        self.chunker = TextChunker(
            chunk_size=config.get('processing.chunk_size', 500),
            overlap_size=config.get('processing.overlap_size', 50)
        )
        self.extractor = DataExtractor(
            model=config.get('models.translator', 'qwen2.5:14b'),
            max_retries=config.get('processing.max_retries', 3)
        )
        self.translator = Translator(
            model=config.get('models.translator', 'qwen2.5:14b'),
            temperature=config.get('processing.temperature', 0.3)
        )
    
    def load_prompt_template(self) -> str:
        """Load prompt template from memory_management/prompts.yaml"""
        prompt_path = Path("memory_management/prompts.yaml")
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8-sig') as f:
                data = yaml.safe_load(f)
                return data.get('translator_prompt', TRANSLATION_PROMPT_TEMPLATE)
        return TRANSLATION_PROMPT_TEMPLATE
    
    def get_chapter_files(self, novel_name: str) -> List[Path]:
        """Get sorted list of chapter files for a novel"""
        chapters_dir = Path("chines_chapters") / novel_name
        if not chapters_dir.exists():
            logger.error(f"Chapters directory not found: {chapters_dir}")
            return []
        
        files = sorted(chapters_dir.glob(f"{novel_name}_*.md"))
        return files
    
    def load_chapter(self, file_path: Path) -> str:
        """Load chapter content from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def save_translation(self, novel_name: str, chapter_num: int, content: str) -> Path:
        """Save translated chapter"""
        output_dir = Path("books") / novel_name / "chapters"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{novel_name}_{chapter_num:03d}_mm.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Saved translation: {output_file}")
        return output_file
    
    def extract_and_update_memory(self, chapter_text: str, chapter_num: int):
        """Extract entities from chapter and update memory files"""
        logger.info(f"Extracting entities from Chapter {chapter_num}...")
        
        # Create chunks
        chunks = self.chunker.create_chunks(chapter_text)
        
        all_data = {
            "characters": [],
            "cultivation_realms": [],
            "sects_organizations": [],
            "items_artifacts": []
        }
        
        # Extract from each chunk
        for chunk in chunks[:5]:  # Limit to first 5 chunks for speed
            data = self.extractor.extract_from_chunk(chunk['text'], chapter_num)
            
            # Merge results
            for category in all_data:
                existing = {e['source_term'] for e in all_data[category]}
                for entity in data[category]:
                    if entity['source_term'] not in existing:
                        all_data[category].append(entity)
        
        # Update memory with extracted entities
        new_chars = 0
        for char in all_data['characters']:
            if self.memory.add_character_profile(
                name_cn=char['source_term'],
                description=char.get('description', ''),
                chapter=chapter_num
            ):
                new_chars += 1
        
        logger.info(f"Extraction complete. Found {len(all_data['characters'])} characters, "
                   f"{len(all_data['cultivation_realms'])} realms, "
                   f"{len(all_data['sects_organizations'])} sects, "
                   f"{len(all_data['items_artifacts'])} items.")
        logger.info(f"Added {new_chars} new character profiles.")
        
        return all_data
    
    def process_chapter(self, novel_name: str, chapter_num: int, chapter_file: Path = None) -> Path:
        """Process a single chapter: extract + translate + save"""
        
        # Get chapter file
        if chapter_file is None:
            files = self.get_chapter_files(novel_name)
            if chapter_num > len(files):
                raise ValueError(f"Chapter {chapter_num} not found. Only {len(files)} chapters available.")
            chapter_file = files[chapter_num - 1]
        
        logger.info(f"Processing {chapter_file.name}")
        
        # Load chapter
        chapter_text = self.load_chapter(chapter_file)
        
        # Step 1: Extract entities and update memory
        extracted = self.extract_and_update_memory(chapter_text, chapter_num)
        
        # Step 2: Translate
        translated = self.translator.translate_chapter(chapter_text, chapter_num, self.memory)
        
        # Step 3: Save
        output_file = self.save_translation(novel_name, chapter_num, translated)
        
        # Step 4: Update chapter context
        self.memory.update_chapter_context(chapter_num, f"Chapter {chapter_num} translated.")
        
        return output_file
    
    def process_all_chapters(self, novel_name: str, start: int = 1):
        """Process all chapters sequentially"""
        files = self.get_chapter_files(novel_name)
        total = len(files)
        
        logger.info(f"Found {total} chapters for {novel_name}")
        
        for i in range(start - 1, total):
            chapter_num = i + 1
            print(f"\n{'='*60}")
            print(f"Chapter {chapter_num}/{total}")
            print(f"{'='*60}")
            
            try:
                output = self.process_chapter(novel_name, chapter_num, files[i])
                print(f"✓ Saved: {output}")
                
                # Ask for feedback
                self._prompt_feedback(chapter_num)
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Progress saved.")
                break
            except Exception as e:
                logger.error(f"Failed to process chapter {chapter_num}: {e}")
                print(f"✗ Error: {e}")
                continue
    
    def _prompt_feedback(self, chapter_num: int):
        """Prompt user for feedback"""
        print(f"\n{'-'*60}")
        print("Feedback options:")
        print("  CORRECT: [CN_TERM] -> [MM_TERM]  (session correction)")
        print("  PERMANENT: [CN_TERM] -> [MM_TERM]  (save to glossary)")
        print("  skip  (continue to next chapter)")
        print("  stop  (halt pipeline)")
        print(f"{'-'*60}")
        
        while True:
            try:
                feedback = input("> ").strip()
                
                if feedback.lower() == 'skip':
                    return
                
                if feedback.lower() == 'stop':
                    raise KeyboardInterrupt()
                
                # Parse permanent correction
                perm_match = re.match(r'permanent:\s*(\S+)\s*->\s*(\S+)', feedback, re.I)
                if perm_match:
                    cn, mm = perm_match.groups()
                    self.memory.add_feedback(cn, mm, chapter_num, permanent=True)
                    print(f"✓ Permanent: {cn} -> {mm}")
                    continue
                
                # Parse session correction
                corr_match = re.match(r'correct:\s*(\S+)\s*->\s*(\S+)', feedback, re.I)
                if corr_match:
                    cn, mm = corr_match.groups()
                    self.memory.add_feedback(cn, mm, chapter_num, permanent=False)
                    print(f"✓ Session: {cn} -> {mm}")
                    continue
                
                if feedback:
                    print("Unknown format. Use: CORRECT:, PERMANENT:, skip, or stop")
                    continue
                
                return  # Empty input = continue
                
            except EOFError:
                return  # Non-interactive mode


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Chinese to Myanmar Novel Translation Pipeline")
    parser.add_argument("--novel", required=True, help="Novel name (e.g., 古道仙鸿)")
    parser.add_argument("--chapter", type=int, help="Specific chapter number to translate")
    parser.add_argument("--all", action="store_true", help="Translate all chapters")
    parser.add_argument("--start", type=int, default=1, help="Start from chapter (default: 1)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Chinese Xianxia to Myanmar Translation Pipeline")
    print("=" * 60)
    print(f"Novel: {args.novel}")
    
    # Load configuration
    config = ConfigLoader()
    print(f"Model: {config.get('models.translator', 'qwen2.5:14b')}")
    
    # Initialize pipeline
    pipeline = PipelineOrchestrator(config)
    
    # Run pipeline
    try:
        if args.chapter:
            # Translate single chapter
            output = pipeline.process_chapter(args.novel, args.chapter)
            print(f"\n✓ Translation saved: {output}")
        elif args.all:
            # Translate all chapters
            pipeline.process_all_chapters(args.novel, args.start)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print("\n\nPipeline stopped by user.")
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    main()
