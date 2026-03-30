"""Ponto de entrada principal (wizard interativo + CLI)."""

import os
import sys
import argparse
import logging

from .config import load_config
from .engine import ConversionEngine, VERSIONS, VALID_CONVERSIONS
from .utils import setup_logging
from .linter.engine import LintEngine, LintConfig
from .analyzer.engine import (
    AnalyzeEngine,
    ANALYZER_MODULES,
    format_analysis_text,
    format_analysis_json,
    format_analysis_html,
)
from .linter.reporter import format_text, format_json, format_html
from .fixer.auto_fix import (
    FixEngine,
    FixReport,
    format_fix_text,
    format_fix_json,
    FIXABLE_RULES,
)
from .doctor.engine import (
    DoctorEngine,
    DOCTOR_MODULES,
    format_doctor_text,
    format_doctor_json,
    format_doctor_html,
)
from .doctor.health_check import HEALTH_CHECKS
from .docs import (
    DocsGenerator,
    DocsReport,
    export_markdown,
    export_html,
    export_json,
    format_docs_text,
)
from .formatter import LuaFormatter, LuaFormatConfig, FormatReport, format_report_text
from .testing.runner import run_tests, format_test_report


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    banner = r"""
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   ████████╗████████╗████████╗                            ║
  ║   ╚══██╔══╝╚══██╔══╝╚══██╔══╝                            ║
  ║      ██║      ██║      ██║                                ║
  ║      ██║      ██║      ██║                                ║
  ║      ╚═╝      ╚═╝      ╚═╝                                ║
  ║                                                          ║
  ║   TFS Script Converter  v2.0                             ║
  ║   Legacy → RevScript  ·  The Forgotten Server            ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
"""
    print(banner)


