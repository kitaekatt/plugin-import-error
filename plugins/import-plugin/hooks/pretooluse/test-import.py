#!/usr/bin/env python3
"""PreToolUse hook that reproduces the cache staleness bug.

Uses registry-based bootstrap (installed_plugins.json) for path resolution,
matching the pattern used by all kitaekatt-plugins hooks.

This hook has a shadow path hack that inserts shadow-lib/lib/ (empty package
with only __init__.py) BEFORE the real base-plugin/python/lib/ on sys.path.
Python finds the shadow lib first, which has no config_cache.py, causing the error.

To reproduce the cache bug:
1. Install with this hook as-is — import fails (shadow path wins)
2. Remove the lines between --- SHADOW PATH HACK --- and --- END SHADOW PATH HACK ---
3. Clear plugin cache and refresh
4. Verify: grep shadow_path in cached hook returns nothing
5. Observe: does Claude Code still fail with the stale error?

If the error persists after step 4 despite verified fix, that's the bug.

Log file: ~/.claude/plugins/cache/plugin-import-error/plugin-import-error.log
"""
import json
import sys
from datetime import datetime
from pathlib import Path


LOG_FILE = Path(__file__).resolve().parent.parent.parent.parent.parent / "plugin-import-error.log"


def log(msg: str) -> None:
    """Append timestamped message to log file."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def _safe_main() -> None:
    hook_file = Path(__file__).resolve()
    log(f"Hook invoked from: {hook_file}")

    # Registry-based import: resolve plugin paths from installed_plugins.json.
    # This works in both source and cache directory layouts.
    _registry = Path.home() / ".claude/plugins/installed_plugins.json"
    with open(_registry) as _f:
        _plugins = json.loads(_f.read())["plugins"]

    # Add base-plugin's python/ to path (the real lib package lives here)
    base_path = str(Path(_plugins["base-plugin@plugin-import-error"][0]["installPath"]) / "python")
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    log(f"Base plugin path inserted: {base_path}")

    # --- SHADOW PATH HACK (remove these lines in Step 2 to "fix" the error) ---
    # Inserted AFTER base_path so shadow lands at sys.path[0] and wins resolution
    shadow_path = str(Path(_plugins["import-plugin@plugin-import-error"][0]["installPath"]) / "shadow-lib")
    if shadow_path not in sys.path:
        sys.path.insert(0, shadow_path)
    log(f"Shadow path inserted (at position 0, overrides base): {shadow_path}")
    # --- END SHADOW PATH HACK ---

    # With shadow hack: fails because shadow-lib/lib/ is found first
    # shadow-lib/lib/ has __init__.py but no config_cache.py
    # Without shadow hack: should succeed via base-plugin/python/lib/config_cache.py
    log("Attempting: from lib.config_cache import get_config")
    from lib.config_cache import get_config

    result = get_config()
    log(f"SUCCESS: {result}")

    print(json.dumps({
        "continue": True,
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"config loaded: {result}"
        }
    }))


if __name__ == "__main__":
    try:
        _safe_main()
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        log(f"FAILED: {error_msg}")
        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"IMPORT ERROR: {error_msg}"
            }
        }))
