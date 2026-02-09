---
_schema_version: 1
name: favorite-color
description: Invoke to test cross-plugin import collision. Triggers hooks that attempt importing lib.config_cache with a shadowing lib package on sys.path. Used to reproduce github.com/anthropics/claude-code/issues/23089.
---

# Favorite Color (Import Collision Test)

Invoke this skill to trigger the cross-plugin import collision test.

## What Happens

1. **PreToolUse: test-import.py** — Adds both `base-plugin/python/lib/` (real module) and `import-plugin/shadow-lib/lib/` (shadow, no config_cache) to sys.path, then attempts `from lib.config_cache import get_config`
   - **Success**: Shows "import succeeded: source=base-plugin"
   - **Bug reproduced**: Denies with "BUG REPRODUCED" message showing the collision details

2. **PreToolUse: probe-modules.py** — Checks if `lib` leaked into sys.modules from test-import.py (detects same-process hook execution)

3. **PostToolUse: check-stale-modules.py** — Checks if `lib` from PreToolUse leaked into PostToolUse (detects cross-event-type process sharing)

## How to Use

```
Skill(skill: "favorite-color")
```

Then check the log file for detailed diagnostics:
```
cat ~/Dev/plugin-import-error/plugin-import-error.log
```

## Related

- Issue: https://github.com/anthropics/claude-code/issues/23089