def interactive_mode():
    clear_screen()
    print_banner()

    config = load_config()
    convert_cfg = config.get("convert", {})

    print("  Welcome! This tool converts TFS scripts between versions.")
    print("  Just answer a few questions and the conversion will start.\n")

    # Versão de origem
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Which TFS version are your CURRENT scripts from?  │")
    print("  │                                                     │")
    print("  │   [1] TFS 0.3.6 (Crying Damson / YurOTS-based)     │")
    print("  │   [2] TFS 0.4   (OTX 2.x / OTHire-based)          │")
    print("  │   [3] TFS 1.x   (OOP API, XML registration)        │")
    print("  │                                                     │")
    print("  └─────────────────────────────────────────────────────┘")

    source_map = {"1": "tfs03", "2": "tfs04", "3": "tfs1x"}
    source_names = {"1": "TFS 0.3.6", "2": "TFS 0.4", "3": "TFS 1.x"}
    source_num = {v: k for k, v in source_map.items()}  # reverse: tfs03 → "1"
    cfg_source = convert_cfg.get("from", "")
    cfg_source_num = source_num.get(cfg_source, "")
    cfg_source_hint = f" [press Enter for {cfg_source_num}]" if cfg_source_num else ""

    while True:
        choice = input(f"\n  Your choice [1/2/3]{cfg_source_hint}: ").strip()
        if not choice and cfg_source_num:
            choice = cfg_source_num
        if choice in source_map:
            source_version = source_map[choice]
            print(f"  ✓ Source: {source_names[choice]}")
            break
        print("  Please type 1, 2, or 3.")

    # Versão destino
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  What version do you want to CONVERT TO?           │")
    print("  │                                                     │")

    target_options = {}
    opt_num = 1
    for (src, tgt), desc in VALID_CONVERSIONS.items():
        if src == source_version:
            target_options[str(opt_num)] = tgt
            print(f"  │   [{opt_num}] {desc:<47s}│")
            opt_num += 1

    if not target_options:
        print("  │   No valid conversions for this source version!    │")
        print("  └─────────────────────────────────────────────────────┘")
        print("\n  Press Enter to exit...")
        input()
        return

    print("  │                                                     │")
    print("  └─────────────────────────────────────────────────────┘")

    cfg_target = convert_cfg.get("to", "")
    target_num = {v: k for k, v in target_options.items()}  # reverse: revscript → "1"
    cfg_target_num = target_num.get(cfg_target, "")
    options_str = "/".join(target_options.keys())
    cfg_target_hint = f" [press Enter for {cfg_target_num}]" if cfg_target_num else ""

    while True:
        choice = input(f"\n  Your choice [{options_str}]{cfg_target_hint}: ").strip()
        if not choice and cfg_target_num:
            choice = cfg_target_num
        if choice in target_options:
            target_version = target_options[choice]
            tgt_name = VERSIONS.get(target_version, target_version)
            print(f"  ✓ Target: {tgt_name}")
            break
        print(f"  Please type one of: {options_str}")

    # Pasta de entrada
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Enter the path to your INPUT scripts folder:      │")
    print("  │  (the folder with your current Lua/XML files)      │")
    print("  └─────────────────────────────────────────────────────┘")

    cfg_input = convert_cfg.get("input", "")
    input_hint = f" [{cfg_input}]" if cfg_input else ""

    while True:
        raw = input(f"\n  Input folder{input_hint}: ").strip().strip('"').strip("'")
        input_dir = raw or cfg_input
        if os.path.isdir(input_dir):
            input_dir = os.path.abspath(input_dir)
            print(f"  ✓ Input: {input_dir}")
            break
        print(f"  Folder not found: {input_dir}")
        print("  Please enter a valid folder path.")

    # Pasta de saída
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Enter the path for the OUTPUT folder:             │")
    print("  │  (where converted files will be saved)             │")
    print("  └─────────────────────────────────────────────────────┘")

    cfg_output = convert_cfg.get("output", "")
    default_output = cfg_output if cfg_output else input_dir + "_converted"
    while True:
        output_input = (
            input(f"\n  Output folder [{default_output}]: ")
            .strip()
            .strip('"')
            .strip("'")
        )
        output_dir = output_input if output_input else default_output
        output_dir = os.path.abspath(output_dir)

        if output_dir == input_dir:
            print("  Output folder must be different from input folder!")
            continue

        if os.path.exists(output_dir) and os.listdir(output_dir):
            confirm = (
                input(f"  Folder already exists. Overwrite? [y/N]: ").strip().lower()
            )
            if confirm not in ("y", "yes", "s", "sim"):
                continue

        print(f"  ✓ Output: {output_dir}")
        break

    # Dry-run?
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Would you like a dry-run first?                   │")
    print("  │  (Analyzes scripts without writing any files)      │")
    print("  │                                                     │")
    print("  │   [1] No, convert directly                         │")
    print("  │   [2] Yes, dry-run only (preview)                  │")
    print("  │                                                     │")
    print("  └─────────────────────────────────────────────────────┘")

    cfg_dry_run = convert_cfg.get("dry_run", False)
    dr_default_hint = " [config: dry-run]" if cfg_dry_run else ""
    dry_run = False
    dr_choice = input(f"\n  Your choice [1/2]{dr_default_hint}: ").strip()
    if dr_choice == "2" or (not dr_choice and cfg_dry_run):
        dry_run = True
        print("  ✓ Mode: Dry-run (preview only)")
    else:
        print("  ✓ Mode: Full conversion")

    # HTML diff?
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Generate an HTML visual diff page?                │")
    print("  │  (Side-by-side before/after comparison)            │")
    print("  │                                                     │")
    print("  │   [1] No                                           │")
    print("  │   [2] Yes, generate HTML diff                      │")
    print("  │                                                     │")
    print("  └─────────────────────────────────────────────────────┘")

    cfg_html_diff = convert_cfg.get("html_diff", False)
    hd_default_hint = " [config: yes]" if cfg_html_diff else ""
    html_diff = False
    hd_choice = input(f"\n  Your choice [1/2]{hd_default_hint}: ").strip()
    if hd_choice == "2" or (not hd_choice and cfg_html_diff):
        html_diff = True
        print("  ✓ HTML diff: Yes")
    else:
        print("  ✓ HTML diff: No")

    # Confirmação
    print()
    mode_label = "PREVIEW" if dry_run else "CONVERT"
    print("  ╔═══════════════════════════════════════════════════════╗")
    print(f"  ║  Ready to {mode_label}!{' ' * (41 - len(mode_label))}║")
    print(
        f"  ║  {VERSIONS.get(source_version, source_version):15s} → {VERSIONS.get(target_version, target_version):20s}          ║"
    )
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()

    confirm = input("  Start? [Y/n]: ").strip().lower()
    if confirm in ("n", "no", "nao", "não"):
        print("\n  Cancelled.")
        return

    print()
    setup_logging(verbose=True)

    engine = ConversionEngine(
        source_version=source_version,
        target_version=target_version,
        input_dir=input_dir,
        output_dir=output_dir,
        verbose=True,
        dry_run=dry_run,
        html_diff=html_diff,
    )

    engine.run()

    print("\n  Press Enter to exit...")
    input()


