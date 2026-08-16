# MCP_SERVICE.md — Model Context Protocol Service Specification
## Myanmar Novel Translation Pipeline

**Version:** 1.0  
**Protocol:** Model Context Protocol (MCP)  
**Transport:** stdio (local) / HTTP SSE (remote, optional)  
**Server Name:** `myanmar-novel-translator`

---

## 1. Service Overview

The MCP Service exposes the entire translation pipeline as a set of **tools**, **resources**, and **prompts** that any MCP-compatible client (Claude Desktop, custom IDE, etc.) can invoke.

This enables:
- **Decoupled architecture**: Clients don't need to know pipeline internals
- **Multi-client support**: Web UI, CLI, and IDE extensions can all use the same backend
- **Standardized discovery**: Clients auto-discover available capabilities

---

## 2. Exposed Tools

### 2.1 `read_source_chapter`
Read and parse an English source markdown file.
```json
{
  "name": "read_source_chapter",
  "description": "Parse source markdown into structured paragraphs and metadata",
  "inputSchema": {
    "type": "object",
    "properties": {
      "file_path": {"type": "string", "description": "Absolute path to chapter-en-XXXX.md"}
    },
    "required": ["file_path"]
  },
  "returns": {
    "chapter_id": "string",
    "metadata": {"title": "string", "novel": "string", "chapter": "string"},
    "paragraphs": ["string"],
    "word_count": "integer"
  }
}
```

### 2.2 `chunk_chapter`
Split chapter into scene-based chunks.
```json
{
  "name": "chunk_chapter",
  "description": "Split chapter into overlapping scene-based chunks",
  "inputSchema": {
    "type": "object",
    "properties": {
      "chapter_id": {"type": "string"},
      "max_paragraphs": {"type": "integer", "default": 5},
      "overlap": {"type": "integer", "default": 1}
    },
    "required": ["chapter_id"]
  },
  "returns": {
    "chunks": [
      {
        "chunk_id": "string",
        "sequence": "integer",
        "type": "dialogue-heavy | narration-heavy | mixed",
        "source_text": "string",
        "speakers": ["string"]
      }
    ]
  }
}
```

### 2.3 `translate_chunk`
Translate a single chunk via Ollama.
```json
{
  "name": "translate_chunk",
  "description": "Translate one chunk using context, glossary, and few-shot examples",
  "inputSchema": {
    "type": "object",
    "properties": {
      "chunk_id": {"type": "string"},
      "model": {"type": "string", "default": "gemma2:9b"},
      "temperature": {"type": "number", "default": 0.3},
      "use_two_pass": {"type": "boolean", "default": true}
    },
    "required": ["chunk_id"]
  },
  "returns": {
    "chunk_id": "string",
    "translated_text": "string",
    "tokens_used": "integer",
    "duration_ms": "integer",
    "micro_prompts_used": ["analyze", "draft", "polish", "normalize"]
  }
}
```

### 2.4 `verify_chunk`
Run Verifier subagent on a translated chunk.
```json
{
  "name": "verify_chunk",
  "description": "Check chunk for glossary violations, voice inconsistencies, and format errors",
  "inputSchema": {
    "type": "object",
    "properties": {
      "chunk_id": {"type": "string"},
      "auto_fix": {"type": "boolean", "default": true}
    },
    "required": ["chunk_id"]
  },
  "returns": {
    "chunk_id": "string",
    "pass": "boolean",
    "issues": [
      {
        "severity": "critical | warning | info",
        "category": "glossary | voice | format | coherence",
        "message": "string",
        "suggestion": "string",
        "line_number": "integer"
      }
    ],
    "corrected_text": "string | null",
    "glossary_hits": "integer"
  }
}
```

### 2.5 `audit_chapter`
Run Auditor subagent on full chapter.
```json
{
  "name": "audit_chapter",
  "description": "Perform holistic literary review of complete translated chapter",
  "inputSchema": {
    "type": "object",
    "properties": {
      "chapter_id": {"type": "string"},
      "compare_with_human": {"type": "boolean", "default": false}
    },
    "required": ["chapter_id"]
  },
  "returns": {
    "chapter_id": "string",
    "grade": "A | B | C | D | F",
    "scores": {
      "flow": "integer (0-100)",
      "voice_consistency": "integer (0-100)",
      "terminology": "integer (0-100)",
      "literary_quality": "integer (0-100)"
    },
    "verdict": "pass | fail | needs_human_review",
    "suggestions": ["string"],
    "comparison": {
      "human_reference_similarity": "float | null",
      "key_differences": ["string"]
    }
  }
}
```

### 2.6 `commit_translation`
Save approved translation to disk.
```json
{
  "name": "commit_translation",
  "description": "Write final markdown, metadata, and audit report to output directory",
  "inputSchema": {
    "type": "object",
    "properties": {
      "chapter_id": {"type": "string"},
      "output_dir": {"type": "string"}
    },
    "required": ["chapter_id"]
  },
  "returns": {
    "output_files": ["string"],
    "committed_at": "ISO8601"
  }
}
```

### 2.7 `get_glossary`
Retrieve current glossary.
```json
{
  "name": "get_glossary",
  "description": "Get all glossary entries or filter by category",
  "inputSchema": {
    "type": "object",
    "properties": {
      "category": {"type": "string", "enum": ["character", "place", "item", "concept", "honorific"]},
      "locked_only": {"type": "boolean", "default": false}
    }
  },
  "returns": {
    "version": "string",
    "entries": [GlossaryEntry]
  }
}
```

