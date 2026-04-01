"""
NPC Conversation Analyzer — Parses NPC XML+Lua and analyzes dialogue flow.

Detects:
- Keywords and responses (msgcontains/addKeyword patterns)
- Greet/farewell handlers
- Shop items (XML parameters + ShopModule)
- Travel destinations
- Duplicate keywords
- Conversation loops
- Unreachable responses
- Missing greet/farewell
- Mermaid graph generation
"""

import os
import re
from typing import List, Dict, Any, Optional, Set
from xml.etree import ElementTree


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class NPCData:
    """Parsed NPC data from XML + Lua."""

    def __init__(self, name: str = "", file: str = ""):
        self.name = name
        self.file = file
        self.xml_file = ""
        self.lua_file = ""
        self.script_ref = ""

        # XML-level data
        self.greet_message = ""
        self.farewell_message = ""
        self.shop_buyable: List[Dict[str, Any]] = []
        self.shop_sellable: List[Dict[str, Any]] = []
        self.parameters: Dict[str, str] = {}

        # Lua-level data
        self.keywords: List[str] = []  # keyword strings handled
        self.responses: Dict[str, str] = {}  # keyword -> response text
        self.has_greet = False
        self.has_farewell = False
        self.has_shop_module = False
        self.has_focus_module = False
        self.has_travel_module = False
        self.callback_keywords: List[str] = []  # from creatureSayCallback
        self.modules: List[str] = []
        self.graph: Dict[str, List[str]] = {}  # keyword -> list of referenced keywords

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "xml_file": self.xml_file,
            "lua_file": self.lua_file,
            "keywords": self.keywords,
            "responses": self.responses,
            "has_greet": self.has_greet,
            "has_farewell": self.has_farewell,
            "has_shop_module": self.has_shop_module,
            "shop_buyable": self.shop_buyable,
            "shop_sellable": self.shop_sellable,
            "modules": self.modules,
            "graph": self.graph,
        }


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class NPCConversationAnalyzer:
    def __init__(self, npc_dir: str, items_xml: str = None):
        self.npc_dir = npc_dir
        self.items_xml = items_xml
        self.npcs: List[NPCData] = []
        self._valid_items: Optional[Set[str]] = None

    def load_npcs(self):
        """Load and parse all NPCs from the directory."""
        self.npcs = []
        if not os.path.isdir(self.npc_dir):
            return

        # Find XML files (NPC definitions)
        xml_files = []
        for root, _, files in os.walk(self.npc_dir):
            for fname in files:
                if fname.endswith(".xml"):
                    fpath = os.path.join(root, fname)
                    xml_files.append(fpath)

        for xml_path in xml_files:
            npc = self._parse_xml(xml_path)
            if npc:
                # Try to find linked Lua script
                lua_path = self._find_lua_script(xml_path, npc.script_ref)
                if lua_path:
                    npc.lua_file = lua_path
                    self._parse_lua(npc, lua_path)
                self.npcs.append(npc)

        # Also scan for standalone Lua NPC scripts not linked from XML
        lua_only = set()
        for root, _, files in os.walk(self.npc_dir):
            for fname in files:
                if fname.endswith(".lua"):
                    fpath = os.path.join(root, fname)
                    if not any(n.lua_file == fpath for n in self.npcs):
                        lua_only.add(fpath)

        for lua_path in sorted(lua_only):
            npc = NPCData(
                name=os.path.splitext(os.path.basename(lua_path))[0],
                file=lua_path,
            )
            npc.lua_file = lua_path
            self._parse_lua(npc, lua_path)
            if npc.keywords or npc.modules:
                self.npcs.append(npc)

    # ------------------------------------------------------------------
    # XML Parsing
    # ------------------------------------------------------------------

    def _parse_xml(self, path: str) -> Optional[NPCData]:
        """Parse an NPC XML file."""
        try:
            tree = ElementTree.parse(path)
            root = tree.getroot()
        except (ElementTree.ParseError, OSError):
            return None

        if root.tag != "npc":
            return None

        npc = NPCData(
            name=root.get("name", ""),
            file=path,
        )
        npc.xml_file = path
        npc.script_ref = root.get("script", "")

        # Parse parameters
        for param in root.iter("parameter"):
            key = param.get("key", "")
            value = param.get("value", "")
            npc.parameters[key] = value

            if key == "message_greet":
                npc.greet_message = value
                npc.has_greet = True
            elif key == "message_farewell":
                npc.farewell_message = value
                npc.has_farewell = True
            elif key == "shop_buyable":
                npc.shop_buyable = self._parse_shop_param(value)
            elif key == "shop_sellable":
                npc.shop_sellable = self._parse_shop_param(value)

        # Extract keywords from greet message ({keyword} patterns)
        if npc.greet_message:
            for m in re.finditer(r"\{(\w+)\}", npc.greet_message):
                kw = m.group(1).lower()
                if kw not in npc.keywords:
                    npc.keywords.append(kw)

        return npc

    def _parse_shop_param(self, value: str) -> List[Dict[str, Any]]:
        """Parse shop_buyable/shop_sellable parameter value."""
        items = []
        for entry in value.split(";"):
            parts = entry.strip().split(",")
            if len(parts) >= 3:
                items.append(
                    {
                        "id": parts[0].strip(),
                        "name": parts[1].strip(),
                        "price": parts[2].strip(),
                    }
                )
        return items

    # ------------------------------------------------------------------
    # Lua Parsing
    # ------------------------------------------------------------------

    def _parse_lua(self, npc: NPCData, path: str) -> None:
        """Parse an NPC Lua script for keywords, modules, responses."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
        except OSError:
            return

        # Detect modules
        if "FocusModule" in code:
            npc.has_focus_module = True
            npc.modules.append("FocusModule")
        if "ShopModule" in code:
            npc.has_shop_module = True
            npc.modules.append("ShopModule")
        if "TravelModule" in code:
            npc.has_travel_module = True
            npc.modules.append("TravelModule")

        # Detect greet/farewell from setMessage
        if re.search(r"setMessage\s*\(\s*MESSAGE_GREET", code):
            npc.has_greet = True
        if re.search(r"setMessage\s*\(\s*MESSAGE_FAREWELL", code):
            npc.has_farewell = True

        # Detect greet from message_greet parameter
        if "message_greet" in code:
            npc.has_greet = True

        # Parse msgcontains keywords from callback
        for match in re.finditer(
            r'msgcontains\s*\(\s*msg\s*,\s*["\']([^"\']+)["\']', code, re.IGNORECASE
        ):
            kw = match.group(1).lower()
            if kw not in npc.keywords:
                npc.keywords.append(kw)
            npc.callback_keywords.append(kw)

        # Parse addKeyword patterns
        for match in re.finditer(
            r'(?:keywordHandler|npcHandler)\s*:\s*addKeyword\s*\(\s*["\']([^"\']+)["\']',
            code,
            re.IGNORECASE,
        ):
            kw = match.group(1).lower()
            if kw not in npc.keywords:
                npc.keywords.append(kw)

        # Parse selfSay responses within msgcontains blocks
        self._extract_responses(npc, code)

        # Build conversation graph
        self._build_graph(npc, code)

    def _extract_responses(self, npc: NPCData, code: str) -> None:
        """Extract keyword -> response mappings from msgcontains + selfSay."""
        # Pattern: msgcontains(msg, "keyword") ... selfSay("response", ...)
        blocks = re.split(r"(?=if\s+msgcontains)", code)
        for block in blocks:
            kw_match = re.search(
                r'msgcontains\s*\(\s*msg\s*,\s*["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            if not kw_match:
                continue
            kw = kw_match.group(1).lower()

            # Find selfSay in same block
            say_match = re.search(
                r'selfSay\s*\(\s*["\']([^"\']+)["\']', block, re.IGNORECASE
            )
            if say_match:
                npc.responses[kw] = say_match.group(1)

    def _build_graph(self, npc: NPCData, code: str) -> None:
        """Build conversation flow graph (keyword -> referenced keywords)."""
        # Start node is "greet"
        npc.graph["greet"] = list(npc.keywords)

        # Each keyword that references other keywords in its response
        for kw in npc.keywords:
            referenced = []
            response = npc.responses.get(kw, "")
            # Check for {keyword} references in responses
            for m in re.finditer(r"\{(\w+)\}", response):
                ref = m.group(1).lower()
                if ref in npc.keywords and ref != kw:
                    referenced.append(ref)
            npc.graph[kw] = referenced

    # ------------------------------------------------------------------
    # Finding Lua scripts
    # ------------------------------------------------------------------

    def _find_lua_script(self, xml_path: str, script_ref: str) -> Optional[str]:
        """Find the Lua script referenced by an NPC XML file."""
        if not script_ref:
            return None

        # Try scripts/ subdir relative to XML
        xml_dir = os.path.dirname(xml_path)
        candidates = [
            os.path.join(xml_dir, "scripts", script_ref),
            os.path.join(xml_dir, script_ref),
            os.path.join(self.npc_dir, "scripts", script_ref),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    # ------------------------------------------------------------------
    # Analysis methods
    # ------------------------------------------------------------------

    def detect_loops(self) -> Dict[str, Any]:
        """Detect conversation loops (cycles in keyword graph)."""
        result = {}
        for npc in self.npcs:
            loops = self._find_cycles(npc.graph)
            result[npc.file] = {
                "has_loop": len(loops) > 0,
                "loops": loops,
            }
        return result

    def _find_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Find cycles in a directed graph using DFS."""
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        path: List[str] = []
        path_set: Set[str] = set()

        def dfs(node: str):
            if node in path_set:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in graph.get(node, []):
                dfs(neighbor)
            path.pop()
            path_set.discard(node)

        for node in graph:
            dfs(node)
        return cycles

    def detect_duplicate_keywords(self) -> Dict[str, Any]:
        """Detect duplicate keyword handlers in each NPC."""
        result = {}
        for npc in self.npcs:
            # callback_keywords captures each occurrence (including repeats)
            seen: Dict[str, int] = {}
            duplicates = []
            for kw in npc.callback_keywords:
                seen[kw] = seen.get(kw, 0) + 1
            for kw, count in seen.items():
                if count > 1:
                    duplicates.append(kw)
            result[npc.file] = {"duplicates": duplicates}
        return result

    def detect_unreachable_responses(self) -> Dict[str, Any]:
        """Detect responses that can't be reached from the greet node."""
        result = {}
        for npc in self.npcs:
            reachable = self._reachable_from(npc.graph, "greet")
            unreachable = [kw for kw in npc.keywords if kw not in reachable]
            result[npc.file] = {"unreachable": unreachable}
        return result

    def _reachable_from(self, graph: Dict[str, List[str]], start: str) -> Set[str]:
        """BFS to find all reachable nodes from start."""
        visited: Set[str] = set()
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        return visited

    def check_greet_farewell(self) -> Dict[str, Any]:
        """Check if NPCs have greet/farewell handlers."""
        result = {}
        for npc in self.npcs:
            result[npc.file] = {
                "greet": npc.has_greet,
                "farewell": npc.has_farewell,
            }
        return result

    def validate_shop_items(self) -> Dict[str, Any]:
        """Validate shop items against items.xml if available."""
        result = {}
        valid_ids = self._load_valid_items()

        for npc in self.npcs:
            invalid = []
            all_items = npc.shop_buyable + npc.shop_sellable
            if valid_ids is not None:
                for item in all_items:
                    item_id = item.get("id", "")
                    if item_id and item_id not in valid_ids:
                        invalid.append(item)
            result[npc.file] = {
                "total_items": len(all_items),
                "invalid_items": invalid,
            }
        return result

    def _load_valid_items(self) -> Optional[Set[str]]:
        """Load valid item IDs from items.xml."""
        if self._valid_items is not None:
            return self._valid_items
        if not self.items_xml or not os.path.isfile(self.items_xml):
            return None
        try:
            tree = ElementTree.parse(self.items_xml)
            root = tree.getroot()
            self._valid_items = set()
            for item in root.iter("item"):
                item_id = item.get("id", "")
                if item_id:
                    self._valid_items.add(item_id)
            return self._valid_items
        except (ElementTree.ParseError, OSError):
            return None

    def generate_visual_graph(self, output_path: str) -> None:
        """Generate a Mermaid diagram of conversation flows."""
        lines = ["```mermaid", "graph TD"]
        for npc in self.npcs:
            prefix = (
                re.sub(r"[^a-zA-Z0-9_]", "_", npc.name)
                if npc.name
                else os.path.splitext(os.path.basename(npc.file))[0]
            )
            lines.append(f"    subgraph {prefix}")
            lines.append(f'        {prefix}_greet(("{npc.name or prefix}: Greet"))')

            for kw in npc.keywords:
                node_id = f"{prefix}_{kw}"
                lines.append(f'        {node_id}["{kw}"]')

            # Edges from greet to keywords
            for kw in npc.graph.get("greet", []):
                node_id = f"{prefix}_{kw}"
                lines.append(f"        {prefix}_greet --> {node_id}")

            # Edges between keywords
            for kw, targets in npc.graph.items():
                if kw == "greet":
                    continue
                src = f"{prefix}_{kw}"
                for tgt in targets:
                    dst = f"{prefix}_{tgt}"
                    lines.append(f"        {src} --> {dst}")

            lines.append("    end")

        lines.append("```")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def analyze(self) -> Dict[str, Any]:
        """Run all analyses and return consolidated report."""
        return {
            "total_npcs": len(self.npcs),
            "npcs": [n.to_dict() for n in self.npcs],
            "loops": self.detect_loops(),
            "duplicate_keywords": self.detect_duplicate_keywords(),
            "unreachable_responses": self.detect_unreachable_responses(),
            "greet_farewell": self.check_greet_farewell(),
            "shop_items": self.validate_shop_items(),
        }

    def format_report(self) -> str:
        """Format analysis results as readable text."""
        report = self.analyze()
        lines = []
        sep = "=" * 60
        lines.append("")
        lines.append(sep)
        lines.append("  NPC Conversation Analysis Report")
        lines.append(sep)
        lines.append(f"  Total NPCs analyzed: {report['total_npcs']}")
        lines.append("")

        for npc in self.npcs:
            fname = os.path.basename(npc.file)
            lines.append(f"  NPC: {npc.name or fname}")
            lines.append(f"  File: {fname}")
            lines.append(
                f"  Keywords: {', '.join(npc.keywords) if npc.keywords else '(none)'}"
            )
            lines.append(
                f"  Modules: {', '.join(npc.modules) if npc.modules else '(none)'}"
            )

            greet_info = report["greet_farewell"].get(npc.file, {})
            lines.append(
                f"    {'OK' if greet_info.get('greet') else 'MISSING'} Greet handler"
            )
            lines.append(
                f"    {'OK' if greet_info.get('farewell') else 'MISSING'} Farewell handler"
            )

            dups = report["duplicate_keywords"].get(npc.file, {})
            if dups.get("duplicates"):
                for kw in dups["duplicates"]:
                    lines.append(f"    WARN Duplicate keyword: '{kw}'")
            else:
                lines.append("    OK All keywords unique")

            loops = report["loops"].get(npc.file, {})
            if loops.get("has_loop"):
                for loop in loops.get("loops", []):
                    lines.append(f"    WARN Loop: {' -> '.join(loop)}")
            else:
                lines.append("    OK No conversation loops")

            unreachable = report["unreachable_responses"].get(npc.file, {})
            if unreachable.get("unreachable"):
                for resp in unreachable["unreachable"]:
                    lines.append(f"    WARN Unreachable keyword: '{resp}'")
            else:
                lines.append("    OK All keywords reachable")

            shop = report["shop_items"].get(npc.file, {})
            if shop.get("invalid_items"):
                for item in shop["invalid_items"]:
                    lines.append(
                        f"    WARN Invalid shop item: {item.get('name', item.get('id', '?'))}"
                    )
            elif shop.get("total_items", 0) > 0:
                lines.append(f"    OK All {shop['total_items']} shop items valid")

            lines.append("")

        lines.append(sep)
        return "\n".join(lines)


# CLI support
if __name__ == "__main__":
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="NPC Conversation Analyzer")
    parser.add_argument("npc_dir", help="Directory containing NPC scripts")
    parser.add_argument(
        "--items-xml", help="Path to items.xml for shop validation", default=None
    )
    parser.add_argument("--graph", help="Save conversation graph to file", default=None)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    analyzer = NPCConversationAnalyzer(args.npc_dir, items_xml=args.items_xml)
    analyzer.load_npcs()

    if args.json:
        print(_json.dumps(analyzer.analyze(), indent=2))
    else:
        print(analyzer.format_report())

    if args.graph:
        analyzer.generate_visual_graph(args.graph)
        print(f"Visual graph saved to {args.graph}")
