# TTT Release Quality Checklist

Pre-release verification for TTT versions.

## Automated (CI)

- [ ] All tests pass on Windows and Linux (`pytest tests/`)
- [ ] Lint passes (`ruff check ttt/ tests/`)
- [ ] Format passes (`ruff format --check ttt/ tests/`)
- [ ] Benchmark runs against `examples/tfs03_input` corpus
- [ ] No conversion errors in benchmark
- [ ] Golden comparison match rate ≥ current baseline

## Manual

- [ ] `ttt --help` shows all subcommands
- [ ] `ttt convert` wizard completes successfully
- [ ] `ttt migrate-server` produces full migration bundle
- [ ] `ttt review` generates HTML report with correct categories
- [ ] `ttt benchmark` produces machine-readable JSON output
- [ ] Review HTML report opens correctly in browser
- [ ] Migration summary markdown renders correctly

## Benchmark Baseline Metrics

Track these across releases:

| Metric | Baseline | Current |
|--------|----------|---------|
| Files converted | — | — |
| Review markers | — | — |
| Unrecognized calls | — | — |
| Golden match rate | — | — |
| Benchmark duration | — | — |

## Expanding Benchmark Coverage

1. Add new corpus entries under `examples/` or a dedicated `benchmarks/` directory
2. Each corpus needs an `input/` directory with source scripts
3. Optionally add an `expected/` directory with golden reference outputs
4. Run `ttt benchmark -i <corpus>/input -f <ver> -t <ver> --golden <corpus>/expected`
5. Compare JSON output against previous run to detect regressions
6. Add new corpora to CI workflow matrix for automated tracking
