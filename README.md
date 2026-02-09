# plugin-import-error

Passive detection for Claude Code's shared Python process state bug across plugin hooks.

## The Bug

Claude Code's hook execution environment may share Python `sys.modules` state across hook invocations within a session. When two plugins have packages with the same name (e.g., `lib`), the first to import "wins" in `sys.modules`, causing `ModuleNotFoundError` in subsequent hooks that expect the other package.

**Issue**: https://github.com/anthropics/claude-code/issues/23089

**Status**: The bug manifests organically in production (kitaekatt-plugins) but has not been reliably reproduced in a minimal case. Each hook invocation gets its own process (different PIDs, fresh `sys.modules`). This plugin passively monitors for the condition.

## How This Plugin Works

Two plugins set up the conditions for a namespace collision:

- **base-plugin**: Provides `python/lib/config_cache.py` with `get_config()` returning `{"source": "base-plugin"}`
- **import-plugin**: Provides `shadow-lib/lib/__init__.py` — a shadow `lib` package with NO `config_cache` submodule (NOT added to sys.path by the hook — only relevant if leaked by the runtime)

The `favorite-color` skill triggers three hooks that passively monitor:

### Hook 1: PreToolUse `test-import.py` (Passive Detection)
- Checks if `lib` or `lib.config_cache` is in `sys.modules` at startup (before importing anything)
- If found: **denies with "STALE MODULE DETECTED"** — proves cross-invocation persistence
- If not found: imports normally from base-plugin, reports success
- Logs PID, sys.modules state, and sys.path for forensics

### Hook 2: PreToolUse `probe-modules.py` (Process Sharing Detector)
- Checks if `lib` leaked into `sys.modules` from test-import.py running in the same process
- Different PID = separate process (expected). Same PID with `lib` present = process sharing (the bug)

### Hook 3: PostToolUse `check-stale-modules.py` (Cross-Event Detector)
- Checks if `lib` leaked from PreToolUse into PostToolUse
- If present, proves process sharing across hook event types

## Usage

```
Skill(skill: "favorite-color")
```

Or:
```
Skill(skill: "import-plugin:favorite-color")
```

Invoke repeatedly across a session. The bug is intermittent — it may take many invocations or specific conditions to trigger.

## What to Look For

| Outcome | Meaning |
|---------|---------|
| "no stale modules detected" | Fresh process, no bug this invocation |
| Hook denies with "STALE MODULE DETECTED" | `lib` was in sys.modules at startup — bug reproduced! |
| Hook denies with "UNEXPECTED IMPORT FAILURE" | Import failed without shadow — runtime state interference |
| probe-modules.py logs "BATCH SHARING DETECTED" | Hooks share a Python process within one tool call |
| check-stale-modules.py reports stale modules | Process state leaks from PreToolUse to PostToolUse |

Check the log file for detailed diagnostics:
```
cat ~/.claude/plugins/cache/plugin-import-error/plugin-import-error.log
```

## Previous Testing Results

| Hypothesis | Status | Evidence |
|---|---|---|
| sys.modules shared between invocations | Not observed | Different PIDs, sys.modules starts empty each time |
| Multiple hooks share one Python process | Not observed | Different PIDs for test-import.py and probe-modules.py |
| Self-inflicted collision (shadow + real on same sys.path) | Confirmed works | But this doesn't prove the real bug |
| Organic staleness in production | Confirmed occurs | kitaekatt-plugins hooks fail with identical symptoms |

## Structure

```
plugins/
├── base-plugin/              # Provides the real lib.config_cache module
│   ├── .claude-plugin/
│   │   └── plugin.json
│   └── python/lib/
│       ├── __init__.py
│       └── config_cache.py   # get_config() → {"source": "base-plugin"}
└── import-plugin/            # Passive monitor + shadow lib
    ├── .claude-plugin/
    │   └── plugin.json
    ├── hooks/
    │   ├── hooks.json
    │   ├── pretooluse/
    │   │   ├── test-import.py      # Passive stale module detector
    │   │   └── probe-modules.py    # Process sharing detector
    │   └── posttooluse/
    │       └── check-stale-modules.py  # Cross-event-type detector
    ├── shadow-lib/lib/
    │   └── __init__.py       # Shadow package (NOT loaded by hooks)
    └── skills/
        └── favorite-color/
            └── SKILL.md      # Trigger skill
```

## Related

- GitHub issue: https://github.com/anthropics/claude-code/issues/23089
- Full investigation context: `kitaekatt-plugins/tmp/hook-error-investigation-report.md`