def lint_cli():
    """CLI entry point for 'ttt lint'."""
    config = load_config()
    lint_cfg = config.get("lint", {})

    parser = argparse.ArgumentParser(
        prog="ttt lint",
        description="TTT Linter — Static analyzer for TFS/OTServ Lua scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ttt lint ./data/scripts
  ttt lint ./data/scripts --format json
  ttt lint ./data/scripts --format html --output report.html
  ttt lint ./data/scripts --disable deprecated-api --disable hardcoded-id
  ttt lint script.lua
        """,
    )

    parser.add_argument("path", help="File or directory to lint")
    parser.add_argument(
        "--format",
        choices=["text", "json", "html"],
        default=lint_cfg.get("format", "text"),
        help="Output format (default: text)",
    )
    parser.add_argument("--output", "-o", help="Write report to file instead of stdout")
    parser.add_argument(
        "--disable",
        action="append",
        default=list(lint_cfg.get("disable", [])),
        help="Disable specific rules (can be used multiple times)",
    )
    parser.add_argument(
        "--enable",
        action="append",
        default=list(lint_cfg.get("enable", [])),
        help="Enable only specific rules (can be used multiple times)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=lint_cfg.get("verbose", False),
        help="Show all files including clean ones",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="List all available lint rules and exit",
    )

    args = parser.parse_args(sys.argv[2:])

    # List rules mode
    if args.list_rules:
        from .linter.rules import ALL_RULES

        print("\nAvailable lint rules:\n")
        for rule_id, rule_cls in ALL_RULES.items():
            r = rule_cls()
            print(f"  {rule_id:<30s} {r.severity.value:<8s}  {r.description}")
        print()
        return

    target_path = os.path.abspath(args.path)

    if not os.path.exists(target_path):
        print(f"ERROR: Path not found: {target_path}")
        sys.exit(1)

    setup_logging(verbose=args.verbose)

    # Load config
    config_path = LintConfig.find_config(
        target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
    )
    if config_path:
        config = LintConfig.load(config_path)
    else:
        config = LintConfig()

    # Apply CLI overrides
    if args.enable:
        config.enabled_rules = args.enable
    if args.disable:
        config.disabled_rules.extend(args.disable)

    # Run linter
    engine = LintEngine(config=config)

    if os.path.isfile(target_path):
        result = engine.lint_file(target_path)
        from .linter.engine import LintReport

        report = LintReport(
            files=[result],
            rules_used=engine.rule_ids,
            target_path=os.path.dirname(target_path),
        )
    else:
        report = engine.lint_directory(target_path)

    # Format output
    base_dir = (
        os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
    )
    use_colors = not args.no_color and args.format == "text" and not args.output

    if args.format == "json":
        output = format_json(report, base_dir)
    elif args.format == "html":
        output = format_html(report, base_dir)
    else:
        output = format_text(
            report, base_dir, use_colors=use_colors, verbose=args.verbose
        )

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to: {args.output}")
    else:
        print(output)

    # Exit code: 1 if there are errors/warnings, 0 if clean
    sys.exit(1 if report.total_errors > 0 or report.total_warnings > 0 else 0)


def fix_cli():
    """CLI entry point for 'ttt fix'."""
    config = load_config()
    fix_cfg = config.get("fix", {})

    parser = argparse.ArgumentParser(
        prog="ttt fix",
        description="TTT Auto-Fixer — Automatically fix issues in TFS/OTServ Lua scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Fixable rules:
  deprecated-api              Replace old procedural calls with OOP equivalents
  missing-return              Add 'return true' to callbacks without return
  global-variable-leak        Add 'local' before undeclared variable assignments
  deprecated-constant         Replace obsolete constant names
  invalid-callback-signature  Update callback parameter lists

Examples:
  ttt fix ./data/scripts
  ttt fix ./data/scripts --dry-run
  ttt fix ./data/scripts --diff
  ttt fix ./data/scripts --no-backup
  ttt fix script.lua --only deprecated-api deprecated-constant
        """,
    )

    cfg_fix_only = list(fix_cfg.get("only", [])) or None

    parser.add_argument("path", help="File or directory to fix")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=fix_cfg.get("dry_run", False),
        help="Preview fixes without writing changes to disk",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show unified diff of changes (before/after)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        default=not fix_cfg.get("backup", True),
        help="Do not create .bak backup files before modifying",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="RULE",
        default=cfg_fix_only,
        help="Only apply specific fix rules (e.g. --only deprecated-api deprecated-constant)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--output", "-o", help="Write report to file instead of stdout")
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output including unchanged files",
    )

    args = parser.parse_args(sys.argv[2:])

    target_path = os.path.abspath(args.path)

    if not os.path.exists(target_path):
        print(f"ERROR: Path not found: {target_path}")
        sys.exit(1)

    setup_logging(verbose=args.verbose)

    # Validate --only rule IDs
    enabled_fixes = None
    if args.only:
        invalid = [r for r in args.only if r not in FIXABLE_RULES]
        if invalid:
            print(f"ERROR: Unknown fix rule(s): {', '.join(invalid)}")
            print(f"Available: {', '.join(sorted(FIXABLE_RULES))}")
            sys.exit(1)
        enabled_fixes = args.only

    # Create fix engine
    engine = FixEngine(
        dry_run=args.dry_run,
        create_backup=not args.no_backup,
        enabled_fixes=enabled_fixes,
    )

    # Run fixer
    if os.path.isfile(target_path):
        result = engine.fix_file(target_path)
        report = FixReport(
            files=[result],
            target_path=os.path.dirname(target_path),
        )
    else:
        report = engine.fix_directory(target_path)

    # Format output
    base_dir = (
        os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
    )
    use_colors = not args.no_color and args.format == "text" and not args.output

    if args.format == "json":
        output = format_fix_json(report, base_dir)
    else:
        output = format_fix_text(
            report, base_dir, use_colors=use_colors, show_diff=args.diff
        )

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to: {args.output}")
    else:
        # Handle Windows console encoding issues
        try:
            print(output)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")

    if args.dry_run:
        print("\n  (dry-run mode -- no files were modified)")

    sys.exit(0)


