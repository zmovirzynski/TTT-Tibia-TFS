"""Analyzes Lua scripts for OOP conversion opportunities."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ttt.analyzers.ast_enricher import ASTMetrics


MIN_OLD_CALLS = 3           # min old-style API calls to flag
MAX_AVG_LINES = 50          # avg lines/function threshold
MIN_GLOBALS = 2             # min global vars to flag
MIN_STORAGE_KEYS = 2        # min numeric keys to flag as storage table
MIN_STORAGE_KEY_VALUE = 1000  # numeric value threshold for storage key detection
MIN_EFFECT_EVENTS = 3       # min addEvent effect calls to flag as sequence


@dataclass
class LuaOopIssue:
    issue_type: str
    description: str
    guideline: str


@dataclass
class LuaFileAnalysis:
    file_path: str
    issues: List[LuaOopIssue] = field(default_factory=list)
    total_lines: int = 0
    ast_metrics: Optional["ASTMetrics"] = field(default=None, repr=False)


# ── Compiled regexes ────────────────────────────────────────────────────────

# Old procedural API: doPlayerXxx, getCreatureXxx, setItemXxx, etc.
_OLD_API_RE = re.compile(
    r'\b(do|get|set|is|has)(Player|Creature|Item|Container|Tile|Town|House)'
    r'([A-Z]\w*)\s*\('
)

# Function definitions that receive `cid` as a parameter
_CID_PARAM_RE = re.compile(
    r'\bfunction\b[^(]*\([^)]*\bcid\b[^)]*\)'
)

# Named function definition — captures function name and param list
_NAMED_FUNC_RE = re.compile(
    r'\bfunction\s+([\w.:]+)\s*\(([^)]*)\)(.*?)(?=\bfunction\b|\Z)',
    re.DOTALL,
)

# Count `function` keywords (for avg lines/function estimate)
_FUNC_KW_RE = re.compile(r'\bfunction\b')

# Global variable assignment: ALL_CAPS = value (not a function)
_GLOBAL_VAR_RE = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(?!function\b)')

# Nil guard patterns: if not isCreature(x) / if not isPlayer(x)
_NIL_GUARD_RE = re.compile(
    r'\bif\s+not\s+(isCreature|isPlayer|isMonster|isNpc)\s*\(\s*(\w+)\s*\)'
)

# addEvent with a creature/player identifier as third arg
_ADD_EVENT_RE = re.compile(
    r'\baddEvent\s*\(\s*(\w+)\s*,\s*[^,)]+,\s*(\w*cid\w*|\bcid\b|\bplayer\b)\b'
)

# Entity variable names commonly holding cid-like values
_ENTITY_VAR_RE = re.compile(
    r'^(cid|target|attacker|defender|killer|victim|creature|pid)$'
)

# createConditionObject / setConditionParam / doAddCondition
_COND_CREATE_RE = re.compile(r'\bcreateConditionObject\s*\(')
_COND_PARAM_RE = re.compile(r'\bsetConditionParam\s*\(')
_COND_ADD_RE = re.compile(r'\bdoAddCondition\s*\(')

# Combat damage calls
_COMBAT_RE = re.compile(
    r'\b(doTargetCombat(?:Health|Mana)?|doAreaCombat(?:Health|Mana)?|doCombat)\s*\('
)

# Effect / distance shoot inside addEvent
_EFFECT_EVENT_RE = re.compile(
    r'\baddEvent\s*\(\s*(doSendMagicEffect|doSendDistanceShoot)\s*,'
)

# Standalone storage key globals: varName = <number >= MIN_STORAGE_KEY_VALUE>
# Must be at line start (global scope), not inside a table
_STORAGE_GLOBAL_RE = re.compile(
    r'^([a-zA-Z_]\w*)\s*=\s*(\d+)\s*$'
)


class LuaOopAnalyzer:
    def analyze_content(self, content: str, rel_path: str) -> LuaFileAnalysis:
        lines = content.splitlines()
        issues: List[LuaOopIssue] = []
        issues.extend(self._detect_cid_pattern(content))
        issues.extend(self._detect_old_api_calls(content))
        issues.extend(self._detect_nil_guards(content))
        issues.extend(self._detect_storage_tables(content))
        issues.extend(self._detect_storage_key_globals(lines))
        issues.extend(self._detect_add_event_cid(content))
        issues.extend(self._detect_condition_object(content))
        issues.extend(self._detect_combat_calls(content))
        issues.extend(self._detect_effect_sequence(content))
        issues.extend(self._detect_recursive_addevent(content))
        issues.extend(self._detect_multi_entity(content))
        issues.extend(self._detect_large_functions(content, lines))
        issues.extend(self._detect_global_state(lines))
        return LuaFileAnalysis(file_path=rel_path, issues=issues, total_lines=len(lines))

    # ── Detectors ────────────────────────────────────────────────────────────

    def _detect_cid_pattern(self, content: str) -> List[LuaOopIssue]:
        matches = _CID_PARAM_RE.findall(content)
        if not matches:
            return []
        count = len(matches)
        return [LuaOopIssue(
            issue_type="CID_USAGE",
            description=(
                f"{count} function(s) receive `cid` as a player/creature identifier "
                f"instead of an OOP object."
            ),
            guideline=(
                "At the top of each function add `local player = Player(cid)` "
                "and guard with `if not player then return end`. "
                "Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` "
                "calls with `player:xxx(...)` method calls."
            ),
        )]

    def _detect_old_api_calls(self, content: str) -> List[LuaOopIssue]:
        matches = list(_OLD_API_RE.finditer(content))
        if len(matches) < MIN_OLD_CALLS:
            return []

        by_entity: Dict[str, Set[str]] = {}
        for m in matches:
            entity = m.group(2)
            func = m.group(0).rstrip("(").strip()
            by_entity.setdefault(entity, set()).add(func)

        entity_summary = ", ".join(
            f"{len(v)} on {k}" for k, v in sorted(by_entity.items())
        )
        total = len(matches)
        unique = sum(len(v) for v in by_entity.values())
        all_funcs = sorted({m.group(0).rstrip("(").strip() for m in matches})
        sample = ", ".join(f"`{f}`" for f in all_funcs[:6])
        if len(all_funcs) > 6:
            sample += f" (+{len(all_funcs) - 6} more)"

        return [LuaOopIssue(
            issue_type="OLD_API_CALLS",
            description=(
                f"{total} old-style procedural call(s) ({unique} unique): "
                f"{entity_summary}. Sample: {sample}."
            ),
            guideline=(
                "Cache each entity object once per function: "
                "`local player = Player(cid)`, `local item = Item(uid)`, "
                "`local target = Creature(targetId)`. "
                "Then use OOP methods: `player:getLevel()` instead of "
                "`getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of "
                "`doPlayerSendTextMessage(cid, ...)`. "
                "Each entity needs its own local variable."
            ),
        )]

    def _detect_nil_guards(self, content: str) -> List[LuaOopIssue]:
        matches = list(_NIL_GUARD_RE.finditer(content))
        if not matches:
            return []
        if not _OLD_API_RE.search(content):
            return []

        guard_vars: Dict[str, Set[str]] = {}
        for m in matches:
            guard_vars.setdefault(m.group(2), set()).add(m.group(1))

        count = len(matches)
        vars_list = ", ".join(f"`{v}`" for v in list(guard_vars)[:5])
        return [LuaOopIssue(
            issue_type="NIL_GUARD_PATTERN",
            description=(
                f"{count} `isCreature`/`isPlayer` guard(s) on variable(s) "
                f"{vars_list} need migration to OOP nil checks."
            ),
            guideline=(
                "After creating the OOP object (`local player = Player(cid)`), "
                "replace `if not isCreature(cid) then return end` with "
                "`if not player then return end`. "
                "For creatures: `local creature = Creature(cid); "
                "if not creature then return end`."
            ),
        )]

    def _detect_storage_tables(self, content: str) -> List[LuaOopIssue]:
        table_block_re = re.compile(r'(\w+)\s*=\s*\{([^}]{10,})\}', re.DOTALL)
        storage_tables: List[Tuple[str, int]] = []

        for m in table_block_re.finditer(content):
            body = m.group(2)
            num_vals = [
                int(v) for v in re.findall(r'=\s*(\d+)', body)
                if int(v) >= MIN_STORAGE_KEY_VALUE
            ]
            if len(num_vals) >= MIN_STORAGE_KEYS:
                storage_tables.append((m.group(1), len(num_vals)))

        if not storage_tables:
            return []

        names = ", ".join(f"`{n}` ({k} keys)" for n, k in storage_tables[:5])
        total_keys = sum(k for _, k in storage_tables)
        return [LuaOopIssue(
            issue_type="STORAGE_KEY_TABLE",
            description=(
                f"{len(storage_tables)} storage key table(s) with {total_keys} "
                f"total key(s): {names}."
            ),
            guideline=(
                "`getPlayerStorageValue(cid, TABLE.key)` → `player:getStorageValue(TABLE.key)`. "
                "`setPlayerStorageValue(cid, TABLE.key, val)` → `player:setStorageValue(TABLE.key, val)`. "
                "The table structure itself can stay unchanged."
            ),
        )]

    def _detect_storage_key_globals(self, lines: list) -> List[LuaOopIssue]:
        """Detects standalone global variables whose value is a storage key (>= 1000)."""
        found: List[str] = []
        for line in lines:
            stripped = line.strip()
            # Skip lines inside tables (indented or after comma)
            if stripped.startswith("--"):
                continue
            m = _STORAGE_GLOBAL_RE.match(stripped)
            if m:
                val = int(m.group(2))
                name = m.group(1)
                # Ignore common non-storage numbers and ALL_CAPS config constants
                if val >= MIN_STORAGE_KEY_VALUE and not name.isupper():
                    found.append(f"`{name}` = {val}")

        if len(found) < MIN_GLOBALS:
            return []

        sample = ", ".join(found[:6]) + ("…" if len(found) > 6 else "")
        return [LuaOopIssue(
            issue_type="STORAGE_KEY_GLOBALS",
            description=(
                f"{len(found)} standalone global storage key(s) detected: {sample}. "
                "These are used directly in `getPlayerStorageValue`/`setPlayerStorageValue` calls."
            ),
            guideline=(
                "Group standalone storage key globals into a named table: "
                "`local storages = { myKey = 55000, otherKey = 55001 }` "
                "then access as `player:getStorageValue(storages.myKey)`. "
                "This makes all keys discoverable and avoids magic numbers scattered across files."
            ),
        )]

    def _detect_add_event_cid(self, content: str) -> List[LuaOopIssue]:
        matches = list(_ADD_EVENT_RE.finditer(content))
        if not matches:
            return []

        callbacks = {m.group(1) for m in matches}
        count = len(matches)
        cb_list = ", ".join(f"`{c}`" for c in sorted(callbacks)[:5])
        return [LuaOopIssue(
            issue_type="ADD_EVENT_CID",
            description=(
                f"{count} `addEvent()` call(s) pass a creature/player ID directly "
                f"(callback(s): {cb_list}). "
                "The creature may be dead or despawned when the callback fires, "
                "causing a server crash."
            ),
            guideline=(
                "Never pass a live creature object to `addEvent`. "
                "Pass the numeric ID and re-fetch inside the callback: "
                "`addEvent(function(id, ...) "
                "local creature = Creature(id) "  # Player/Monster/Npc depending on context
                "if not creature then return end "
                "-- your logic here "
                "end, delay, creature:getId(), ...)`. "
                "Use `Player(id)`, `Monster(id)` or `Npc(id)` instead of `Creature(id)` "
                "when the entity type is known, for stricter nil safety."
            ),
        )]

    def _detect_condition_object(self, content: str) -> List[LuaOopIssue]:
        """Detects the createConditionObject → setConditionParam → doAddCondition chain."""
        creates = len(_COND_CREATE_RE.findall(content))
        if creates == 0:
            return []

        params = len(_COND_PARAM_RE.findall(content))
        adds = len(_COND_ADD_RE.findall(content))

        detail_parts = [f"{creates} `createConditionObject`"]
        if params:
            detail_parts.append(f"{params} `setConditionParam`")
        if adds:
            detail_parts.append(f"{adds} `doAddCondition`")

        return [LuaOopIssue(
            issue_type="CONDITION_OBJECT",
            description=(
                f"Old condition chain detected: {', '.join(detail_parts)}. "
                "This pattern requires manual object threading and is error-prone."
            ),
            guideline=(
                "Replace with the TFS 1.x Condition API: "
                "`local condition = Condition(CONDITIONTYPE_HASTE)` then set parameters "
                "with `condition:setParameter(CONDITION_PARAM_TICKS, ms)` and apply with "
                "`creature:addCondition(condition)`. "
                "Conditions can be reused across creatures — create once, apply many times."
            ),
        )]

    def _detect_combat_calls(self, content: str) -> List[LuaOopIssue]:
        """Detects raw combat damage calls (doTargetCombatHealth, doAreaCombat, etc.)."""
        matches = list(_COMBAT_RE.finditer(content))
        if not matches:
            return []

        funcs = sorted({m.group(1) for m in matches})
        count = len(matches)
        sample = ", ".join(f"`{f}`" for f in funcs[:5])
        return [LuaOopIssue(
            issue_type="COMBAT_CALLS",
            description=(
                f"{count} raw combat call(s) found: {sample}. "
                "Damage type and formula are passed as loose arguments."
            ),
            guideline=(
                "Replace with the TFS 1.x Combat object: "
                "`local combat = Combat()` then configure with "
                "`combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_PHYSICALDAMAGE)`, "
                "`combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_HITAREA)`, "
                "`combat:setFormula(COMBAT_FORMULA_DAMAGE, -1, minDmg, -1, maxDmg)`. "
                "Execute with `combat:execute(cid, variant)`. "
                "This keeps combat config centralised and makes the formula explicit."
            ),
        )]

    def _detect_effect_sequence(self, content: str) -> List[LuaOopIssue]:
        """Detects timed effect sequences: 3+ addEvent(doSendMagicEffect/doSendDistanceShoot)."""
        # Scan per named function to give per-function counts
        flagged_funcs: List[str] = []

        for m in _NAMED_FUNC_RE.finditer(content):
            func_name = m.group(1)
            body = m.group(3)
            hits = len(_EFFECT_EVENT_RE.findall(body))
            if hits >= MIN_EFFECT_EVENTS:
                flagged_funcs.append(f"`{func_name}` ({hits} events)")

        # Fallback: file-level count if no named functions matched
        if not flagged_funcs:
            total_hits = len(_EFFECT_EVENT_RE.findall(content))
            if total_hits < MIN_EFFECT_EVENTS:
                return []
            flagged_funcs = [f"(file-level, {total_hits} events)"]

        sample = ", ".join(flagged_funcs[:4])
        if len(flagged_funcs) > 4:
            sample += f" (+{len(flagged_funcs) - 4} more)"

        return [LuaOopIssue(
            issue_type="EFFECT_SEQUENCE",
            description=(
                f"Timed effect sequence(s) via `addEvent` detected in: {sample}. "
                "Hardcoded delays and repeated `getThingPos` calls are fragile."
            ),
            guideline=(
                "Extract the sequence into a dedicated helper that accepts the position "
                "snapshot at call time: capture `local fromPos = creature:getPosition()` "
                "before the first `addEvent`, then pass it as a parameter. "
                "Avoid calling `getThingPos`/`creature:getPosition()` inside delayed "
                "callbacks — the creature may have moved or died. "
                "Consider wrapping sequences in a local table: "
                "`local seq = {{300, CONST_ME_X}, {450, CONST_ME_Y}}` and iterating "
                "with a single scheduling loop."
            ),
        )]

    def _detect_recursive_addevent(self, content: str) -> List[LuaOopIssue]:
        """Detects functions that reschedule themselves via addEvent(ownName, delay, ...)."""
        recursive: List[str] = []

        for m in _NAMED_FUNC_RE.finditer(content):
            func_name = m.group(1)
            body = m.group(3)
            # Look for addEvent(funcName, ...) where funcName == this function
            escaped = re.escape(func_name)
            if re.search(rf'\baddEvent\s*\(\s*{escaped}\s*,', body):
                recursive.append(f"`{func_name}`")

        if not recursive:
            return []

        sample = ", ".join(recursive[:5])
        if len(recursive) > 5:
            sample += f" (+{len(recursive) - 5} more)"

        return [LuaOopIssue(
            issue_type="RECURSIVE_ADDEVENT",
            description=(
                f"{len(recursive)} self-rescheduling function(s) via `addEvent`: {sample}. "
                "Each reschedule passes the creature ID again — if the creature is gone "
                "the callback still fires, risking a crash or stale state."
            ),
            guideline=(
                "Wrap the recursive body in an anonymous closure that re-validates "
                "the creature on every tick: "
                "`addEvent(function(id, ...) "
                "local creature = Creature(id) "  # use Player/Monster/Npc when type is known
                "if not creature then return end "
                "-- your logic; reschedule if needed "
                "end, delay, creature:getId(), ...)`. "
                "Store a storage flag to allow external cancellation "
                "(`creature:setStorageValue(STOP_KEY, 1)`) and check it at the top "
                "of each tick before rescheduling."
            ),
        )]

    def _detect_multi_entity(self, content: str) -> List[LuaOopIssue]:
        """Detects functions that operate on multiple distinct entity variables."""
        multi_entity_funcs: List[str] = []

        for m in _NAMED_FUNC_RE.finditer(content):
            func_name = m.group(1)
            params = m.group(2)
            body = m.group(3)
            combined = params + body

            entity_vars: Set[str] = set()
            for api_m in _OLD_API_RE.finditer(combined):
                after = combined[api_m.end():]
                arg_m = re.match(r'\s*(\w+)', after)
                if arg_m:
                    var = arg_m.group(1)
                    if _ENTITY_VAR_RE.match(var):
                        entity_vars.add(var)

            if len(entity_vars) >= 2:
                multi_entity_funcs.append(
                    f"`{func_name}` ({', '.join(sorted(entity_vars))})"
                )

        if not multi_entity_funcs:
            return []

        sample = ", ".join(multi_entity_funcs[:4])
        if len(multi_entity_funcs) > 4:
            sample += f" (+{len(multi_entity_funcs) - 4} more)"
        return [LuaOopIssue(
            issue_type="MULTI_ENTITY",
            description=(
                f"{len(multi_entity_funcs)} function(s) operate on multiple entity "
                f"variable(s): {sample}."
            ),
            guideline=(
                "Create a separate OOP object for each entity at the function start: "
                "`local player = Player(cid)`, `local target = Creature(targetId)`, "
                "`local item = Item(uid)`. "
                "Guard each one independently before use."
            ),
        )]

    def _detect_large_functions(self, content: str, lines: list) -> List[LuaOopIssue]:
        func_count = len(_FUNC_KW_RE.findall(content))
        total = len(lines)
        if func_count == 0 or total // func_count <= MAX_AVG_LINES:
            return []
        avg = total // func_count
        return [LuaOopIssue(
            issue_type="LARGE_FUNCTIONS",
            description=(
                f"Average ~{avg} lines per function "
                f"({total} total lines, {func_count} `function` keyword(s))."
            ),
            guideline=(
                "Break large functions into focused helpers. In RevScript, "
                "group related helpers under a local module table "
                "(e.g. `local M = {}`) and register callbacks at the end."
            ),
        )]

    def _detect_global_state(self, lines: list) -> List[LuaOopIssue]:
        found = []
        for line in lines:
            m = _GLOBAL_VAR_RE.match(line.strip())
            if m:
                found.append(m.group(1))
        if len(found) < MIN_GLOBALS:
            return []
        sample = ", ".join(found[:5]) + ("…" if len(found) > 5 else "")
        return [LuaOopIssue(
            issue_type="GLOBAL_STATE",
            description=(
                f"{len(found)} global variable(s) detected: {sample}."
            ),
            guideline=(
                "Replace script-level globals with `local` constants or a "
                "local config table. For persistent state use the storage API "
                "(`player:getStorageValue` / `player:setStorageValue`)."
            ),
        )]
