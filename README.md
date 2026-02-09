# plugin-import-error

Minimal reproduction for Claude Code shared `sys.modules` state across plugin hooks.

**Issue**: https://github.com/anthropics/claude-code/issues/23089

## The Bug

Plugin hooks that import from other plugins experience `ModuleNotFoundError` or `ImportError` even though the import works in a standalone Python process. Errors appear and disappear spontaneously within a session without code changes. This suggests the hook execution environment leaks `sys.modules` state across invocations.

## How It Works

Two plugins:
- **base-plugin** — provides `python/lib/config_cache.py` (a simple module)
- **import-plugin** — has a PreToolUse hook that imports `lib.config_cache` from base-plugin on every tool call

The hook fires on every tool call, silently passes when the import succeeds, and **denies with "BUG REPRODUCED"** if:
- `lib` is already in `sys.modules` at startup (stale from a prior invocation)
- The import fails despite `base-plugin/python` being on `sys.path`

## Installation

1. Clone this repo
2. Register the marketplace in `~/.claude/plugins/known_marketplaces.json`:
   ```json
   {
     "plugin-import-error": {
       "source": {"source": "directory", "path": "/path/to/plugin-import-error"},
       "installLocation": "/path/to/plugin-import-error"
     }
   }
   ```
3. Enable both plugins in `~/.claude/settings.json`:
   ```json
   {
     "enabledPlugins": {
       "base-plugin@plugin-import-error": true,
       "import-plugin@plugin-import-error": true
     }
   }
   ```
4. Restart Claude Code

## What to Expect

- **Normal usage**: Nothing visible. The hook runs silently on every tool call.
- **Bug detected**: A hook error appears: `"BUG REPRODUCED (github.com/anthropics/claude-code/issues/23089)"` with diagnostic state (PID, `sys.modules` contents, `lib.__file__`).
- **Log file**: `plugin-import-error.log` in the plugin cache directory (only written on failure).

## Structure

```
plugins/
├── base-plugin/
│   ├── .claude-plugin/plugin.json
│   └── python/lib/
│       ├── __init__.py
│       └── config_cache.py
└── import-plugin/
    ├── .claude-plugin/plugin.json
    └── hooks/
        ├── hooks.json
        └── pretooluse/
            └── test-import.py
```
