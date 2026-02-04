#!/usr/bin/env python3
"""Compare buggy walk-up bootstrap vs fixed registry-based bootstrap.

Demonstrates both approaches side-by-side:
- Walk-up: fragile, silently falls through to / when marker missing
- Registry: deterministic, reads installed_plugins.json directly

Fixed in kitaekatt-plugins commit af3e53f.
"""
import json
import sys
from pathlib import Path


def test_walkup_bootstrap() -> dict:
    """Test the old walk-up pattern from the hook's actual location.

    When running from source (--plugin-dir), .claude-plugin IS in an
    ancestor, so this succeeds. But when running from a location where
    the marker is missing, it silently falls through to /.
    """
    hook_file = Path(__file__).resolve()
    plugin_root = hook_file.parent
    while not (plugin_root / ".claude-plugin").exists() and plugin_root != plugin_root.parent:
        plugin_root = plugin_root.parent

    python_path = str(plugin_root / "python")
    fell_through = str(plugin_root) == "/"

    import_ok = False
    error = None
    if not fell_through:
        sys.path.insert(0, python_path)
        try:
            from import_plugin_resolver import import_plugin
            import_plugin("base-plugin@plugin-import-error", "python")
            from base_module import hello  # noqa: F401
            import_ok = True
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        finally:
            if python_path in sys.path:
                sys.path.remove(python_path)
    else:
        error = "Walk-up fell through to / — would inject /python/ into sys.path"

    return {
        "method": "walk-up",
        "plugin_root": str(plugin_root),
        "fell_through_to_root": fell_through,
        "import_succeeded": import_ok,
        "error": error,
    }


def test_registry_bootstrap() -> dict:
    """Test the fixed registry-based pattern.

    Reads installed_plugins.json directly — no filesystem walking.
    Always works if plugins are installed in the registry.
    """
    registry_path = Path.home() / ".claude/plugins/installed_plugins.json"

    if not registry_path.exists():
        return {
            "method": "registry",
            "import_succeeded": False,
            "error": f"Registry not found: {registry_path}",
            "note": "Expected when plugin-import-error marketplace not registered",
        }

    try:
        with open(registry_path) as f:
            plugins = json.loads(f.read())["plugins"]

        plugin_id = "base-plugin@plugin-import-error"
        if plugin_id not in plugins:
            return {
                "method": "registry",
                "import_succeeded": False,
                "error": f"Plugin not in registry: {plugin_id}",
                "available_plugins": list(plugins.keys())[:5],
                "note": "Register plugin-import-error marketplace to test this path",
            }

        install_path = str(Path(plugins[plugin_id][0]["installPath"]) / "python")
        sys.path.insert(0, install_path)
        try:
            from base_module import hello  # noqa: F401
            return {
                "method": "registry",
                "install_path": install_path,
                "import_succeeded": True,
                "error": None,
            }
        except ImportError as e:
            return {
                "method": "registry",
                "install_path": install_path,
                "import_succeeded": False,
                "error": str(e),
            }
        finally:
            if install_path in sys.path:
                sys.path.remove(install_path)

    except Exception as e:
        return {
            "method": "registry",
            "import_succeeded": False,
            "error": f"{type(e).__name__}: {e}",
        }


def main() -> None:
    """Run both bootstrap methods and compare results."""
    walkup_result = test_walkup_bootstrap()
    registry_result = test_registry_bootstrap()

    result = {
        "continue": True,
        "message": json.dumps({
            "test": "walk-up vs registry bootstrap comparison",
            "walkup": walkup_result,
            "registry": registry_result,
            "summary": (
                "Walk-up works HERE because --plugin-dir provides "
                ".claude-plugin in ancestors. But it fails when the marker "
                "is missing (see test-walkup-fallthrough.py). Registry-based "
                "bootstrap is deterministic regardless of directory structure."
            ),
        }, indent=2),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