def format_cli():
    """CLI entry point for 'ttt format'."""
    parser = argparse.ArgumentParser(
        prog="ttt format",
        description="TTT Formatter — Format Lua scripts with consistent style",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ttt format ./data/scripts
  ttt format ./data/scripts --check
  ttt format script.lua --indent-style tabs
  ttt format ./data/scripts --config .tttformat.json
        """
    )

    parser.add_argument(
        "path",
        help="File or directory to format"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check formatting without writing files (exit 1 if changes needed)"
    )
    parser.add_argument(
        "--config",
        help="Path to .tttformat.json configuration file"
    )
    parser.add_argument(
        "--indent-style",
        choices=["spaces", "tabs"],
        help="Override indentation style"
    )
    parser.add_argument(
        "--indent-size",
        type=int,
        help="Override indentation size (for spaces mode)"
    )

    args = parser.parse_args(sys.argv[2:])

    target_path = os.path.abspath(args.path)

    if not os.path.exists(target_path):
        print(f"ERROR: Path not found: {target_path}")
        sys.exit(1)

    if args.config:
        config = LuaFormatConfig.load(os.path.abspath(args.config))
    else:
        config_start = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        config_path = LuaFormatConfig.find_config(config_start)
        config = LuaFormatConfig.load(config_path) if config_path else LuaFormatConfig()

    if args.indent_style:
        config.indent_style = args.indent_style
    if args.indent_size is not None:
        if args.indent_size < 1:
            print("ERROR: --indent-size must be >= 1")
            sys.exit(1)
        config.indent_size = args.indent_size

    formatter = LuaFormatter(config)

    if os.path.isfile(target_path):
        result = formatter.format_file(target_path, check=args.check)
        report = FormatReport(
            files=[result],
            target_path=os.path.dirname(target_path),
            check_mode=args.check,
        )
        base_dir = os.path.dirname(target_path)
    else:
        report = formatter.format_directory(target_path, check=args.check)
        base_dir = target_path

    print(format_report_text(report, base_dir=base_dir))

    if report.files_errored > 0:
        sys.exit(1)
    if args.check and report.files_changed > 0:
        sys.exit(1)
    sys.exit(0)


def test_cli():
    """CLI entry point for 'ttt test'."""
    parser = argparse.ArgumentParser(
        prog="ttt test",
        description="TTT Test Framework — Run OTServ script tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ttt test ./tests
  ttt test ./tests --pattern test_*.py
  ttt test tests/test_ttt.py
  ttt test ./tests --quiet
        """
    )

    parser.add_argument(
        "path",
        nargs="?",
        default="tests",
        help="Test directory or single test file (default: ./tests)"
    )
    parser.add_argument(
        "--pattern",
        default="test*.py",
        help="Discovery pattern for test files (default: test*.py)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce unittest verbosity"
    )

    args = parser.parse_args(sys.argv[2:])
    target_path = os.path.abspath(args.path)

    if not os.path.exists(target_path):
        print(f"ERROR: Path not found: {target_path}")
        sys.exit(1)

    try:
        report = run_tests(
            test_path=target_path,
            pattern=args.pattern,
            verbosity=1 if args.quiet else 2,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print()
    print(format_test_report(report))
    sys.exit(report.return_code)


def cli_mode():
    config = load_config()
    convert_cfg = config.get("convert", {})

    parser = argparse.ArgumentParser(
        description="TTT — TFS Script Converter: Legacy to RevScript Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --input ./data --output ./data_converted --from tfs03 --to tfs1x
  python run.py -i ./my_server/data -o ./converted -f tfs04 -t revscript
  python run.py -i ./data -o ./output -f tfs1x -t revscript
  python run.py -i ./data -f tfs03 -t revscript --dry-run

Valid conversions:
  tfs03  → tfs1x      TFS 0.3 → TFS 1.x (API conversion)
  tfs04  → tfs1x      TFS 0.4 → TFS 1.x (API conversion)
  tfs03  → revscript   TFS 0.3 → RevScript (API + registration)
  tfs04  → revscript   TFS 0.4 → RevScript (API + registration)
  tfs1x  → revscript   TFS 1.x → RevScript (registration only)
        """,
    )

    cfg_input = convert_cfg.get("input", "")
    cfg_source = convert_cfg.get("from", "")
    cfg_target = convert_cfg.get("to", "")

    parser.add_argument(
        "-i", "--input",
        required=not bool(cfg_input),
        default=cfg_input or None,
        help="Input directory containing TFS scripts",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=False,
        default=convert_cfg.get("output", ""),
        help="Output directory for converted scripts (optional with --dry-run)",
    )
    parser.add_argument(
        "-f",
        "--from",
        dest="source",
        required=not bool(cfg_source),
        default=cfg_source or None,
        choices=["tfs03", "tfs036", "tfs04", "tfs1x", "tfs1"],
        help="Source TFS version",
    )
    parser.add_argument(
        "-t",
        "--to",
        dest="target",
        required=not bool(cfg_target),
        default=cfg_target or None,
        choices=["tfs1x", "revscript"],
        help="Target TFS version",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=convert_cfg.get("verbose", False),
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=convert_cfg.get("dry_run", False),
        help="Analyze scripts without writing files (preview mode)",
    )
    parser.add_argument(
        "--html-diff",
        action="store_true",
        default=convert_cfg.get("html_diff", False),
        help="Generate an HTML page with side-by-side visual diff (before/after)",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.output:
        parser.error("--output is required unless --dry-run is set")

    setup_logging(verbose=args.verbose)

    engine = ConversionEngine(
        source_version=args.source,
        target_version=args.target,
        input_dir=args.input,
        output_dir=args.output or "",
        verbose=args.verbose,
        dry_run=args.dry_run,
        html_diff=args.html_diff,
    )

    errors = engine.validate()
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    stats = engine.run()
    sys.exit(0 if stats["errors"] == 0 else 1)


# ---------------------------------------------------------------------------
# ttt analyze
# ---------------------------------------------------------------------------


def analyze_cli():
    """CLI entry point for 'ttt analyze'."""
    config = load_config()
    analyze_cfg = config.get("analyze", {})

    parser = argparse.ArgumentParser(
        prog="ttt analyze",
        description="TTT Server Analyzer — Full server analysis and statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Analysis modules:
  stats              General statistics (scripts, lines, functions, API style)
  dead_code          Detect unreferenced scripts, broken XML refs, unused functions
  duplicates         Find identical scripts, duplicate registrations
  storage            Scan storage IDs, find conflicts and free ranges
  item_usage         Analyze item ID usage across scripts and XML
  complexity         Cyclomatic complexity scoring and refactoring suggestions

Examples:
  ttt analyze ./data
  ttt analyze ./data --format json --output report.json
  ttt analyze ./data --format html --output analysis.html
  ttt analyze ./data --only stats complexity
  ttt analyze ./data --list-modules
        """,
    )

    cfg_only = list(analyze_cfg.get("only", [])) or None

    parser.add_argument("path", nargs="?", help="Server data directory to analyze")
    parser.add_argument(
        "--format",
        choices=["text", "json", "html"],
        default=analyze_cfg.get("format", "text"),
        help="Output format (default: text)",
    )
    parser.add_argument("--output", "-o", help="Write report to file instead of stdout")
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="MODULE",
        default=cfg_only,
        help="Only run specific modules (e.g. --only stats complexity)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=analyze_cfg.get("verbose", False),
        help="Show verbose output (all details, no truncation)",
    )
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="List all available analysis modules and exit",
    )
    parser.add_argument(
        "--use-ast",
        action="store_true",
        default=analyze_cfg.get("use_ast", False),
        help="Use AST-backed analysis for higher accuracy (requires luaparser).",
    )

    args = parser.parse_args(sys.argv[2:])

    if args.list_modules:
        print("\nAvailable analysis modules:")
        print("  stats          General statistics (scripts, lines, API style)")
        print("  dead_code      Dead code detector (orphan scripts, broken refs)")
        print(
            "  duplicates     Duplicate detector (identical scripts, dup registrations)"
        )
        print("  storage        Storage ID scanner (conflicts, free ranges)")
        print("  item_usage     Item ID usage analysis")
        print("  complexity     Cyclomatic complexity scoring")
        print()
        return

    if not args.path:
        parser.print_help()
        sys.exit(1)

    target_path = os.path.abspath(args.path)
    if not os.path.isdir(target_path):
        print(f"ERROR: Directory not found: {target_path}")
        sys.exit(1)

    setup_logging(verbose=args.verbose)

    enabled = args.only if args.only else None
    engine = AnalyzeEngine(enabled_modules=enabled, use_ast=args.use_ast)
    report = engine.analyze(target_path)

    if args.format == "json":
        output = format_analysis_json(report)
    elif args.format == "html":
        output = format_analysis_html(report)
    else:
        output = format_analysis_text(
            report, no_color=args.no_color, verbose=args.verbose
        )

    if args.output:
        out_path = os.path.abspath(args.output)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to: {out_path}")
    else:
        try:
            print(output)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")