### 2.8 `update_glossary`
Add or update a glossary entry.
```json
{
  "name": "update_glossary",
  "description": "Add new term or update existing. Requires manual review if locked term changed.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "term": {"type": "string"},
      "translation": {"type": "string"},
      "category": {"type": "string"},
      "locked": {"type": "boolean", "default": false}
    },
    "required": ["term", "translation", "category"]
  },
  "returns": {
    "success": "boolean",
    "requires_human_review": "boolean",
    "previous_value": "object | null"
  }
}
```

### 2.9 `get_context_buffer`
Get context for a specific scene.
```json
{
  "name": "get_context_buffer",
  "description": "Retrieve context buffer for given chapter and scene",
  "inputSchema": {
    "type": "object",
    "properties": {
      "chapter_id": {"type": "string"},
      "scene_id": {"type": "string"}
    },
    "required": ["chapter_id", "scene_id"]
  },
  "returns": {
    "chapter_id": "string",
    "scene_id": "string",
    "preceding_summary": "string",
    "active_speakers": "object",
    "preceding_chunks": ["object"]
  }
}
```

### 2.10 `run_pipeline`
Run full pipeline for a chapter.
```json
{
  "name": "run_pipeline",
  "description": "End-to-end translation: chunk → translate → verify → audit → commit",
  "inputSchema": {
    "type": "object",
    "properties": {
      "file_path": {"type": "string"},
      "output_dir": {"type": "string"},
      "model": {"type": "string", "default": "gemma2:9b"},
      "skip_audit": {"type": "boolean", "default": false}
    },
    "required": ["file_path"]
  },
  "returns": {
    "chapter_id": "string",
    "state": "APPROVED | NEEDS_HUMAN | FAILED",
    "output_files": ["string"],
    "audit_grade": "string | null",
    "duration_seconds": "integer"
  }
}
```

---

## 3. Exposed Resources

Resources are read-only data exposed via URI.

### 3.1 `glossary://terms`
Returns full glossary as JSON.

### 3.2 `glossary://terms/{category}`
Returns glossary entries filtered by category.

### 3.3 `context://{chapter_id}/{scene_id}`
Returns context buffer for specific scene.

### 3.4 `style://guide`
Returns style guide rules and examples.

### 3.5 `rules://all`
Returns all enforcement rules.

### 3.6 `prompts://translate`
Returns the current translation system prompt template.

### 3.7 `prompts://verify`
Returns the verifier system prompt template.

### 3.8 `prompts://audit`
Returns the auditor system prompt template.

---

## 4. Exposed Prompts

Prompts are reusable templates clients can invoke.

### 4.1 `prompts://translate-chunk`
Full micro-prompt assembly for chunk translation. Dynamically injects glossary, context, and few-shots.

### 4.2 `prompts://verify-chunk`
Verifier prompt with rules checklist.

### 4.3 `prompts://audit-chapter`
Auditor prompt for holistic review.

### 4.4 `prompts://fix-glossary`
Specialized prompt for correcting glossary violations in a given text.

---

## 5. Error Codes (MCP Standard)

| Code | Meaning | When Returned |
|------|---------|---------------|
| `-32600` | Invalid Request | Malformed JSON |
| `-32601` | Method Not Found | Unknown tool name |
| `-32602` | Invalid Params | Missing required field |
| `-32603` | Internal Error | Pipeline crash |
| `-32000` | Server Error | Ollama unreachable |
| `-32001` | Translation Error | LLM returned garbage |
| `-32002` | Verification Failed | Chunk failed verification and auto-fix |
| `-32003` | Audit Failed | Grade < C |

---

## 6. Security & Rate Limiting

### 6.1 Local-Only Default
By default, the MCP server binds to `127.0.0.1` only. No external network access.

### 6.2 Rate Limiting
- `translate_chunk`: Max 1 call per 5 seconds (prevents GPU overload)
- `run_pipeline`: Max 1 concurrent execution
- `update_glossary`: Unlimited (fast operation)

### 6.3 File System Sandbox
- Can only read from `source/` and `config/` directories
- Can only write to `output/` directory
- Attempts to access other paths return `-32602` (Invalid Params)

---

## 7. Example Client Interaction

```json
// Client requests
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_pipeline",
    "arguments": {
      "file_path": "/data/chapter-en-0001.md",
      "output_dir": "/output/",
      "model": "gemma2:9b"
    }
  }
}

// Server responds
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Pipeline completed. State: APPROVED. Grade: B+. Output: /output/chapter-my-0001.md"
      }
    ],
    "isError": false
  }
}
```

---

## 8. Server Configuration

```json
{
  "mcp_server": {
    "name": "myanmar-novel-translator",
    "version": "1.0.0",
    "transport": "stdio",
    "capabilities": {
      "tools": true,
      "resources": true,
      "prompts": true
    },
    "config": {
      "ollama_host": "http://localhost:11434",
      "default_model": "gemma2:9b",
      "source_dir": "./source",
      "output_dir": "./output",
      "config_dir": "./config"
    }
  }
}
```

---

*End of MCP_SERVICE.md*
