# 📜 Skill: File Generation Handler
**ID:** `output.file_generator` | **Version:** `1.0`

## 🎯 Description
Persists finalized translation to disk with proper encoding, metadata, backups, and integrity checks.

## 📥 Input Schema
- `final_text`: Validated Myanmar markdown
- `metadata`: Novel name, chapter, timestamp, agent versions, glossary version
- `output_path`: `data/output/{novel}/`

## 📤 Output Schema
- `file_path`: Absolute path to saved `.md`
- `backup_created`: boolean
- `file_size_bytes`: integer
- `checksum`: MD5 hash of content

## ⚙️ Rules & Constraints
- 📝 **Encoding:** `utf-8-sig` (critical for Windows/Myanmar Unicode)
- 🔚 **Line Endings:** `unix` (`\n`)
- 📄 **Metadata Header:** HTML comment with translation metadata
- 💾 **Backup Strategy:** `rename_with_timestamp`
- ⚡ **Atomic Write:** `true` (temp file → rename)

## ✅ Validation & Behavior
- Verify Myanmar Unicode validity before save
- Check markdown syntax (warn-only)
- Ensure output directory exists
- Generate checksum for integrity tracking