def doctor_cli():
    """CLI entry point for 'ttt doctor'."""
    config = load_config()
    doctor_cfg = config.get("doctor", {})

    parser = argparse.ArgumentParser(
        prog="ttt doctor",
        description="TTT Server Doctor \u2014 Health check for OTServ servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Health checks:
  syntax-error          Lua syntax errors (block/bracket mismatch)
  broken-xml-ref        XML references to non-existent scripts
  conflicting-id        Duplicate item IDs in actions/movements
  duplicate-event       Duplicate event registrations (talkactions, creature events)
  npc-duplicate-keyword NPC keyword duplicates
  invalid-callback      Invalid callback signatures (wrong param count)

XML validation:
  xml-malformed         XML parse errors
  xml-missing-attr      Missing required attributes
  xml-missing-script    Script paths that don't exist

Health score:
  90-100  HEALTHY   Server is in good shape
  60-89   WARNING   Some issues need attention
  0-59    CRITICAL  Serious problems detected

Examples:
  ttt doctor ./data
  ttt doctor ./data --format json --output health.json
  ttt doctor ./data --format html --output health.html
  ttt doctor --list-checks
        """,
    )

    parser.add_argument("path", nargs="?", help="Server data directory to diagnose")
    parser.add_argument(
        "--format",
        choices=["text", "json", "html"],
        default=doctor_cfg.get("format", "text"),
        help="Output format (default: text)",
    )
    parser.add_argument("--output", "-o", help="Write report to file instead of stdout")
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=doctor_cfg.get("verbose", False),
        help="Show verbose output",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List all available health checks and exit",
    )

    args = parser.parse_args(sys.argv[2:])

    if args.list_checks:
        print("\nAvailable health checks:")
        for name, desc, _ in HEALTH_CHECKS:
            print(f"  {name:<28s} {desc}")
        print("\nXML validation checks:")
        print(f"  {'xml-malformed':<28s} XML parse errors")
        print(f"  {'xml-missing-attr':<28s} Missing required attributes")
        print(f"  {'xml-missing-script':<28s} Script paths that don't exist")
        print()
        return

    if not args.path:
        parser.print_help()
        sys.exit(1)

    target_path = os.path.abspath(args.path)
    if not os.path.isdir(target_path):
        print(f"ERROR: Directory not found: {target_path}")
        sys.exit(1)

    setup_logging(verbose=args.verbose)

    engine = DoctorEngine()
    report = engine.diagnose(target_path)

    if args.format == "json":
        output = format_doctor_json(report)
    elif args.format == "html":
        output = format_doctor_html(report)
    else:
        output = format_doctor_text(
            report, no_color=args.no_color, verbose=args.verbose, base_dir=target_path
        )

    if args.output:
        out_path = os.path.abspath(args.output)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to: {out_path}")
    else:
        try:
            print(output)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")


# ---------------------------------------------------------------------------
# ttt docs
# ---------------------------------------------------------------------------


def docs_cli():
    """CLI entry point for 'ttt docs'."""
    config = load_config()
    docs_cfg = config.get("docs", {})

    parser = argparse.ArgumentParser(
        prog="ttt docs",
        description="TTT Docs Generator — Generate server documentation automatically",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories documented:
  actions            Actions (item ID, script, description)
  movements          Movements (item/tile, type, script)
  talkactions        TalkActions (keyword, script)
  creaturescripts    CreatureScripts (event, script)
  globalevents       GlobalEvents (type, interval, script)
  npcs               NPCs (name, keywords, shop items)
  spells             Spells (name, mana, level, formula)

Output formats:
  text               Summary to terminal (default)
  markdown / md      Markdown files (index.md + per-category .md)
  html               Static HTML site with navigation and code view
  json               Single JSON file (API consumable)

Examples:
  ttt docs ./data
  ttt docs ./data --format html --output ./server-docs
  ttt docs ./data --format markdown --output ./docs
  ttt docs ./data --format json --output docs.json
  ttt docs ./data --format html --output ./server-docs --serve
        """,
    )

    parser.add_argument("path", nargs="?", help="Server data directory to document")
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "md", "html", "json"],
        default=docs_cfg.get("format", "text"),
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output", "-o",
        default=docs_cfg.get("output") or None,
        help="Output directory (for md/html) or file (for json)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=docs_cfg.get("verbose", False),
        help="Show verbose output",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        default=docs_cfg.get("serve", False),
        help="Start a local HTTP server to view HTML docs",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=docs_cfg.get("port", 8080),
        help="Port for local HTTP server (default: 8080)",
    )

    args = parser.parse_args(sys.argv[2:])

    if not args.path:
        parser.print_help()
        sys.exit(1)

    target_path = os.path.abspath(args.path)
    if not os.path.isdir(target_path):
        print(f"ERROR: Directory not found: {target_path}")
        sys.exit(1)

    setup_logging(verbose=args.verbose)

    # Generate documentation data
    gen = DocsGenerator()
    report = gen.generate(target_path)

    fmt = args.format
    if fmt == "md":
        fmt = "markdown"

    if fmt == "text":
        output = format_docs_text(report, no_color=args.no_color)
        try:
            print(output)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")
        return

    if fmt == "markdown":
        out_dir = (
            os.path.abspath(args.output)
            if args.output
            else os.path.join(os.getcwd(), "docs")
        )
        written = export_markdown(report, out_dir)
        print(f"\nGenerated Markdown documentation:")
        for p in written:
            print(f"  {os.path.relpath(p)}")
        print(f"\n  {len(written)} files written to {out_dir}")
        return

    if fmt == "html":
        out_dir = (
            os.path.abspath(args.output)
            if args.output
            else os.path.join(os.getcwd(), "docs")
        )
        written = export_html(report, out_dir)
        print(f"\nGenerated HTML documentation:")
        for p in written:
            print(f"  {os.path.relpath(p)}")
        print(f"\n  {len(written)} files written to {out_dir}")

        if args.serve:
            _serve_docs(out_dir, args.port)
        return

    if fmt == "json":
        out_path = os.path.abspath(args.output) if args.output else None
        json_str = export_json(report, out_path)
        if out_path:
            print(f"JSON documentation written to: {out_path}")
        else:
            print(json_str)
        return


