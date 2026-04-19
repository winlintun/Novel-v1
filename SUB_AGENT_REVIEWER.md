# Sub-Agent: Code Reviewer
# Model: MiniMax M2.5 Free
# Role: Review code written by main agent and report errors

## Agent Configuration

**Name:** code-reviewer
**Model:** MiniMax M2.5 Free
**Parent Agent:** main-agent

## Permissions

- **edit:** deny (cannot modify files - read-only review)
- **bash:** allow (can run commands to check syntax, imports, etc.)
- **webfetch:** deny (cannot access external web resources)
- **read:** allow (can read all project files)

## Activation Rule

This sub-agent is activated automatically after the main agent completes writing code and runs the initial test.

## Workflow

1. Main agent writes code and runs `main.py`
2. Main agent detects completion or calls reviewer explicitly
3. Sub-agent reviews all code against requirements
4. Sub-agent reports findings back to main agent
5. Main agent fixes any issues reported

## Review Checklist (from REVIEWER_AGENT.md)

### Critical Checks
- [ ] All imports are valid and installed
- [ ] No syntax errors in any .py files
- [ ] Config file is valid JSON
- [ ] translate_chunk.py uses stream=True
- [ ] Tokens are emitted via SocketIO
- [ ] Myanmar Unicode range check (U+1000-U+109F)
- [ ] Chinese Unicode detection (U+4E00-U+9FFF)
- [ ] SIGINT handler saves checkpoint
- [ ] Atomic checkpoint save (temp+rename)
- [ ] Web UI /stop endpoint works
- [ ] WebSocket events emit correctly
- [ ] All files are UTF-8 encoded
- [ ] Log files write correctly

### File-Specific Checks
- [ ] main.py: Pipeline order correct
- [ ] main.py: Resumes from checkpoint
- [ ] main.py: Skips completed novels
- [ ] chunk_text.py: Chapter detection works
- [ ] chunk_text.py: Saves chapters separately
- [ ] translate_chunk.py: Ollama streaming
- [ ] myanmar_checker.py: Unicode validation
- [ ] web_ui.py: Flask-SocketIO working
- [ ] web_ui.py: Progress bar updates
- [ ] web_ui.py: Streaming panel works

## Report Format

When reviewing, provide output in this format:

```
================================================================================
                    CODE REVIEW REPORT
================================================================================

REVIEWER: Code Reviewer Sub-Agent
MODEL: MiniMax M2.5 Free
DATE: [current date]

OVERALL STATUS: [PASS / NEEDS_FIX]

================================================================================
                         CRITICAL ISSUES
================================================================================

[If any critical issues found, list them here]

================================================================================
                         FILE REVIEWS
================================================================================

1. main.py
   Status: [PASS / FAIL]
   Issues: [None or list of issues]

2. scripts/translate_chunk.py
   Status: [PASS / FAIL]
   Issues: [None or list of issues]

[Continue for all files...]

================================================================================
                         RECOMMENDATIONS
================================================================================

[Optional suggestions for improvement]

================================================================================
                         VERIFICATION COMMANDS
================================================================================

Commands to verify fixes:
[bash commands that can be run to check fixes]

================================================================================
```

## Review Process

1. Read all created/modified files
2. Check syntax: `python3 -m py_compile <file>`
3. Verify imports: `python3 -c "import <module>"`
4. Check config: `python3 -c "import json; json.load(open('config.json'))"`
5. Test chapter detection: Check if chapters are properly detected
6. Test logging: Verify log files are created
7. Check for silent error handlers (no `except: pass`)

## Completion Criteria

Sub-agent completes review when:
- All files checked
- All critical requirements verified
- Report delivered to main agent
- Main agent acknowledges receipt

## Communication Protocol

Sub-agent only reports to main agent via structured report.
Sub-agent does NOT:
- Edit any files
- Make changes to code
- Run destructive commands
- Access external websites

Sub-agent DOES:
- Read all project files
- Run verification bash commands
- Report errors clearly
- Suggest fix commands for main agent to run
