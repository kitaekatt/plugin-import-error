#!/usr/bin/env python3
"""PreToolUse hook: Passive detection of stale sys.modules across hook invocations.

Does NOT force a collision. Instead:
1. Checks if `lib` or `lib.config_cache` is already in sys.modules at startup
2. If found: reports STALE MODULE DETECTED (proves cross-invocation persistence)
3. If not found: imports normally from base-plugin and reports success

The shadow-lib package exists but is NOT added to sys.path by this hook.
It's only relevant if Claude Code's runtime leaks it from another hook/invocation.

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

    # === PASSIVE DETECTION ===
    # Check if lib is already in sys.modules BEFORE we do anything.
    # In a fresh process, it should NOT be present.
    # If present, it leaked from a prior hook invocation (the bug).
    lib_stale = "lib" in sys.modules
    lib_cc_stale = "lib.config_cache" in sys.modules

    stale_details = ""
    if lib_stale or lib_cc_stale:
        lib_mod = sys.modules.get("lib")
        lib_file = getattr(lib_mod, "__file__", "(none)") if lib_mod else "(none)"
        lib_path_attr = getattr(lib_mod, "__path__", "(none)") if lib_mod else "(none)"
        stale_details = f"lib.__file__={lib_file}, lib.__path__={lib_path_attr}"
        log(f"TEST-IMPORT pid={pid} STALE MODULES AT STARTUP: lib={lib_stale} lib.config_cache={lib_cc_stale} {stale_details}")

    # Log all non-stdlib top-level modules for forensics
    non_stdlib = [m for m in sorted(sys.modules.keys())
                  if not m.startswith(('_', 'builtins', 'sys', 'os', 'io',
                                       'posix', 'encodings', 'codecs', 'abc',
                                       'importlib', 'types', 'warnings',
                                       'collections', 'functools', 'operator',
                                       'keyword', 'signal', 'errno', 'stat',
                                       'genericpath', 'posixpath', 'nt',
                                       'zipimport', 'marshal'))
                  and '.' not in m]
    log(f"TEST-IMPORT pid={pid} sys.modules at startup: {non_stdlib}")

    # Resolve base-plugin path from registry
    registry = Path.home() / ".claude/plugins/installed_plugins.json"
    try:
        with open(registry) as f:
            plugins = json.loads(f.read())["plugins"]
    except Exception as e:
        log(f"TEST-IMPORT pid={pid} registry error: {e}")
        print(json.dumps({"continue": True, "suppressOutput": False}))
        sys.exit(0)

    # Add ONLY base-plugin's python/ to sys.path (no shadow!)
    try:
        base_path = str(Path(plugins["base-plugin@plugin-import-error"][0]["installPath"]) / "python")
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
        log(f"TEST-IMPORT pid={pid} base-plugin path: {base_path}")
    except (KeyError, IndexError) as e:
        log(f"TEST-IMPORT pid={pid} base-plugin not found: {e}")

    # If stale module detected, report it prominently
    if lib_stale or lib_cc_stale:
        reason = (
            f"STALE MODULE DETECTED (github.com/anthropics/claude-code/issues/23089): "
            f"lib was in sys.modules BEFORE this hook imported anything.\n"
            f"lib={lib_stale}, lib.config_cache={lib_cc_stale}\n"
            f"{stale_details}\n"
            f"pid={pid}"
        )
        log(f"TEST-IMPORT pid={pid} REPORTING STALE DETECTION")

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

    # Normal import — should always succeed in a fresh process
    try:
        from lib.config_cache import get_config
        result = get_config()
        source = result.get("source", "unknown")
        log(f"TEST-IMPORT pid={pid} import ok: source={source}")

        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "systemMessage": f"[import-test] pid={pid} import ok, source={source}, no stale modules detected"
        }))

    except (ModuleNotFoundError, ImportError) as e:
        # This shouldn't happen without the shadow — if it does, something else is wrong
        log(f"TEST-IMPORT pid={pid} UNEXPECTED IMPORT FAILURE: {e}")

        lib_mod = sys.modules.get("lib")
        lib_file = getattr(lib_mod, "__file__", "(none)") if lib_mod else "(not in sys.modules)"

        reason = (
            f"UNEXPECTED IMPORT FAILURE (github.com/anthropics/claude-code/issues/23089): {e}\n"
            f"No shadow-lib was added to sys.path — this failure is from stale runtime state.\n"
            f"lib in sys.modules={('lib' in sys.modules)}, lib.__file__={lib_file}\n"
            f"pid={pid}"
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
