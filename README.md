# Plugin Import Error Reproduction

Minimal case demonstrating a bug in Claude Code plugin hook bootstrapping
where hooks silently fail to resolve their plugin root directory.

## The Bug (Fixed)

Plugin hooks used a "walk-up" pattern to find their plugin root:

```python
plugin_root = Path(__file__).resolve().parent
while not (plugin_root / ".claude-plugin").exists() and plugin_root != plugin_root.parent:
    plugin_root = plugin_root.parent

sys.path.insert(0, str(plugin_root / "python"))
```

**The flaw**: When `.claude-plugin` wasn't found in any ancestor (e.g., due to
cache structure mismatch), the loop silently reached `/`. Then
`sys.path.insert(0, "/python/")` injected a nonexistent path, causing
`ModuleNotFoundError` for every plugin import.

**Symptoms observed**:
- `No module named 'skill_invocation_tracker'`
- `No module named 'file_metadata'`
- `No module named 'yaml_config_cache'`
- Errors shifted between different modules on each tool call (non-deterministic)

## The Fix

Replaced walk-up with direct `installed_plugins.json` registry lookup
(kitaekatt-plugins commit `af3e53f`):

```python
_registry = Path.home() / ".claude/plugins/installed_plugins.json"
with open(_registry) as _f:
    _plugins = json.loads(_f.read())["plugins"]

def _add_plugin(pid, sub="python"):
    p = str(Path(_plugins[pid][0]["installPath"]) / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

_add_plugin("plugins-kit@kitaekatt-plugins")
```

This is deterministic — no filesystem walking, no silent fallthrough.

## Directory Structure

```
plugin-import-error/
├── .claude-plugin/
│   └── marketplace.json           # Marketplace manifest
├── plugins/
│   ├── base-plugin/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json        # Minimal manifest
│   │   └── python/
│   │       └── base_module.py     # Simple importable module
│   └── import-plugin/
│       ├── .claude-plugin/
│       │   └── plugin.json        # Manifest
│       ├── python/
│       │   └── import_plugin_resolver.py  # Both resolver patterns
│       └── hooks/
│           ├── hooks.json         # Hook registration
│           └── pretooluse/
│               ├── test-import.py              # Side-by-side comparison
│               └── test-walkup-fallthrough.py  # Isolated bug repro
└── README.md
```

## Reproduction

### test-walkup-fallthrough.py (isolated bug demo)

This hook simulates running from `/tmp/no-plugin-marker-here` — a path
with no `.claude-plugin` in any ancestor. The walk-up reaches `/` and
the import fails.

**Expected output**:
```json
{
  "bug_reproduced": true,
  "walked_up_to": "/",
  "would_inject_path": "/python",
  "import_error": "No module named 'base_module'"
}
```

### test-import.py (comparison test)

Runs both bootstrap methods side-by-side:
- **Walk-up**: Works when `.claude-plugin` exists in ancestors (e.g., via
  `--plugin-dir`), fails when it doesn't
- **Registry**: Always works if plugins are in `installed_plugins.json`

### To run as Claude Code hooks

1. Start Claude Code with: `claude --plugin-dir ~/Dev/plugin-import-error/plugins/import-plugin`
2. Use any tool — PreToolUse hooks fire
3. Hook output shows bug reproduction and comparison results

### To run standalone

```bash
echo '{}' | python3 plugins/import-plugin/hooks/pretooluse/test-walkup-fallthrough.py
echo '{}' | python3 plugins/import-plugin/hooks/pretooluse/test-import.py
```

## What This Proves

| Pattern | Behavior | Failure Mode |
|---------|----------|--------------|
| Walk-up | Search ancestors for `.claude-plugin` | Silent fallthrough to `/` |
| Registry | Read `installed_plugins.json` directly | Explicit `FileNotFoundError` |

The walk-up pattern is fragile because it depends on directory structure.
The registry pattern is deterministic because it reads from a known location.

## Environment

- Fixed in: kitaekatt-plugins commit `af3e53f`
- Issue: `dev/issues/fix-session-lifecycle-kit-import-errors.md`
- Python: 3.12+
- OS: Linux (Ubuntu)
