# TTT Plugin System

TTT supports loading custom **mapping packs** and **lint/fix rule packs** from your project. This lets you extend TTT for server-specific functions and checks without forking the codebase.

## Quick Start

1. Run `ttt init` to scaffold a `ttt.project.toml`.
2. Create your plugin files (see formats below).
3. Reference them in your project config:

```toml
[plugins]
mappings = ["./custom/my_mappings.toml"]
rules = ["./custom/my_rules.py"]
```

4. TTT will automatically load these packs when running commands.

## Mapping Packs

Mapping packs are TOML files that add new function-conversion mappings. Each pack must include a `[manifest]` section and a `[mappings]` table.

### Format

```toml
[manifest]
name = "my-custom-mappings"
version = "1.0.0"
type = "mappings"
description = "Custom mappings for my server"

[mappings.getPlayerCustomPoints]
method = "getCustomPoints"
obj_type = "player"
obj_param = 0
drop_params = [0]

[mappings.setPlayerCustomPoints]
method = "setCustomPoints"
obj_type = "player"
obj_param = 0
drop_params = [0]
```

### Mapping Entry Fields

| Field | Required | Description |
|-------|----------|-------------|
| `method` | **Yes** | Target method name |
| `obj_type` | No | Object type (`player`, `creature`, `item`, etc.) |
| `obj_param` | No | Parameter index used as the object (0-based) |
| `drop_params` | No | List of parameter indices to drop |
| `chain` | No | Extra method chain (e.g., `":getId()"`) |
| `note` | No | `-- TTT:` comment to add for manual review |
| `static_class` | No | For static method calls (e.g., `Game`) |
| `stub` | No | If `true`, marks call with a review comment |

## Rule Packs

Rule packs are Python modules that define custom lint rules. Each pack must expose a `RULES` dict mapping rule IDs to `LintRule` subclasses.

### Format

```python
from ttt.linter.rules import LintRule, LintIssue, LintSeverity

class MyCustomRule(LintRule):
    rule_id = "custom-my-check"
    description = "Description of what this rule checks"
    severity = LintSeverity.WARNING

    def check(self, code, lines, filename=""):
        issues = []
        for i, line in enumerate(lines, 1):
            if "something_bad" in line:
                issues.append(LintIssue(
                    line=i,
                    column=1,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message="Found something bad",
                ))
        return issues

RULES = {
    "custom-my-check": MyCustomRule,
}
```

### Requirements

- Each class must inherit from `ttt.linter.rules.LintRule`
- The class `rule_id` attribute must match its key in the `RULES` dict
- The `check()` method receives `(code, lines, filename)` and returns `List[LintIssue]`

## Manifest Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | **Yes** | Unique pack name |
| `version` | No | Semantic version string |
| `type` | **Yes** | `"mappings"` or `"rules"` |
| `description` | No | Human-readable description |

## Conflict Handling

If two packs define the same mapping key or rule ID, TTT logs an error but continues loading. The last-loaded value wins. Check `PluginLoader.errors` for conflict details.

## Error Handling

Invalid packs fail safely:
- Missing files → `PluginError` with clear path
- Parse errors → `PluginError` with parser message
- Invalid manifest → `PluginError` describing what's wrong
- Invalid rule class → `PluginError` naming the offending class

All errors are collected (not raised) when using `PluginLoader.load_all()`, so one bad pack doesn't prevent other packs from loading.

## Examples

See `examples/plugins/` for working examples:
- `custom_mappings.toml` — Mapping pack with 3 custom function conversions
- `custom_rules.py` — Rule pack with a `print()` detection rule

## Programmatic API

```python
from ttt.plugins import PluginLoader
from ttt.init.scaffold import load_project_config

config = load_project_config(".")
loader = PluginLoader(config)
loader.load_all()

# Access loaded extensions
print(loader.extra_mappings)  # dict of function_name → mapping
print(loader.extra_rules)     # dict of rule_id → LintRule class
print(loader.errors)          # list of error messages
```
