# Next Sprints Plan - 2026-04-01

## Planning assumptions

This sprint plan assumes:

- 2-week sprints
- 1 to 3 engineers on the core Python codebase
- 1 engineer can also touch the VS Code extension when needed
- the team wants to maximize product leverage, not just ship isolated features

Primary goal for the next cycle:

"Turn TTT from a strong toolkit into a guided migration platform with measurable quality."

---

## Priority order

1. Hero flow for server migration
2. Review workflow for residual manual work
3. Benchmark and CI foundation
4. Team workflow and editor integration
5. Extensibility layer

---

## Sprint 1 - Migrator Foundations

### Goal

Create the foundation for `ttt migrate-server` without trying to ship the full end-to-end experience in one jump.

### Deliverables

- migration pipeline orchestrator design
- config model for multi-step execution
- execution state and step summary model
- CLI stub for `ttt migrate-server`

### Tasks

- [x] Add `ttt migrate-server` command entry point in `ttt/main.py`
- [x] Create `ttt/migrator/` package with orchestrator skeleton
- [x] Define pipeline steps: `convert`, `fix`, `analyze`, `doctor`, `docs`
- [x] Define a `MigrationRunReport` structure with per-step status, duration, outputs and summary
- [x] Define a `MigrationConfig` structure for selecting steps and output locations
- [x] Support dry-run orchestration mode for the whole migration flow
- [x] Add basic terminal summary for a migration run
- [x] Add unit tests for orchestration and config parsing
- [x] Document the intended contract in a dedicated developer doc

### Definition of Done

- `ttt migrate-server --help` exists
- migration pipeline can execute selected steps in order
- run report is serialized cleanly
- tests cover successful and failed step orchestration

### Notes

This sprint is about architecture and safe execution shape, not polish.

---

## Sprint 2 - Migrator MVP

### Goal

Ship the first real "hero flow" that a user can run on a server directory.

### Deliverables

- usable `ttt migrate-server` MVP
- backup/snapshot before execution
- output folder strategy
- final executive summary

### Tasks

- [x] Add pre-run backup or snapshot mode
- [x] Add output workspace layout for migrated results and generated artifacts
- [x] Execute `convert`, `fix`, `analyze`, `doctor` and `docs` from a single command
- [x] Add failure handling so one failed step does not corrupt the whole run state
- [x] Add final summary with:
- [x] health/risk score
- [x] number of converted files
- [x] number of `-- TTT:` markers
- [x] doctor issues
- [x] paths to reports/docs
- [x] Add markdown export for migration summary
- [x] Add integration test using `examples/`

### Definition of Done

- user can run one command and get a reviewable migration bundle
- backup is created before mutation when not in dry-run
- final summary points to all generated artifacts
- at least one integration path is tested end to end

### Notes

This sprint creates the main demo story for the product.

---

## Sprint 3 - Review Workbench

### Goal

Reduce friction around the manual review that remains after conversion.

### Deliverables

- `ttt review` command
- aggregation of residual review markers
- categorized review report

### Tasks

- [x] Add `ttt review` command entry point
- [x] Scan conversion outputs for `-- TTT:` markers and related warnings
- [x] Group findings by category:
- [x] API replacement needed
- [x] object unwrapping
- [x] unsupported legacy behavior
- [x] custom game-specific function
- [x] confidence/risk bucket
- [x] Include source file, transformed file and snippet context
- [x] Add HTML output for review report
- [x] Add JSON output for downstream tooling
- [x] Add "top blockers" section for fastest human triage
- [x] Link review report from `migrate-server` summary
- [x] Add tests for parser and grouping logic

### Definition of Done

- `ttt review <path>` works on converted output
- report is readable in terminal and HTML
- findings are grouped in a way that helps a human review efficiently
- `migrate-server` can point to the generated review report

### Notes

This sprint closes the gap between automation and human approval.

---

## Sprint 4 - Benchmark and CI Baseline

### Goal

Start proving product quality with data, not just feature coverage.

### Deliverables

- benchmark command skeleton
- official corpus layout
- CI for Python on Windows and Linux

### Tasks

- [x] Add `ttt benchmark` command entry point
- [x] Define corpus structure for benchmark fixtures
- [x] Add golden input/output test strategy
- [x] Track benchmark metrics:
- [x] files converted
- [x] review markers count
- [x] unrecognized calls count
- [x] step success/failure
- [x] time to run
- [x] Add machine-readable benchmark output
- [x] Create GitHub Actions workflow for Python tests on Windows and Linux
- [x] Run lint/test smoke on pull requests
- [x] Add release-quality checklist doc

