"""
Main conversion engine - Orchestrates the full conversion process.
"""

import os
import re
import shutil
import logging
import time
from typing import Dict, List, Optional

from .scanner import scan_directory, ScanResult
from .converters.lua_transformer import LuaTransformer
from .converters.xml_to_revscript import XmlToRevScriptConverter
from .converters.npc_converter import NpcConverter
from .converters.explain import ExplainReport
from .converters.ast_guidance import GuidanceReport, analyze_converted_code
from .diff_html import HtmlDiffGenerator, DiffEntry
from .mappings.tfs03_functions import TFS03_TO_1X
from .mappings.tfs04_functions import TFS04_TO_1X
from .report import ConversionReport, FileReport
from .utils import (
    read_file_safe,
    write_file_safe,
    ensure_dir,
    relative_path,
)

# Try to import AST transformer (with fallback for backward compatibility)
try:
    from .converters.ast_lua_transformer import ASTLuaTransformer

    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False
    ASTLuaTransformer = None

logger = logging.getLogger("ttt")

# Version identifiers
VERSIONS = {
    "tfs03": "TFS 0.3.6",
    "tfs036": "TFS 0.3.6",
    "tfs04": "TFS 0.4",
    "tfs1": "TFS 1.x",
    "tfs1x": "TFS 1.x",
    "revscript": "TFS 1.3+ (RevScript)",
}

VALID_CONVERSIONS = {
    ("tfs03", "tfs1x"): "TFS 0.3 → TFS 1.x (API conversion)",
    ("tfs036", "tfs1x"): "TFS 0.3.6 → TFS 1.x (API conversion)",
    ("tfs04", "tfs1x"): "TFS 0.4 → TFS 1.x (API conversion)",
    ("tfs03", "revscript"): "TFS 0.3 → RevScript (API + registration)",
    ("tfs036", "revscript"): "TFS 0.3.6 → RevScript (API + registration)",
    ("tfs04", "revscript"): "TFS 0.4 → RevScript (API + registration)",
    ("tfs1x", "revscript"): "TFS 1.x → RevScript (registration only)",
    ("tfs1", "revscript"): "TFS 1.x → RevScript (registration only)",
}


def _normalize_version(version: str) -> str:
    """Normalize a version string to a canonical key."""
    v = version.lower().replace(".", "").replace(" ", "")
    if v in ("tfs036", "tfs03", "03", "036"):
        return "tfs03"
    if v in ("tfs04", "04"):
        return "tfs04"
    if v in ("tfs1", "tfs1x", "1", "1x", "10", "12", "13"):
        return "tfs1x"
    if v in ("revscript", "rev", "rs"):
        return "revscript"
    return v


