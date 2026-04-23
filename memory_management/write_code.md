Please implement the following 4-step workflow:

Step 1: Text Chunking Strategy
Implement a robust text processing logic before sending data to the LLM.

Semantic Chunking: Do not split text arbitrarily by character count. Split the text logically by paragraphs or chapter markers to ensure sentences and semantic meanings are not broken.

Optimal Chunk Size: Target approximately 1000 to 1500 tokens per chunk to prevent context window overflow while maintaining enough context for the LLM.

Overlap Technique: Implement a sliding window approach. When moving from Chunk A to Chunk B, include the last 2 to 3 sentences of Chunk A at the beginning of Chunk B. This prevents missing entities that might span across chunk boundaries.

Step 2: System Prompting
Create a strict system prompt for the Ollama API call. The prompt must enforce the following rules:

Role: You are an expert Data Extraction AI specializing in Chinese Xianxia/Cultivation novels.

Task: Extract specific entities from the provided text chunk. The target categories are:

Characters: Name and physical/status description.

Cultivation Realms: Names of cultivation stages or levels.

Sects/Organizations: Names of sects, clans, or factions.

Items/Artifacts: Magical tools, pills, or cauldrons.

Strict Constraint: If the provided text does not contain information for a specific category, you MUST leave that field entirely empty (e.g., an empty list []). You are strictly forbidden from guessing, inventing, or hallucinating data. Output ONLY the requested JSON format.

Step 3: Data Validation & Structure Target
Implement a validation step to ensure the LLM output is functional.

Data Structure Target: The LLM must return a strict JSON object with exactly these four root keys:

characters

cultivation_realms

sects_organizations

items_artifacts

Validation Logic: The code must catch JSON decode errors, strip any markdown formatting (like json ... ) that the LLM might output, and verify that the required keys exist before proceeding to the next step.

Step 4: Updating JSON (Data Integration)
Implement a file management system to update existing database files.

Action: Open the existing target JSON files (e.g., character_profiles.json, glossary_memory.json).

Append & Deduplicate: Compare the newly extracted data against the existing data. Append the new entries. If an entity already exists, skip it or append new context to it to avoid duplicates.

Save: Write the updated data back to the JSON files safely.