### Definition of Done

- CI runs automatically on PRs
- benchmark command can run against at least one curated corpus
- benchmark output is stable enough to compare versions
- team has a documented path to expand benchmark coverage

### Notes

This sprint is what starts building the product moat.

---

## Sprint 5 - Dashboard and Reports 2.0

### Goal

Turn generated artifacts into a much stronger review and management experience.

### Deliverables

- unified HTML dashboard for migration runs
- linked cards for convert/fix/analyze/doctor/review/docs outputs
- improved visual triage

### Tasks

- [x] Design a single HTML landing page for migration outputs
- [x] Add summary cards for:
- [x] conversion status
- [x] review markers
- [x] doctor issues
- [x] analysis issues
- [x] benchmark snapshot
- [x] Add file-level table with filtering and severity badges
- [x] Link into diff HTML and review details
- [x] Add trend placeholders for future regression history
- [x] Make output work on desktop and laptop resolutions
- [x] Add smoke test for HTML generation

### Definition of Done

- `migrate-server` produces one primary dashboard entry point
- a user can navigate the whole run from the dashboard
- report layout is good enough for demos and stakeholder review

### Notes

This sprint improves perceived product quality a lot.

---

## Sprint 6 - Team Workflow and VS Code Pro Foundations

### Goal

Move from migration-only value to recurring day-to-day developer value.

### Deliverables

- `ttt init`
- project manifest
- first VS Code workflow upgrades

### Tasks

- [x] Add `ttt init` command to scaffold local config and workspace conventions
- [x] Create `ttt.project.toml` format for project profiles
- [x] Add profile support for common migration modes
- [x] Add preset loading for CLI commands
- [x] Add VS Code command for "Run migrate-server"
- [x] Add VS Code command for "Open latest migration dashboard"
- [x] Add navigator for `-- TTT:` review markers
- [x] Add TypeScript test setup for extension commands
- [x] Document workspace setup flow in README or extension docs

### Definition of Done

- new project setup is faster and repeatable
- extension can trigger the new hero flow
- extension has at least minimal automated test coverage

### Notes

This sprint starts the shift from one-off utility to everyday tooling.

---

## Sprint 7 - Extensibility Foundations

### Goal

Prepare the codebase for community and team-specific extensions.

### Deliverables

- plugin architecture proposal implemented at minimum viable level
- custom mappings pack loading
- custom lint/fix rules loading

### Tasks

- [x] Define plugin loading model
- [x] Define manifest format for custom packs
- [x] Add support for loading extra mapping packs from project config
- [x] Add support for loading extra lint/fix rules from a configured path
- [x] Add validation and error reporting for invalid packs
- [x] Add examples of one custom mapping pack and one custom rule pack
- [x] Add docs for extension points
- [x] Add tests for pack discovery and conflict handling

### Definition of Done

- project can extend mappings without forking TTT
- project can add at least one custom rule pack
- invalid plugins fail safely with clear messages

### Notes

This sprint is strategic. It opens the path to ecosystem growth.

---

## Backlog after Sprint 7

These should stay queued until the first 7 sprints are in good shape:

- [x] `ttt convert --explain`
- [x] transformation confidence per rule
- [x] richer AST-assisted guidance
- [x] release-over-release benchmark trend reports
- [x] fully implemented NPC conversation analyzer
- [ ] community plugin registry

---

## Suggested ticket labels

To keep execution clean, use these labels:

- `epic:migrator`
- `epic:review`
- `epic:benchmark`
- `epic:dashboard`
- `epic:vscode`
- `epic:plugins`
- `type:cli`
- `type:html`
- `type:test`
- `type:docs`
- `type:dx`
- `priority:p0`
- `priority:p1`
- `priority:p2`

---

## Suggested ownership split

If the team is small:

- Engineer 1: CLI + orchestrator + Python reports
- Engineer 2: benchmark + CI + tests
- Engineer 3: HTML dashboard + VS Code extension

If the team is only one person:

- do Sprints 1, 2 and 3 first
- only start Sprint 4 after the hero flow is stable

---

## Recommendation

If we want the highest leverage path, the best next 3 sprints are:

1. Sprint 1 - Migrator Foundations
2. Sprint 2 - Migrator MVP
3. Sprint 3 - Review Workbench

That sequence creates a true flagship workflow fast, and everything after that compounds on top of it.
