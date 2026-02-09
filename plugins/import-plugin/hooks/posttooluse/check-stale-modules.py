#!/usr/bin/env python3
"""PostToolUse hook: Check for stale modules leaked from PreToolUse hooks.

Tests whether PostToolUse hooks share process state with PreToolUse hooks
from the same tool call. If `lib` or `lib.config_cache` appears in
sys.modules without this hook importing them, it proves process sharing.

Only triggers after "favorite-color" skill invocation.

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

    # Only act after "favorite-color" skill
    tool_input = hook_input.get("tool_input", {})
    skill_name = tool_input.get("skill", "")
    if skill_name not in ("favorite-color", "import-plugin:favorite-color"):
        print(json.dumps({"continue": True, "suppressOutput": True}))
        sys.exit(0)

    pid = os.getpid()
    lib_in_modules = "lib" in sys.modules
    lib_cc_in_modules = "lib.config_cache" in sys.modules

    log(f"CHECK-STALE pid={pid} lib={lib_in_modules} lib.config_cache={lib_cc_in_modules}")

    if lib_in_modules or lib_cc_in_modules:
        # Stale modules detected — process sharing confirmed
        lib_mod = sys.modules.get("lib")
        lib_file = getattr(lib_mod, "__file__", "(none)") if lib_mod else "(none)"
        lib_path_attr = getattr(lib_mod, "__path__", "(none)") if lib_mod else "(none)"

        msg = (
            f"STALE MODULE DETECTED in PostToolUse (pid={pid}): "
            f"lib in sys.modules from prior PreToolUse hook invocation. "
            f"lib.__file__={lib_file}, lib.__path__={lib_path_attr}. "
            f"This confirms process sharing across hook event types. "
            f"See: github.com/anthropics/claude-code/issues/23089"
        )
        log(f"CHECK-STALE pid={pid} PROCESS SHARING CONFIRMED: {msg}")

        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": msg
            }
        }))
    else:
        log(f"CHECK-STALE pid={pid} clean — no stale modules (separate process)")
        print(json.dumps({"continue": True, "suppressOutput": True}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"CHECK-STALE FATAL: {type(e).__name__}: {e}")
        print(json.dumps({"continue": True, "suppressOutput": True}))
        sys.exit(0)