class ConversionEngine:
    def __init__(
        self,
        source_version: str,
        target_version: str,
        input_dir: str,
        output_dir: str = "",
        verbose: bool = False,
        dry_run: bool = False,
        html_diff: bool = False,
        explain: bool = False,
    ):

        self.source_version = _normalize_version(source_version)
        self.target_version = _normalize_version(target_version)
        self.input_dir = os.path.abspath(input_dir)
        self.output_dir = os.path.abspath(output_dir) if output_dir else ""
        self.verbose = verbose
        self.dry_run = dry_run
        self.html_diff = html_diff
        self.explain = explain
        self.explain_report: Optional[ExplainReport] = (
            ExplainReport() if explain else None
        )
        self.guidance_report = GuidanceReport()

        # Select function mapping
        if self.source_version == "tfs03":
            self.function_map = TFS03_TO_1X
        elif self.source_version == "tfs04":
            self.function_map = TFS04_TO_1X
        else:
            self.function_map = {}

        # Stats
        self.stats = {
            "lua_files_processed": 0,
            "xml_files_processed": 0,
            "revscripts_generated": 0,
            "errors": 0,
            "warnings": 0,
            "total_functions_converted": 0,
            "defensive_checks_added": 0,
            "time_elapsed": 0.0,
        }

    def validate(self) -> List[str]:
        errors = []

        if not os.path.isdir(self.input_dir):
            errors.append(f"Input directory does not exist: {self.input_dir}")

        key = (self.source_version, self.target_version)
        if key not in VALID_CONVERSIONS:
            valid = "\n  ".join(
                f"{k[0]} → {k[1]}: {v}" for k, v in VALID_CONVERSIONS.items()
            )
            errors.append(
                f"Invalid conversion: {self.source_version} → {self.target_version}\n"
                f"Valid conversions:\n  {valid}"
            )

        if not self.dry_run:
            if not self.output_dir:
                errors.append("Output directory is required (unless using --dry-run)")
            elif self.input_dir == self.output_dir:
                errors.append("Input and output directories must be different!")

        return errors

    def run(self) -> Dict:
        start_time = time.time()

        src_label = VERSIONS.get(self.source_version, self.source_version)
        tgt_label = VERSIONS.get(self.target_version, self.target_version)
        self.report = ConversionReport(
            src_label, tgt_label, self.input_dir, self.output_dir
        )

        mode_label = "DRY RUN" if self.dry_run else "CONVERSION"
        logger.info("=" * 60)
        logger.info(f"  TTT — TFS Script Converter v2.0  [{mode_label}]")
        logger.info("=" * 60)
        logger.info(f"  Source:  {src_label}")
        logger.info(f"  Target:  {tgt_label}")
        logger.info(f"  Input:   {self.input_dir}")
        if not self.dry_run:
            logger.info(f"  Output:  {self.output_dir}")
        logger.info("=" * 60)
        logger.info("")

        errors = self.validate()
        if errors:
            for e in errors:
                logger.error(e)
            return self.stats

        if not self.dry_run:
            ensure_dir(self.output_dir)

        logger.info("[1/5] Scanning input directory...")
        scan = scan_directory(self.input_dir)
        self.report.scan_summary = scan.summary()
        logger.info(scan.summary())
        logger.info("")

        needs_lua_transform = self.source_version in ("tfs03", "tfs04")
        needs_xml_to_revscript = self.target_version == "revscript"

        transformer = None
        if needs_lua_transform:
            transformer = LuaTransformer(self.function_map, self.source_version)
            if self.explain_report is not None:
                transformer.explain = self.explain_report

        if needs_xml_to_revscript and self._has_xml_registrations(scan):
            logger.info("[2/5] Converting XML + Lua → RevScript...")
            self._convert_xml_to_revscript(scan, transformer)
        else:
            logger.info("[2/5] No XML → RevScript conversion needed (or no XML found).")

        logger.info("")
        if self._has_npc_scripts(scan):
            logger.info("[3/5] Converting NPC scripts...")
            self._convert_npc_scripts(scan, transformer)
        else:
            logger.info("[3/5] No NPC scripts found.")

        logger.info("")
        logger.info("[4/5] Converting standalone Lua files...")
        self._convert_lua_files(scan, transformer)

        logger.info("")
        if not self.dry_run:
            logger.info("[5/5] Copying non-Lua/XML files...")
            self._copy_other_files(scan)
        else:
            logger.info("[5/5] Skipped file copy (dry-run mode)")

        self.stats["time_elapsed"] = time.time() - start_time
        self._print_summary()

        html_diff_dir = self.output_dir or self.input_dir

        if self.dry_run:
            report_text = self.report.generate_dry_run()
            logger.info("")
            print(report_text)
            self._guidelines_content = self._generate_oop_guidelines(html_diff_dir)
        else:
            report_path = os.path.join(self.output_dir, "conversion_report.txt")
            report_text = self.report.generate(report_path)
            logger.info(f"\n  Report saved to: {report_path}")
            self._guidelines_content = (
                self._generate_oop_guidelines(html_diff_dir) if self.html_diff else ""
            )

        if self.html_diff:
            self._generate_html_diff()

        if self.explain_report is not None and self.explain_report.entries:
            out = self.output_dir or self.input_dir
            explain_path = self.explain_report.write(out)
            logger.info(f"  Explain report saved to: {explain_path}")

        if self.guidance_report.entries:
            out = self.output_dir or self.input_dir
            guidance_path = os.path.join(out, "ast_guidance.txt")
            os.makedirs(out, exist_ok=True)
            with open(guidance_path, "w", encoding="utf-8") as f:
                f.write(self.guidance_report.to_text())
            logger.info(f"  AST guidance report saved to: {guidance_path}")

        return self.stats

    def _generate_oop_guidelines(self, output_dir: str = "") -> str:
        try:
            from .analyzers.lua_oop_analyzer import LuaOopAnalyzer
            from .analyzers.guidelines_generator import GuidelinesGenerator
        except ImportError:
            return ""

        analyzer = LuaOopAnalyzer()
        analyses = []
        for fr in self.report.file_reports:
            if not fr.original_content:
                continue
            rel = (
                os.path.relpath(fr.source_path, self.input_dir)
                if self.input_dir and fr.source_path
                else os.path.basename(fr.source_path)
            )
            if rel.endswith(".lua"):
                analysis = analyzer.analyze_content(fr.original_content, rel)
                # Enrich with AST metrics for more accurate LLM guidelines
                try:
                    from .analyzers.ast_enricher import enrich_analysis

                    enrich_analysis(analysis, fr.original_content)
                except Exception:
                    pass  # AST enrichment is optional; continue without it
                analyses.append(analysis)

        content = GuidelinesGenerator().generate(analyses, self.report)

        guidelines_path = os.path.join(
            output_dir or self.input_dir or os.getcwd(), "llm_refactor_guide.md"
        )
        try:
            with open(guidelines_path, "w", encoding="utf-8") as f:
                f.write(content)
            files_with = sum(1 for a in analyses if a.issues)
            total_issues = sum(len(a.issues) for a in analyses)
            logger.info(
                f"\n  LLM refactoring guide saved to: {guidelines_path} "
                f"({files_with} files, {total_issues} issues)"
            )
        except Exception as e:
            logger.warning(f"  Could not write LLM refactoring guide: {e}")

        return content

    def _has_xml_registrations(self, scan: ScanResult) -> bool:
        return any(
            [
                scan.actions_xml,
                scan.movements_xml,
                scan.talkactions_xml,
                scan.creaturescripts_xml,
                scan.globalevents_xml,
            ]
        )

    def _has_npc_scripts(self, scan: ScanResult) -> bool:
        return bool(scan.npc_dir and scan.npc_xml_files)

    def _generate_html_diff(self):
        src_label = VERSIONS.get(self.source_version, self.source_version)
        tgt_label = VERSIONS.get(self.target_version, self.target_version)
        diff_gen = HtmlDiffGenerator(
            src_label, tgt_label, self.input_dir, self.output_dir
        )
        if getattr(self, "_guidelines_content", ""):
            diff_gen.set_guidelines(self._guidelines_content)

        for fr in self.report.file_reports:
            if not fr.original_content and not fr.converted_content:
                continue

            filename = os.path.basename(fr.source_path)
            rel = (
                relative_path(fr.source_path, self.input_dir)
                if self.input_dir
                else filename
            )

            diff_gen.add_entry(
                DiffEntry(
                    filename=rel,
                    source_path=fr.source_path,
                    original=fr.original_content,
                    converted=fr.converted_content,
                    file_type=fr.file_type or fr.conversion_type,
                    confidence=fr.confidence_label,
                    functions_converted=fr.functions_converted,
                    total_changes=fr.total_changes,
                )
            )

        if self.output_dir:
            html_path = os.path.join(self.output_dir, "conversion_diff.html")
        else:
            html_path = os.path.join(self.input_dir, "conversion_diff.html")

        diff_gen.generate(html_path)
        logger.info(f"\n  HTML diff saved to: {html_path}")

    def _component_out_dir(
        self, scripts_dir: Optional[str], name: str, revscript_dir: str
    ) -> str:
        """Return the output dir for a component's converted scripts.

        When the input_dir IS the component folder (e.g. converting
        data-invictus/creaturescripts/ directly), the scripts_dir sits at
        input_dir/scripts/ — so we should NOT append the component name again.
        When input_dir is a parent folder, scripts_dir lives at
        input_dir/<name>/scripts/ and we DO need the extra level.
        """
        if not revscript_dir:
            return ""
        if scripts_dir:
            rel = os.path.relpath(scripts_dir, self.input_dir)
            first = rel.split(os.sep)[0]
            if first != name:
                # Already inside the component folder — no extra nesting
                return revscript_dir
        return os.path.join(revscript_dir, name)

    def _convert_xml_to_revscript(
        self, scan: ScanResult, transformer: Optional[LuaTransformer]
    ):
        ast_transformer = self._select_transformer(transformer)
        converter = XmlToRevScriptConverter(
            lua_transformer=ast_transformer, dry_run=self.dry_run
        )
        revscript_dir = (
            os.path.join(self.output_dir, "scripts") if self.output_dir else ""
        )

        conversions = [
            (
                scan.actions_xml,
                scan.actions_dir,
                "actions",
                self._component_out_dir(scan.actions_dir, "actions", revscript_dir),
            ),
            (
                scan.movements_xml,
                scan.movements_dir,
                "movements",
                self._component_out_dir(scan.movements_dir, "movements", revscript_dir),
            ),
            (
                scan.talkactions_xml,
                scan.talkactions_dir,
                "talkactions",
                self._component_out_dir(
                    scan.talkactions_dir, "talkactions", revscript_dir
                ),
            ),
            (
                scan.creaturescripts_xml,
                scan.creaturescripts_dir,
                "creaturescripts",
                self._component_out_dir(
                    scan.creaturescripts_dir, "creaturescripts", revscript_dir
                ),
            ),
            (
                scan.globalevents_xml,
                scan.globalevents_dir,
                "globalevents",
                self._component_out_dir(
                    scan.globalevents_dir, "globalevents", revscript_dir
                ),
            ),
        ]

        for xml_path, scripts_dir, name, out_dir in conversions:
            if not xml_path:
                continue

            if not scripts_dir:
                # Use the XML file's directory as scripts dir
                scripts_dir = os.path.dirname(xml_path)

            logger.info(f"  Converting {name}...")
            try:
                output_files = converter.convert_xml_file(
                    xml_path, scripts_dir, out_dir
                )
                logger.info(f"    Generated {len(output_files)} RevScript file(s)")
                self.stats["xml_files_processed"] += 1
                self.stats["revscripts_generated"] += len(output_files)

                for fr in converter.pop_file_reports():
                    fr.file_type = name
                    fr.conversion_type = "xml_to_revscript"
                    # Count TTT warnings in output file
                    if fr.output_path and os.path.isfile(fr.output_path):
                        fr.ttt_warnings = self.report.count_ttt_warnings_in_file(
                            fr.output_path
                        )
                    self.report.add_file_report(fr)

            except Exception as e:
                logger.error(f"    Error converting {name}: {e}")
                self.stats["errors"] += 1

        conv_summary = converter.get_summary()
        if conv_summary:
            logger.info(f"  XML→RevScript summary: {conv_summary}")

    def _convert_npc_scripts(
        self, scan: ScanResult, transformer: Optional[LuaTransformer]
    ):
        npc_converter = NpcConverter(lua_transformer=transformer, dry_run=self.dry_run)
        output_npc_dir = os.path.join(self.output_dir, "npc") if self.output_dir else ""

        try:
            output_files = npc_converter.convert_npc_folder(
                npc_dir=scan.npc_dir,
                scripts_dir=scan.npc_scripts_dir,
                npc_xml_files=scan.npc_xml_files,
                output_npc_dir=output_npc_dir,
            )
            logger.info(
                f"  Converted {npc_converter.stats['npcs_converted']} NPC(s), "
                f"{npc_converter.stats['scripts_transformed']} script(s)"
            )
            self.stats["revscripts_generated"] += len(output_files)

            for fr in npc_converter.pop_file_reports():
                fr.file_type = "npc"
                if fr.output_path and os.path.isfile(fr.output_path):
                    fr.ttt_warnings = self.report.count_ttt_warnings_in_file(
                        fr.output_path
                    )
                self.report.add_file_report(fr)

        except Exception as e:
            logger.error(f"  Error converting NPCs: {e}")
            self.stats["errors"] += 1

        npc_summary = npc_converter.get_summary()
        if npc_summary:
            logger.info(f"  NPC summary: {npc_summary}")

    def _select_transformer(self, transformer: Optional[LuaTransformer]):
        """Return the best available transformer (AST-based preferred, regex fallback)."""
        if AST_AVAILABLE and self.source_version in ("tfs03", "tfs04"):
            try:
                ast_t = ASTLuaTransformer(
                    function_map=self.function_map, source_version=self.source_version
                )
                logger.info("  Using AST-based transformer (with defensive checks)")
                return ast_t
            except Exception as e:
                logger.warning(f"  Could not initialize AST transformer: {e}")
                logger.info("  Falling back to regex transformer")

        if AST_AVAILABLE:
            logger.info(
                "  AST transformer available - using with defensive programming"
            )
        else:
            logger.info("  AST transformer not available - using regex transformer")
        return transformer

    def _collect_handled_dirs(self, scan: ScanResult) -> set:
        """Return set of normalized directory paths already handled by XML conversion."""
        handled = set()
        for attr in (
            "actions_dir",
            "movements_dir",
            "talkactions_dir",
            "creaturescripts_dir",
            "globalevents_dir",
            "npc_dir",
            "npc_scripts_dir",
        ):
            dir_path = getattr(scan, attr)
            if dir_path:
                handled.add(os.path.normpath(dir_path))
        return handled

    def _process_lua_file(self, lua_file: str, ast_transformer, rel: str, content: str):
        """Transform one Lua file, populate a FileReport, and update global stats."""
        fr = FileReport(source_path=lua_file, conversion_type="lua_transform")
        try:
            new_content = ast_transformer.transform(content, rel)
            summary = ast_transformer.get_summary()

            fr.functions_converted = ast_transformer.stats.get("functions_converted", 0)
            fr.signatures_updated = ast_transformer.stats.get("signatures_updated", 0)
            fr.constants_replaced = ast_transformer.stats.get("constants_replaced", 0)
            fr.variables_renamed = ast_transformer.stats.get("variables_renamed", 0)
            fr.defensive_checks_added = ast_transformer.stats.get(
                "defensive_checks_added", 0
            )
            fr.warnings = list(ast_transformer.warnings)

            if hasattr(ast_transformer, "warnings") and any(
                "regex fallback" in str(w) for w in ast_transformer.warnings
            ):
                fr.warnings.append("Used regex fallback due to AST error")

            fr.unrecognized_calls = self._find_unrecognized_calls(new_content)
            fr.original_content = content
            fr.converted_content = new_content

            # Collect per-rule confidence scores
            if hasattr(ast_transformer, "rule_confidences"):
                fr.rule_confidences = list(ast_transformer.rule_confidences)
            elif (
                hasattr(ast_transformer, "_fallback_transformer")
                and ast_transformer._fallback_transformer
            ):
                fr.rule_confidences = list(
                    ast_transformer._fallback_transformer.rule_confidences
                )

            # AST-assisted guidance analysis
            analyze_converted_code(new_content, content, rel, self.guidance_report)

            if not self.dry_run:
                out_path = os.path.join(self.output_dir, rel)
                write_file_safe(out_path, new_content)
                fr.output_path = out_path
                fr.ttt_warnings = self.report.count_ttt_warnings_in_file(out_path)

            if summary != "No changes":
                logger.info(f"  {rel}: {summary}")
                self.stats["total_functions_converted"] += ast_transformer.stats.get(
                    "functions_converted", 0
                )
                self.stats["defensive_checks_added"] += ast_transformer.stats.get(
                    "defensive_checks_added", 0
                )
            else:
                logger.debug(f"  {rel}: No changes needed")

            self.stats["lua_files_processed"] += 1

        except Exception as e:
            logger.error(f"  Error converting {rel}: {e}")
            fr.error = str(e)
            fr.success = False
            self.stats["errors"] += 1

        return fr

    def _convert_lua_files(
        self, scan: ScanResult, transformer: Optional[LuaTransformer]
    ):
        if not transformer:
            logger.info("  No API transformation needed (source is already 1.x)")
            if not self.dry_run:
                self._copy_lua_files(scan)
            return

        ast_transformer = self._select_transformer(transformer)
        handled_dirs = self._collect_handled_dirs(scan)

        converted = 0
        for lua_file in scan.lua_files:
            file_dir = os.path.normpath(os.path.dirname(lua_file))
            if (
                any(file_dir.startswith(hd) for hd in handled_dirs)
                and self.target_version == "revscript"
            ):
                continue

            content = read_file_safe(lua_file)
            if content is None:
                self.stats["errors"] += 1
                continue

            rel = relative_path(lua_file, self.input_dir)
            fr = self._process_lua_file(lua_file, ast_transformer, rel, content)
            self.report.add_file_report(fr)
            converted += 1

        logger.info(f"  Processed {converted} Lua file(s)")

    def _copy_lua_files(self, scan: ScanResult):
        copied = 0
        for lua_file in scan.lua_files:
            rel = relative_path(lua_file, self.input_dir)
            out_path = os.path.join(self.output_dir, rel)
            content = read_file_safe(lua_file)
            if content:
                write_file_safe(out_path, content)
                copied += 1
        logger.info(f"  Copied {copied} Lua file(s)")

    def _copy_other_files(self, scan: ScanResult):
        copied = 0
        for root, _, files in os.walk(self.input_dir):
            for f in files:
                if f.endswith((".lua", ".xml")):
                    continue

                src = os.path.join(root, f)
                rel = relative_path(src, self.input_dir)
                dst = os.path.join(self.output_dir, rel)

                try:
                    ensure_dir(os.path.dirname(dst))
                    shutil.copy2(src, dst)
                    copied += 1
                except Exception as e:
                    logger.debug(f"  Could not copy {rel}: {e}")

        if copied:
            logger.info(f"  Copied {copied} other file(s)")

    def _print_summary(self):
        label = "DRY RUN COMPLETE" if self.dry_run else "CONVERSION COMPLETE"
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  {label}")
        logger.info("=" * 60)
        logger.info(f"  Lua files processed:      {self.stats['lua_files_processed']}")
        logger.info(f"  XML files processed:      {self.stats['xml_files_processed']}")
        logger.info(f"  RevScripts generated:     {self.stats['revscripts_generated']}")
        logger.info(
            f"  Function calls converted: {self.stats['total_functions_converted']}"
        )
        if self.stats.get("defensive_checks_added", 0) > 0:
            logger.info(
                f"  Defensive checks added:   {self.stats['defensive_checks_added']}"
            )
        logger.info(f"  Errors:                   {self.stats['errors']}")
        logger.info(f"  Time elapsed:             {self.stats['time_elapsed']:.2f}s")
        if not self.dry_run:
            logger.info(f"  Output directory:         {self.output_dir}")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info(
                "\n  This was a dry-run. No files were written."
                "\n  Run without --dry-run to perform the actual conversion."
            )
        elif self.stats["errors"] > 0:
            logger.warning(
                "\n  Some errors occurred during conversion."
                "\n  Review the output files, especially those marked with '-- TTT:' comments."
            )
        else:
            logger.info(
                "\n  All files converted successfully!"
                "\n  Review output files for '-- TTT:' comments that may need manual attention."
            )

    # ─── Helpers ────────────────────────────────────────────────────────

    # Common old-API prefixes that indicate unrecognized legacy functions
    _OLD_API_PREFIXES = (
        "do",
        "get",
        "set",
        "is",
        "has",
    )

    _SAFE_FUNCS = {
        "print",
        "type",
        "tostring",
        "tonumber",
        "pairs",
        "ipairs",
        "table",
        "string",
        "math",
        "os",
        "io",
        "error",
        "pcall",
        "xpcall",
        "require",
        "dofile",
        "loadfile",
        "select",
        "unpack",
        "rawget",
        "rawset",
        "setmetatable",
        "getmetatable",
        "next",
        "assert",
        "collectgarbage",
    }

    def _find_unrecognized_calls(self, code: str) -> List[str]:
        unrecognized = set()
        # Match standalone function calls (not method calls obj:method)
        for m in re.finditer(r"\b(do[A-Z]\w+|get[A-Z]\w+|set[A-Z]\w+)\s*\(", code):
            func = m.group(1)
            # Skip if it's in a -- TTT comment line
            line_start = code.rfind("\n", 0, m.start()) + 1
            line = code[line_start : m.start()]
            if "--" in line:
                continue
            # Skip known safe
            if func.split(".")[0] not in self._SAFE_FUNCS:
                unrecognized.add(func)
        return sorted(unrecognized)
