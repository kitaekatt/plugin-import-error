"""Plugin resolver demonstrating both buggy and fixed import patterns.

Walk-up pattern (buggy): Searches up directory tree for .claude-plugin marker.
Registry pattern (fixed): Reads installed_plugins.json directly.
"""
import json
import sys
from pathlib import Path

_INSTALLED_PLUGINS = Path.home() / ".claude/plugins/installed_plugins.json"


# === BUGGY PATTERN: Walk-up resolver ===

def get_plugin_path_walkup(hook_file: Path) -> Path:
    """Find plugin root by walking up from hook file (THE BUG).

    Silently falls through to / if .claude-plugin marker not found,
    returning an invalid path.
    """
    plugin_root = hook_file.parent
    while not (plugin_root / ".claude-plugin").exists() and plugin_root != plugin_root.parent:
        plugin_root = plugin_root.parent
    return plugin_root


# === FIXED PATTERN: Registry resolver ===

def get_plugin_path(plugin_id: str) -> Path:
    """Get plugin path from installed_plugins.json registry (THE FIX).

    Deterministic — reads from known location, no filesystem walking.
    """
    if not _INSTALLED_PLUGINS.exists():
        raise FileNotFoundError(
            f"Plugin registry not found: {_INSTALLED_PLUGINS}\n"
            f"Path.home() = {Path.home()}\n"
            f"File exists check failed"
        )

    with open(_INSTALLED_PLUGINS) as f:
        data = json.load(f)

    if plugin_id not in data["plugins"]:
        raise ImportError(f"Plugin not installed: {plugin_id}")

    return Path(data["plugins"][plugin_id][0]["installPath"])


def import_plugin(plugin_id: str, subpath: str = "") -> None:
    """Add a plugin's path to sys.path for importing (uses registry)."""
    plugin_path = get_plugin_path(plugin_id)
    import_path = plugin_path / subpath if subpath else plugin_path

    if not import_path.exists():
        raise ImportError(f"Plugin path does not exist: {import_path}")

    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))