def _serve_docs(directory: str, port: int):
    """Start a simple HTTP server to serve the generated HTML docs."""
    import http.server
    import functools

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=directory
    )
    print(f"\n  Serving docs at http://localhost:{port}")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        with http.server.HTTPServer(("", port), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


def main():
    # Check for subcommands first
    if len(sys.argv) > 1:
        subcommand = sys.argv[1].lower()
        if subcommand == "lint":
            lint_cli()
            return
        elif subcommand == "fix":
            fix_cli()
            return
        elif subcommand == "analyze":
            analyze_cli()
            return
        elif subcommand == "doctor":
            doctor_cli()
            return
        elif subcommand == "docs":
            docs_cli()
            return
        elif subcommand == "format":
            format_cli()
            return
        elif subcommand == "test":
            test_cli()
            return
        elif subcommand == "convert":
            # Remove the 'convert' subcommand so argparse sees the rest
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            cli_mode()
            return
        elif subcommand == "create":
            create_cli()
            return
        elif subcommand in ("-h", "--help") and len(sys.argv) == 2:
            _print_global_help()
            return
        elif subcommand == "--version":
            from . import __version__

            print(f"TTT v{__version__}")
            return
        else:
            # Legacy mode: treat as convert arguments
            cli_mode()
            return
    else:
        interactive_mode()


def _print_global_help():
    """Print help for the global TTT command."""
    print("""
    TTT — OTServer Developer Toolkit

    Usage:
        ttt                         Interactive conversion wizard
        ttt convert [args]          Convert scripts between TFS versions
        ttt lint <path> [options]   Analyze scripts for errors and bad practices
        ttt fix <path> [options]    Auto-fix common issues in scripts
        ttt analyze <path> [opts]   Full server analysis and statistics
        ttt doctor <path> [opts]   Health check \u2014 detect broken/conflicting scripts
        ttt docs <path> [opts]     Generate server documentation
        ttt format <path> [opts]   Format Lua scripts (Prettier-style)
        ttt test <path> [opts]     Run tests via TTT testing framework
        ttt create [opts]          Generate script skeletons (scaffolding)

    Create Options:
        ttt create --type <script_type>    Script type (action, movement, creaturescript, globalevent, talkaction, spell, npc)
        ttt create --name <name>           Script name (e.g. healing_potion)
        ttt create --output <path>         Output file or directory
        ttt create --format <format>       Output format (revscript, tfs1x)
        ttt create --params <params>       Extra parameters (comma-separated)

    Convert Options:
        -i, --input DIR             Input directory containing TFS scripts
        -o, --output DIR            Output directory for converted scripts
        -f, --from VERSION          Source TFS version (tfs03, tfs04, tfs1x)
        -t, --to VERSION            Target TFS version (tfs1x, revscript)
        -v, --verbose               Enable verbose logging
        --dry-run                   Preview mode (no file writes)
        --html-diff                 Generate HTML visual diff

    Lint Options:
        ttt lint <path>             Lint a file or directory
        ttt lint <path> --format json|html|text
        ttt lint --list-rules       Show all available rules
        ttt lint <path> --disable <rule>
        ttt lint <path> --output report.html

    Fix Options:
        ttt fix <path>              Fix all fixable issues
        ttt fix <path> --dry-run    Preview fixes without modifying files
        ttt fix <path> --diff       Show before/after diff
        ttt fix <path> --no-backup  Skip creating .bak backup files
        ttt fix <path> --only <rules>  Only apply specific fixes

    Analyze Options:
        ttt analyze <path>          Full server analysis
        ttt analyze <path> --format json|html|text
        ttt analyze --list-modules  Show available analysis modules
        ttt analyze <path> --only stats complexity
        ttt analyze <path> --output report.html

    Doctor Options:
        ttt doctor <path>           Run health checks on server
        ttt doctor <path> --format json|html|text
        ttt doctor --list-checks    Show available health checks
        ttt doctor <path> --output health.html

    Docs Options:
        ttt docs <path>                    Generate server documentation
        ttt docs <path> --format md|html|json
        ttt docs <path> --output ./docs    Output directory or file
        ttt docs <path> --serve            Serve HTML docs locally

    Format Options:
        ttt format <path>          Format Lua file(s) in place
        ttt format <path> --check  Verify formatting without writing
        ttt format <path> --config .tttformat.json
        ttt format <path> --indent-style tabs

    Test Options:
        ttt test ./tests                 Run discovered tests from directory
        ttt test tests/test_ttt.py       Run a single test file
        ttt test ./tests --pattern test_*.py
        ttt test ./tests --quiet         Reduce unittest verbosity

    Examples:
        ttt create --type action --name healing_potion --output ./scripts --format revscript
        ttt create --type npc --name shopkeeper --output ./npc --format tfs1x --params items,gold
        ttt convert -i ./data -o ./output -f tfs03 -t revscript
        ttt lint ./data/scripts
        ttt fix ./data/scripts --dry-run --diff
        ttt analyze ./data --format html
        ttt fix ./data/scripts --only deprecated-api deprecated-constant
        ttt test ./tests
""")


def create_cli():
    """CLI handler for 'ttt create' (script scaffolding)."""
    import argparse
    from .generator import generate_script, TEMPLATE_TYPES

    parser = argparse.ArgumentParser(
        prog="ttt create",
        description="Generate script skeletons (scaffolding)",
        add_help=True,
    )
    parser.add_argument(
        "--type", required=True, choices=TEMPLATE_TYPES, help="Script type"
    )
    parser.add_argument("--name", required=True, help="Script name")
    parser.add_argument("--output", required=True, help="Output file or directory")
    parser.add_argument(
        "--format",
        default="revscript",
        choices=["revscript", "tfs1x"],
        help="Output format",
    )
    parser.add_argument(
        "--params", default="", help="Extra parameters (comma-separated)"
    )

    args = parser.parse_args(sys.argv[2:])

    params = (
        [p.strip() for p in args.params.split(",") if p.strip()] if args.params else []
    )
    script_content, file_ext = generate_script(
        script_type=args.type, name=args.name, output_format=args.format, params=params
    )

    # Determine output path
    out_path = args.output
    if os.path.isdir(out_path):
        out_path = os.path.join(out_path, f"{args.name}.{file_ext}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    print(f"Script generated: {out_path}")


if __name__ == "__main__":
    main()
