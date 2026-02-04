# plugin-import-error

Minimal reproduction case for Claude Code's internal module cache staleness bug.

## The Bug

Claude Code's Python subprocess environment retains stale module state. After fixing an import error in plugin source and refreshing the cache, the error persists inside Claude Code despite the fix being verified in the cached files. The error resolves spontaneously after ~5-10 minutes.

## Structure

```
plugins/
├── base-plugin/          # Provides lib.config_cache module
│   └── python/lib/
│       ├── __init__.py
│       └── config_cache.py
└── import-plugin/        # Hook that tries to import lib.config_cache
    ├── hooks/pretooluse/
    │   └── test-import.py    # Has shadow path hack that causes the error
    └── shadow-lib/lib/
        └── __init__.py       # Empty lib package that shadows the real one
```

## Reproduction Steps

### Step 1: Establish the error

1. Register this marketplace in `~/.claude/plugins/known_marketplaces.json`
2. Enable both plugins
3. Clear cache, restart Claude Code
4. Every tool call should show: `IMPORT ERROR: ModuleNotFoundError: No module named 'lib.config_cache'`

### Step 2: Apply the fix

1. Edit `plugins/import-plugin/hooks/pretooluse/test-import.py`
2. Remove the lines between `--- SHADOW PATH HACK ---` and `--- END SHADOW PATH HACK ---`
3. Clear plugin cache and refresh
4. Verify fix is in cache: `grep shadow_path ~/.claude/plugins/cache/plugin-import-error/import-plugin/*/hooks/pretooluse/test-import.py` should return nothing

### Step 3: Observe

- Direct test should succeed (fresh Python process, no stale state)
- Claude Code: Does the hook still fail with `No module named 'lib.config_cache'`?

If the error persists in Claude Code despite the verified fix, **that's the bug**.

### Log file

Check `~/.claude/plugins/cache/plugin-import-error/plugin-import-error.log` for execution traces.
Each invocation logs the resolved paths and import result (SUCCESS or FAILED).

## What This Simulates

The original bug (`2026-01-31-lib-yaml-config-cache.md` in kitaekatt-plugins):
- `~/.claude/hooks/lib/` had only `__init__.py`
- Plugin hook added `~/.claude/hooks/lib` to `sys.path[0]`
- Python resolved `lib` as that empty package instead of the plugin's `lib/config_cache.py`
- After removing the path hack and refreshing cache, the error persisted inside Claude Code
