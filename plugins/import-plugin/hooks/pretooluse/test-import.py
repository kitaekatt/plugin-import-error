#!/usr/bin/env python3
"""PreToolUse hook: Always-on passive monitor for stale sys.modules.

Fires on every tool call. Silent unless the bug is detected.

On each invocation:
1. Check if `lib` or `lib.config_cache` is already in sys.modules (stale leak)
2. Resolve base-plugin path, add to sys.path
3. Attempt: from lib.config_cache import get_config
4. Success → silent pass
5. Failure → deny with "BUG REPRODUCED" + diagnostic state

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
    try:
        json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    pid = os.getpid()

    # Check for stale modules BEFORE importing anything
    lib_stale = "lib" in sys.modules
    lib_cc_stale = "lib.config_cache" in sys.modules

    # Resolve base-plugin path from registry
    registry = Path.home() / ".claude/plugins/installed_plugins.json"
    try:
        with open(registry) as f:
            plugins = json.loads(f.read())["plugins"]
        base_path = str(Path(plugins["base-plugin@plugin-import-error"][0]["installPath"]) / "python")
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
    except Exception:
        # Can't resolve base-plugin — silently pass
        print(json.dumps({"continue": True, "suppressOutput": True}))
        sys.exit(0)

    # Attempt the import
    try:
        from lib.config_cache import get_config
        get_config()
    except (ModuleNotFoundError, ImportError) as e:
        lib_mod = sys.modules.get("lib")
        lib_file = getattr(lib_mod, "__file__", "(none)") if lib_mod else "(not in sys.modules)"
        lib_path_attr = getattr(lib_mod, "__path__", "(none)") if lib_mod else "(not in sys.modules)"

        reason = (
            f"BUG REPRODUCED (github.com/anthropics/claude-code/issues/23089): {e}\n"
            f"lib stale at startup: {lib_stale}, lib.config_cache stale: {lib_cc_stale}\n"
            f"lib.__file__={lib_file}, lib.__path__={lib_path_attr}, pid={pid}"
        )
        log(f"pid={pid} {reason}")

        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }))
        sys.exit(0)

    # If modules were stale at startup but import succeeded anyway, log it
    if lib_stale or lib_cc_stale:
        lib_mod = sys.modules.get("lib")
        lib_file = getattr(lib_mod, "__file__", "(none)") if lib_mod else "(none)"
        log(f"pid={pid} STALE AT STARTUP (import succeeded): lib={lib_stale} lib.config_cache={lib_cc_stale} lib.__file__={lib_file}")

    # Success — silent pass
    print(json.dumps({"continue": True, "suppressOutput": True}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"pid={os.getpid()} FATAL: {type(e).__name__}: {e}")
        print(json.dumps({"continue": True, "suppressOutput": True}))
