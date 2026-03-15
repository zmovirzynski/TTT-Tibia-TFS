# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TTT (Tibia TFS Transpiler) converts Lua scripts between TFS (The Forgotten Server) versions. It transforms API calls, function signatures, constants, and XML registrations. Zero external dependencies (Python stdlib only, Python 3.7+).

**Valid conversion paths:** tfs03→tfs1x, tfs03→revscript, tfs04→tfs1x, tfs04→revscript, tfs1x→revscript.

## Common Commands

```bash
# Run tests
python -m pytest tests/test_ttt.py -v

# Run a single test class
python -m pytest tests/test_ttt.py::TestLuaTransformer -v

# Run a single test
python -m pytest tests/test_ttt.py::TestLuaTransformer::test_basic_function_conversion -v

# Lint/format (ruff is used)
ruff check ttt/ tests/
ruff format ttt/ tests/

# Run the tool (interactive wizard)
python run.py

# Run via CLI
python run.py -i INPUT -o OUTPUT -f tfs03 -t revscript [--dry-run] [--html-diff] [-v]
```

## Architecture

The conversion pipeline flows: `run.py` → `ttt.main` (CLI/wizard) → `ConversionEngine` (orchestrator) → transformers.

### ConversionEngine (`ttt/engine.py`)
Orchestrates the full pipeline: scans input directory structure, applies the right transformers based on source→target versions, generates reports.

### Transformers (`ttt/converters/`)
- **LuaTransformer** (`lua_transformer.py`) — Regex-based Lua API conversion. Runs a 5-stage pipeline: signatures → variable renames → function calls → constants → positions. This is the primary production transformer.
- **XmlToRevScriptConverter** (`xml_to_revscript.py`) — Converts XML registrations (actions, movements, talkactions, creaturescripts, globalevents) into RevScript-style Lua registration code.
- **NpcConverter** (`npc_converter.py`) — Converts NPC XML metadata + Lua scripts.
- **ASTLuaTransformer** (`ast_lua_transformer.py`) — POC AST-based transformer using `luaparser`. Falls back to regex on parse failure. Uses `ScopeAnalyzer` and `ASTTransformVisitor`.

### Mappings (`ttt/mappings/`)
Data-driven conversion tables:
- `tfs03_functions.py` / `tfs04_functions.py` — Function call mappings (182+ / 204+ entries). Each entry specifies type (`method`/`static`/`rename`), parameter mapping, and target object/method.
- `signatures.py` — 23 callback signature transformations (e.g., `onUse` old→new params) plus parameter rename map (e.g., `cid`→`player`).
- `constants.py` — 243 constant replacements (booleans, talk types, message types, etc.).
- `xml_events.py` — XML event type mappings.

### Supporting Modules
- **scanner.py** — Detects TFS directory structure (finds XML configs and script directories).
- **report.py** — Per-file confidence scoring (HIGH ≥95%, MEDIUM ≥75%, LOW ≥50%, REVIEW <50%). Tracks conversions, warnings, unrecognized calls. Outputs `conversion_report.txt`.
- **diff_html.py** — Generates side-by-side HTML diff of before/after.

## Key Patterns

- Function mappings use a dict structure with `type`, `params_old`, `object`, `method`, `params_new` keys. When adding new mappings, follow this structure.
- The transformer marks uncertain conversions with `-- TTT:` comments for manual review.
- `LuaTransformer.transform(code, filename)` returns converted code and updates internal `stats`/`warnings`.
- The tool is installed as console script `ttt` via setup.py entry point `ttt.main:main`.
