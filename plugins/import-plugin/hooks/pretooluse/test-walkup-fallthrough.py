#!/usr/bin/env python3
"""Reproduce the walk-up bootstrap fallthrough bug.

BUG: When .claude-plugin marker is not in any ancestor directory,
the walk-up loop reaches / and sys.path gets "/python/" injected.
This causes ModuleNotFoundError for all plugin imports.

Fixed in kitaekatt-plugins commit af3e53f by replacing walk-up
with direct installed_plugins.json registry lookup.
"""
import json
import sys
from pathlib import Path


def main() -> None:
    """Demonstrate walk-up fallthrough from a path with no .claude-plugin ancestor."""
    # Simulate hook running from a location where .claude-plugin
    # is NOT in any ancestor (the bug condition)
    fake_hook_dir = Path("/tmp/no-plugin-marker-here")

    # === Old walk-up pattern (THE BUG) ===
    plugin_root = fake_hook_dir
    while not (plugin_root / ".claude-plugin").exists() and plugin_root != plugin_root.parent:
        plugin_root = plugin_root.parent

    # plugin_root is now / — the silent fallthrough
    bad_path = str(plugin_root / "python")

    # Attempt import with the bad path to show the failure
    sys.path.insert(0, bad_path)
    import_error = None
    try:
        import base_module  # noqa: F401
    except ModuleNotFoundError as e:
        import_error = str(e)
    finally:
        if bad_path in sys.path:
            sys.path.remove(bad_path)

    result = {
        "continue": True,
        "message": json.dumps({
            "bug_demo": "walk-up-fallthrough",
            "started_from": str(fake_hook_dir),
            "walked_up_to": str(plugin_root),
            "would_inject_path": bad_path,
            "path_exists": Path(bad_path).exists(),
            "bug_reproduced": str(plugin_root) == "/",
            "import_error": import_error,
            "explanation": (
                "Walk-up reached / because no .claude-plugin marker found. "
                "sys.path gets '/python/' which doesn't exist, "
                "causing ModuleNotFoundError for all plugin imports."
            ),
        }, indent=2),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
