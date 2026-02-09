# plugin-import-error

Minimal reproduction case for Claude Code's shared Python process state bug across plugin hooks.

## The Bug

Claude Code's hook execution environment shares Python `sys.modules` state across hook invocations within a session. When two plugins have packages with the same name (e.g., `lib`), the first to import "wins" in `sys.modules`, causing `ModuleNotFoundError` in subsequent hooks that expect the other package.

**Issue**: https://github.com/anthropics/claude-code/issues/23089

## How This Plugin Works

Two plugins with conflicting `lib` packages:

- **base-plugin**: Provides `python/lib/config_cache.py` with `get_config()` returning `{"source": "base-plugin"}`
- **import-plugin**: Provides `shadow-lib/lib/__init__.py` — a shadow `lib` package with NO `config_cache` submodule

The `favorite-color` skill triggers three hooks that test for the collision:

### Hook 1: PreToolUse `test-import.py`
Adds both paths to `sys.path` (shadow first), then attempts `from lib.config_cache import get_config`.
- **On success**: Shows "import succeeded: source=base-plugin" (collision didn't occur)
- **On failure**: **Denies with "BUG REPRODUCED"** message visible in Claude Code's UI

### Hook 2: PreToolUse `probe-modules.py`
Checks if `lib` appears in `sys.modules` without importing it. If present, another hook in the same process loaded it — proving hooks share a Python process.

### Hook 3: PostToolUse `check-stale-modules.py`
Checks if `lib` leaked from PreToolUse into PostToolUse. If present, proves process sharing across hook event types.

## Usage

```
Skill(skill: "favorite-color")
```

Or:
```
Skill(skill: "import-plugin:favorite-color")
```

## What to Look For

| Outcome | Meaning |
|---------|---------|
| Hook denies with "BUG REPRODUCED" | Shadow `lib` overrode real `lib` via `sys.modules` |
| Hook allows with "import succeeded" | No collision this invocation (may need multiple tries) |
| probe-modules.py logs "BATCH SHARING DETECTED" | Hooks share a Python process within one tool call |
| check-stale-modules.py reports "STALE MODULE DETECTED" | Process state leaks from PreToolUse to PostToolUse |

Check the log file for detailed diagnostics:
```
cat plugin-import-error.log
```

## Structure

```
plugins/
├── base-plugin/              # Provides the real lib.config_cache module
│   ├── .claude-plugin/
│   │   └── plugin.json
│   └── python/lib/
│       ├── __init__.py
│       └── config_cache.py   # get_config() → {"source": "base-plugin"}
└── import-plugin/            # Has shadow lib + test hooks
    ├── .claude-plugin/
    │   └── plugin.json
    ├── hooks/
    │   ├── hooks.json
    │   ├── pretooluse/
    │   │   ├── test-import.py      # Cross-plugin import test
    │   │   └── probe-modules.py    # sys.modules leak detector
    │   └── posttooluse/
    │       └── check-stale-modules.py  # Cross-event-type leak detector
    ├── shadow-lib/lib/
    │   └── __init__.py       # Shadow package (no config_cache)
    └── skills/
        └── favorite-color/
            └── SKILL.md      # Trigger skill
```

## Related

- GitHub issue: https://github.com/anthropics/claude-code/issues/23089
- Full investigation context: `kitaekatt-plugins/tmp/hook-error-investigation-report.md`
