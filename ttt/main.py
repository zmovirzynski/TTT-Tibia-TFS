"""Ponto de entrada principal (wizard interativo + CLI)."""

import os
import sys
import argparse
import logging

from .engine import ConversionEngine, VERSIONS, VALID_CONVERSIONS
from .utils import setup_logging
from .analyzers.oop_analyzer import OopAnalyzer
from .analyzers.guidelines_generator import GuidelinesGenerator


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


def _run_guidelines_wizard():
    ttt_root = os.path.dirname(os.path.abspath(__file__))
    print("\n  Analyzing TTT source files...")
    analyzer = OopAnalyzer()
    analyses = analyzer.analyze_project(ttt_root)

    generator = GuidelinesGenerator()
    content = generator.generate(analyses, ttt_root)

    output_path = os.path.join(os.getcwd(), "oop_guidelines.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    total_issues = sum(len(a.issues) for a in analyses)
    files_with_issues = sum(1 for a in analyses if a.issues)
    print(f"\n  ✓ Guidelines written to: {output_path}")
    print(f"  ✓ {files_with_issues} files with issues, {total_issues} total issues found.")
    print("\n  Press Enter to exit...")
    input()


def interactive_mode():
    clear_screen()
    print_banner()

    print("  Welcome! This tool converts TFS scripts between versions.\n")

    print("  ┌───────────────────────────────────────────────────────┐")
    print("  │  What would you like to do?                          │")
    print("  │                                                       │")
    print("  │   [1] Convert TFS scripts                            │")
    print("  │   [2] Generate LLM refactoring guidelines            │")
    print("  │                                                       │")
    print("  └───────────────────────────────────────────────────────┘")

    while True:
        mode_choice = input("\n  Your choice [1/2]: ").strip()
        if mode_choice == "1":
            break
        if mode_choice == "2":
            _run_guidelines_wizard()
            return
        print("  Please type 1 or 2.")

    print()
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

    while True:
        choice = input("\n  Your choice [1/2/3]: ").strip()
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

    while True:
        options_str = "/".join(target_options.keys())
        choice = input(f"\n  Your choice [{options_str}]: ").strip()
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

    while True:
        input_dir = input("\n  Input folder: ").strip().strip('"').strip("'")
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

    default_output = input_dir + "_converted"
    while True:
        output_input = input(f"\n  Output folder [{default_output}]: ").strip().strip('"').strip("'")
        output_dir = output_input if output_input else default_output
        output_dir = os.path.abspath(output_dir)

        if output_dir == input_dir:
            print("  Output folder must be different from input folder!")
            continue

        if os.path.exists(output_dir) and os.listdir(output_dir):
            confirm = input(f"  Folder already exists. Overwrite? [y/N]: ").strip().lower()
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

    dry_run = False
    dr_choice = input("\n  Your choice [1/2]: ").strip()
    if dr_choice == "2":
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

    html_diff = False
    hd_choice = input("\n  Your choice [1/2]: ").strip()
    if hd_choice == "2":
        html_diff = True
        print("  ✓ HTML diff: Yes")
    else:
        print("  ✓ HTML diff: No")

    # Confirmação
    print()
    mode_label = "PREVIEW" if dry_run else "CONVERT"
    print("  ╔═══════════════════════════════════════════════════════╗")
    print(f"  ║  Ready to {mode_label}!{' ' * (41 - len(mode_label))}║")
    print(f"  ║  {VERSIONS.get(source_version, source_version):15s} → {VERSIONS.get(target_version, target_version):20s}          ║")
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


def cli_mode():
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
        """
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input directory containing TFS scripts"
    )
    parser.add_argument(
        "-o", "--output",
        required=False,
        default="",
        help="Output directory for converted scripts (optional with --dry-run)"
    )
    parser.add_argument(
        "-f", "--from",
        dest="source",
        required=True,
        choices=["tfs03", "tfs036", "tfs04", "tfs1x", "tfs1"],
        help="Source TFS version"
    )
    parser.add_argument(
        "-t", "--to",
        dest="target",
        required=True,
        choices=["tfs1x", "revscript"],
        help="Target TFS version"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze scripts without writing files (preview mode)"
    )
    parser.add_argument(
        "--html-diff",
        action="store_true",
        help="Generate an HTML page with side-by-side visual diff (before/after)"
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


def main():
    if len(sys.argv) > 1:
        cli_mode()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
