# Migrator — Developer Documentation

## Overview

The **migrator** module (`ttt/migrator/`) implements the `ttt migrate-server` command — a single-command pipeline that orchestrates the full server migration workflow.

## Pipeline Steps

The pipeline runs these steps **in order**:

| Step      | Engine                  | Description                                      |
|-----------|-------------------------|--------------------------------------------------|
| `convert` | `ConversionEngine`      | Convert Lua/XML scripts between TFS versions     |
| `fix`     | `FixEngine`             | Auto-fix common issues in converted scripts      |
| `analyze` | `AnalyzeEngine`         | Run stats, dead code, duplicates, complexity      |
| `doctor`  | `DoctorEngine`          | Health check: broken refs, conflicts, syntax      |
| `docs`    | `DocsGenerator`         | Generate server documentation (Markdown)          |

Each step is **independently failable** — a failure in one step does not prevent subsequent steps from running or corrupt the overall state.

## Architecture

```
ttt/migrator/
├── __init__.py          # Public API re-exports
├── config.py            # MigrationConfig dataclass
├── models.py            # StepResult, StepStatus, MigrationRunReport
└── orchestrator.py      # MigrationOrchestrator + format_migration_summary
```

### MigrationConfig

Controls what the pipeline does:

- `input_dir` / `output_dir` — paths
- `source_version` / `target_version` — for the convert step
- `enabled_steps` — run only these steps (default: all)
- `skip_steps` — skip these steps
- `dry_run` — no file writes
- `step_options` — per-step overrides (reserved for Sprint 2+)

The `.validate()` method returns a list of errors (empty = valid). The orchestrator calls it before running.

### MigrationRunReport

Contains full execution results:

- Per-step `StepResult` with status, duration, outputs dict, and summary string
- `StepStatus` enum: `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `SKIPPED`
- `.to_dict()` for JSON serialization
- `.success` — True if zero steps failed

### MigrationOrchestrator

The main execution driver:

```python
from ttt.migrator import MigrationConfig, MigrationOrchestrator

config = MigrationConfig(
    input_dir="./data",
    output_dir="./migrated",
    source_version="tfs03",
    target_version="revscript",
)
orch = MigrationOrchestrator(config)
report = orch.run()

print(report.success)          # True/False
print(report.steps_succeeded)  # int
```

## CLI Usage

```bash
# Full migration
ttt migrate-server -i ./data -o ./migrated -f tfs03 -t revscript

# Dry-run (no file writes)
ttt migrate-server -i ./data -f tfs03 -t revscript --dry-run

# Only specific steps
ttt migrate-server -i ./data -o ./migrated -f tfs03 -t revscript --only convert fix

# Skip steps
ttt migrate-server -i ./data -o ./migrated -f tfs03 -t revscript --skip docs

# JSON report output
ttt migrate-server -i ./data -o ./migrated -f tfs03 -t revscript --json
```

## Step Behavior

### convert
- Uses `ConversionEngine` from `ttt/engine.py`
- Requires `source_version` and `target_version`
- Writes converted files to `output_dir`
- In dry-run, only analyzes without writing

### fix
- Uses `FixEngine` from `ttt/fixer/auto_fix.py`
- Operates on `output_dir` (post-conversion) or `input_dir` (dry-run)
- No backup files inside migration output (clean workspace)

### analyze
- Uses `AnalyzeEngine` from `ttt/analyzer/engine.py`
- Runs all analysis modules (stats, dead_code, duplicates, storage, item_usage, complexity)
- Reports total issues found

### doctor
- Uses `DoctorEngine` from `ttt/doctor/engine.py`
- Produces health score (0-100) and rating (HEALTHY/WARNING/CRITICAL)

### docs
- Uses `DocsGenerator` from `ttt/docs/`
- In non-dry-run, exports Markdown to `output_dir/docs/`
- In dry-run, only counts entries

## Testing

```bash
python -m pytest tests/test_migrator.py -v
```

Tests cover:
- Config validation (missing fields, unknown steps, dry-run)
- Step selection (enabled, skipped, ordering)
- Report model (serialization, status tracking)
- Orchestrator execution (dry-run, single step, failure isolation)
- Terminal summary formatting
