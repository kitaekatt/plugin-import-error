#!/usr/bin/env python3
"""PreToolUse hook: Cross-plugin import collision reproduction.

Tests whether Claude Code's hook execution shares sys.modules across
plugin hooks, causing namespace collisions.

Setup:
- base-plugin provides: python/lib/config_cache.py (the real module)
- import-plugin provides: shadow-lib/lib/__init__.py (shadow package, no config_cache)

This hook adds both to sys.path (shadow first), then attempts:
    from lib.config_cache import get_config

If sys.modules is shared across hooks, a prior hook's `lib` import may
shadow the real one, causing ModuleNotFoundError.

Only triggers on the "favorite-color" skill invocation.

Related: https://github.com/anthropics/claude-code/issues/23089
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent.parent.parent.parent / "plugin-import-error.log"


def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def main() -> None:
    # Read hook input from stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    # Only act on the "favorite-color" skill
    tool_input = hook_input.get("tool_input", {})
    skill_name = tool_input.get("skill", "")
    if skill_name not in ("favorite-color", "import-plugin:favorite-color"):
        sys.exit(0)

    pid = os.getpid()
    log(f"TEST-IMPORT pid={pid} invoked for skill={skill_name}")

    # Check if lib is already in sys.modules (stale from prior invocation)
    lib_already_cached = "lib" in sys.modules
    lib_cc_already_cached = "lib.config_cache" in sys.modules
    if lib_already_cached or lib_cc_already_cached:
        log(f"TEST-IMPORT pid={pid} STALE: lib={lib_already_cached} lib.config_cache={lib_cc_already_cached}")

    # Resolve plugin paths from installed_plugins.json registry
    registry = Path.home() / ".claude/plugins/installed_plugins.json"
    try:
        with open(registry) as f:
            plugins = json.loads(f.read())["plugins"]
    except Exception as e:
        log(f"TEST-IMPORT pid={pid} registry error: {e}")
        # Can't resolve paths — allow and exit
        print(json.dumps({"continue": True, "suppressOutput": False}))
        sys.exit(0)

    # Add base-plugin's python/ to sys.path (provides real lib.config_cache)
    try:
        base_path = str(Path(plugins["base-plugin@plugin-import-error"][0]["installPath"]) / "python")
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
        log(f"TEST-IMPORT pid={pid} base-plugin path: {base_path}")
    except (KeyError, IndexError) as e:
        log(f"TEST-IMPORT pid={pid} base-plugin not found: {e}")

    # Add import-plugin's shadow-lib/ to sys.path at position 0 (shadows real lib)
    try:
        shadow_path = str(Path(plugins["import-plugin@plugin-import-error"][0]["installPath"]) / "shadow-lib")
        if shadow_path not in sys.path:
            sys.path.insert(0, shadow_path)
        log(f"TEST-IMPORT pid={pid} shadow path (pos 0): {shadow_path}")
    except (KeyError, IndexError) as e:
        log(f"TEST-IMPORT pid={pid} shadow path not found: {e}")

    log(f"TEST-IMPORT pid={pid} sys.path order: {sys.path[:5]}")

    # Attempt the cross-plugin import
    try:
        from lib.config_cache import get_config
        result = get_config()
        source = result.get("source", "unknown")
        log(f"TEST-IMPORT pid={pid} SUCCESS: source={source}")

        # Import succeeded — report and allow
        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "systemMessage": f"[import-test] import succeeded: source={source} (no collision this invocation)"
        }))

    except (ModuleNotFoundError, ImportError) as e:
        log(f"TEST-IMPORT pid={pid} BUG REPRODUCED: {e}")

        # Bug reproduced — deny with visible error message
        lib_mod = sys.modules.get("lib")
        lib_file = getattr(lib_mod, "__file__", "(none)") if lib_mod else "(not in sys.modules)"
        lib_path_attr = getattr(lib_mod, "__path__", "(none)") if lib_mod else "(not in sys.modules)"

        reason = (
            f"BUG REPRODUCED (github.com/anthropics/claude-code/issues/23089): {e}\n"
            f"Shadow lib package overrode real lib via sys.path ordering.\n"
            f"lib.__file__={lib_file}, lib.__path__={lib_path_attr}\n"
            f"pid={pid}, stale_before_import={lib_already_cached}"
        )

        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }))

    except Exception as e:
        log(f"TEST-IMPORT pid={pid} unexpected error: {type(e).__name__}: {e}")
        print(json.dumps({"continue": True, "suppressOutput": False}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"TEST-IMPORT FATAL: {type(e).__name__}: {e}")
        print(json.dumps({"continue": True, "suppressOutput": False}))
        sys.exit(0)
