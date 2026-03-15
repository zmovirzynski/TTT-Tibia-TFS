"""Scope analyzer for tracking creature/player IDs in Lua code.

This module provides functionality to analyze Lua AST and track variables
that represent creature/player IDs through different scopes. It's used by
the TTT (TFS Script Converter) to properly convert TFS 0.3/0.4 scripts to
TFS 1.x format.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from luaparser import ast
from luaparser.astnodes import (
    Node,
    Function,
    AnonymousFunction,
    LocalAssign,
    Assign,
    Name,
    Call,
    Invoke,
    Index,
    String,
    Number,
    TrueExpr,
    FalseExpr,
    Nil,
    Block,
    Return,
    If,
    While,
    Repeat,
    Fornum,
    Forin,
    Chunk,
)

# Import from existing mappings
from ..mappings.signatures import SIGNATURE_MAP, PARAM_RENAME_MAP
from ..mappings.tfs03_functions import TFS03_TO_1X, GAME_FUNCTIONS
from .ast_utils import get_function_name, get_base_name


@dataclass
class VariableInfo:
    """Information about a variable in scope.

    Attributes:
        name: The original variable name
        var_type: The inferred type ('player', 'creature', 'monster', 'npc', 'item', etc.)
        is_param: Whether this variable is a function parameter
        renamed_name: The new name after conversion (e.g., cid -> player)
        scope_level: The nesting level of the scope where this variable is defined
    """

    name: str
    var_type: str
    is_param: bool
    renamed_name: Optional[str] = None
    scope_level: int = 0


class Scope:
    """Represents a lexical scope in Lua code.

    A scope contains a mapping of variable names to their information,
    and maintains a reference to the parent scope for variable lookup
    in enclosing scopes.

    Attributes:
        variables: Dictionary mapping variable names to VariableInfo
        parent: Reference to the parent scope (None for global scope)
        level: Nesting level (0 for global, increases with nesting)
    """

    def __init__(self, parent: Optional["Scope"] = None, level: int = 0):
        self.variables: Dict[str, VariableInfo] = {}
        self.parent = parent
        self.level = level

    def define(self, name: str, info: VariableInfo) -> None:
        """Define a variable in this scope.

        Args:
            name: The variable name
            info: The variable information
        """
        self.variables[name] = info

    def lookup(self, name: str) -> Optional[VariableInfo]:
        """Look up a variable in this scope or parent scopes.

        Args:
            name: The variable name to look up

        Returns:
            VariableInfo if found, None otherwise
        """
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def is_defined_locally(self, name: str) -> bool:
        """Check if a variable is defined in this scope (not parent).

        Args:
            name: The variable name to check

        Returns:
            True if defined in this scope, False otherwise
        """
        return name in self.variables


@dataclass
class ScopeInfo:
    """Result of scope analysis containing all tracked information.

    Attributes:
        global_scope: The global scope containing top-level definitions
        function_scopes: List of scopes for each function (in order of visit)
        all_variables: Flattened dictionary of all variables found
    """

    global_scope: Scope
    function_scopes: List[Tuple[str, Scope]] = field(default_factory=list)
    all_variables: Dict[str, List[VariableInfo]] = field(default_factory=dict)

    def get_variable(
        self, name: str, scope: Optional[Scope] = None
    ) -> Optional[VariableInfo]:
        """Get variable info by name, optionally starting from a specific scope.

        Args:
            name: The variable name
            scope: The scope to start lookup from (defaults to global)

        Returns:
            VariableInfo if found, None otherwise
        """
        if scope:
            return scope.lookup(name)
        return self.global_scope.lookup(name)

    def get_variables_by_type(self, var_type: str) -> List[VariableInfo]:
        """Get all variables of a specific type.

        Args:
            var_type: The type to filter by

        Returns:
            List of VariableInfo objects of the specified type
        """
        result = []
        for var_list in self.all_variables.values():
            for var in var_list:
                if var.var_type == var_type:
                    result.append(var)
        return result


class ScopeAnalyzer(ast.ASTVisitor):
    """Analyzer for tracking creature/player IDs through Lua scopes.

    This visitor traverses the Lua AST and builds a scope hierarchy,
    tracking variables that represent creature/player IDs. It uses
    heuristics and signature mappings to infer variable types.

    Attributes:
        signature_map: Mapping of function names to their signatures
        current_scope: The scope currently being processed
        scope_info: The accumulated scope information
        scope_stack: Stack of scopes for nested function handling

    Example usage:
        Basic usage to analyze Lua code and track variable types:

        1. Parse Lua code with luaparser
        2. Create ScopeAnalyzer instance
        3. Call analyze() to get ScopeInfo
        4. Use get_variable() to look up variable information

        The analyzer identifies parameter types from function signatures
        and tracks local variables that receive creature IDs.
    """

    # Type hints from common variable names
    TYPE_HINTS = {
        # Player-related
        "cid": "player",
        "player": "player",
        "playerid": "player",
        "pid": "player",
        # Creature-related
        "creature": "creature",
        "creatureid": "creature",
        "crid": "creature",
        # Monster-related
        "monster": "monster",
        "monstercid": "monster",
        "mid": "monster",
        # NPC-related
        "npc": "npc",
        "npccid": "npc",
        "nid": "npc",
        # Target/attacker/killer (usually creatures)
        "target": "creature",
        "attacker": "creature",
        "killer": "creature",
        "damager": "creature",
        "lasthitkiller": "creature",
        "mostdamagekiller": "creature",
        # Item-related
        "item": "item",
        "itemid": "item",
        "itemuid": "item",
        "item2": "item",
        "itemex": "item",
        # Position-related
        "pos": "position",
        "position": "position",
        "frompos": "position",
        "topos": "position",
        "fromposition": "position",
        "toposition": "position",
    }

    # Functions that return creature/player IDs
    CREATURE_RETURNING_FUNCTIONS = {
        "getPlayerByName": "player",
        "getCreatureByName": "creature",
        "getMonsterByName": "monster",
        "getNpcByName": "npc",
        "getCreatureTarget": "creature",
        "getCreatureMaster": "creature",
        "getCreatureSummons": "creature",  # Returns array, but element type
        "getPlayerParty": "player",  # Returns Party, but members are players
        "getNpcCid": "npc",
    }

    # Functions that return items
    ITEM_RETURNING_FUNCTIONS = {
        "getPlayerSlotItem": "item",
        "doCreateItem": "item",
        "doCreateItemEx": "item",
        "getTileItemById": "item",
        "getTileItemByType": "item",
        "getTileThingByPos": "item",
        "getThingfromPos": "item",
    }

    def __init__(self, signature_map: Optional[Dict] = None):
        """Initialize the scope analyzer.

        Args:
            signature_map: Optional custom signature map. Defaults to SIGNATURE_MAP.
        """
        self.signature_map = signature_map or SIGNATURE_MAP
        self.current_scope: Optional[Scope] = None
        self.scope_info: Optional[ScopeInfo] = None
        self.scope_stack: List[Scope] = []
        self._current_function_name: Optional[str] = None

    def analyze(self, tree: Node) -> ScopeInfo:
        """Main entry point for scope analysis.

        Traverses the AST and builds scope information.

        Args:
            tree: The parsed Lua AST

        Returns:
            ScopeInfo containing all analyzed scope information
        """
        # Initialize global scope
        self.scope_info = ScopeInfo(global_scope=Scope(parent=None, level=0))
        self.current_scope = self.scope_info.global_scope
        self.scope_stack = [self.current_scope]

        # Visit the tree
        self.visit(tree)

        return self.scope_info

    def _push_scope(self) -> Scope:
        """Create and push a new scope onto the stack.

        Returns:
            The newly created scope
        """
        new_scope = Scope(parent=self.current_scope, level=len(self.scope_stack))
        self.scope_stack.append(new_scope)
        self.current_scope = new_scope
        return new_scope

    def _pop_scope(self) -> Optional[Scope]:
        """Pop the current scope from the stack.

        Returns:
            The popped scope, or None if stack is empty
        """
        if len(self.scope_stack) > 1:
            popped = self.scope_stack.pop()
            self.current_scope = self.scope_stack[-1]
            return popped
        return None

    def get_variable(self, name: str) -> Optional[VariableInfo]:
        """Look up a variable in the current scope chain.

        Args:
            name: The variable name to look up

        Returns:
            VariableInfo if found, None otherwise
        """
        if self.current_scope:
            return self.current_scope.lookup(name)
        return None

    def _infer_param_type(
        self, func_name: str, param_index: int, param_name: str
    ) -> Optional[str]:
        """Infer the type of a function parameter using signature mappings.

        Uses SIGNATURE_MAP to determine the expected type of parameters
        based on the function name and parameter position.

        Args:
            func_name: The name of the function
            param_index: The index of the parameter (0-based)
            param_name: The name of the parameter

        Returns:
            Inferred type string, or None if cannot be determined
        """
        # First check if function is in signature map
        if func_name in self.signature_map:
            old_sig, new_sig = self.signature_map[func_name]

            # Check main params
            old_params = old_sig.get("params", [])
            new_params = new_sig.get("params", [])

            if param_index < len(old_params):
                old_param_name = old_params[param_index]

                # Map to new param name if available
                if param_index < len(new_params):
                    new_param_name = new_params[param_index]

                    # Infer type from new param name
                    if new_param_name in ("player", "cid"):
                        return "player"
                    elif new_param_name in ("creature", "monster", "npc"):
                        return "creature"
                    elif new_param_name == "item":
                        return "item"
                    elif new_param_name == "target":
                        return "creature"

                # Check rename map
                if old_param_name in PARAM_RENAME_MAP:
                    renamed = PARAM_RENAME_MAP[old_param_name]
                    if renamed in ("player",):
                        return "player"
                    elif renamed in ("creature", "target"):
                        return "creature"

            # Check alternative signatures
            alt_params_list = old_sig.get("alt_params", [])
            for alt_params in alt_params_list:
                if param_index < len(alt_params):
                    alt_param_name = alt_params[param_index]
                    if alt_param_name in PARAM_RENAME_MAP:
                        renamed = PARAM_RENAME_MAP[alt_param_name]
                        if renamed in ("player",):
                            return "player"
                        elif renamed in ("creature", "target"):
                            return "creature"

        # Fall back to name-based guessing
        return self._guess_type_from_name(param_name)

    def _guess_type_from_name(self, name: str) -> Optional[str]:
        """Guess variable type based on naming conventions.

        Uses common naming patterns to infer variable types.

        Args:
            name: The variable name

        Returns:
            Guessed type string, or None if cannot be determined
        """
        name_lower = name.lower()

        # Direct match
        if name_lower in self.TYPE_HINTS:
            return self.TYPE_HINTS[name_lower]

        # Pattern matching for common suffixes/prefixes
        if name_lower.startswith("player") or name_lower.endswith("player"):
            return "player"
        if name_lower.startswith("creature") or name_lower.endswith("creature"):
            return "creature"
        if name_lower.startswith("monster") or name_lower.endswith("monster"):
            return "monster"
        if name_lower.startswith("npc") or name_lower.endswith("npc"):
            return "npc"
        if name_lower.startswith("item") or name_lower.endswith("item"):
            return "item"
        if name_lower.startswith("target") or name_lower.endswith("target"):
            return "creature"
        if name_lower.startswith("killer") or name_lower.endswith("killer"):
            return "creature"
        if name_lower.startswith("attacker") or name_lower.endswith("attacker"):
            return "creature"

        return None

    def _analyze_value_type(self, value: Node) -> Optional[str]:
        """Analyze an expression to determine if it's a creature ID.

        Examines function calls, variables, and other expressions to
        determine the type of value they produce.

        Args:
            value: The AST node representing the value

        Returns:
            Inferred type string, or None if cannot be determined
        """
        if value is None:
            return None

        # Handle function calls
        if isinstance(value, Call):
            func = value.func
            func_name = get_function_name(func)

            if func_name:
                # Check creature-returning functions
                if func_name in self.CREATURE_RETURNING_FUNCTIONS:
                    return self.CREATURE_RETURNING_FUNCTIONS[func_name]

                # Check item-returning functions
                if func_name in self.ITEM_RETURNING_FUNCTIONS:
                    return self.ITEM_RETURNING_FUNCTIONS[func_name]

                # Check TFS function mappings
                if func_name in TFS03_TO_1X:
                    mapping = TFS03_TO_1X[func_name]
                    obj_type = mapping.get("obj_type")
                    if obj_type in ("player", "creature", "monster", "npc", "item"):
                        return obj_type

        # Handle method invocations (e.g., player:getName())
        elif isinstance(value, Invoke):
            # The source of the invocation might give us type info
            if hasattr(value, "source") and isinstance(value.source, Name):
                source_name = value.source.id
                source_var = self.get_variable(source_name)
                if source_var:
                    return source_var.var_type

        # Handle variable references
        elif isinstance(value, Name):
            var_name = value.id
            var_info = self.get_variable(var_name)
            if var_info:
                return var_info.var_type

        # Handle numeric literals (could be creature IDs)
        elif isinstance(value, Number):
            # Numeric literals could be creature IDs, but we can't be sure
            return None

        return None

    def _get_renamed_name(self, name: str, var_type: str) -> Optional[str]:
        """Get the renamed name for a variable if applicable.

        Args:
            name: The original variable name
            var_type: The inferred variable type

        Returns:
            The renamed name, or None if no rename needed
        """
        # Check explicit rename map
        if name in PARAM_RENAME_MAP:
            return PARAM_RENAME_MAP[name]

        # Type-based renames
        if name == "cid" and var_type == "player":
            return "player"

        return None

    def _record_variable(self, info: VariableInfo) -> None:
        """Record a variable in the scope info.

        Args:
            info: The variable information to record
        """
        if self.scope_info:
            if info.name not in self.scope_info.all_variables:
                self.scope_info.all_variables[info.name] = []
            self.scope_info.all_variables[info.name].append(info)

    # Visitor methods

    def visit_Function(self, node: Function) -> None:
        """Visit a function definition and create a new scope.

        Creates a new scope for the function and analyzes its parameters
        to determine their types.

        Args:
            node: The Function AST node
        """
        # Push new scope
        new_scope = self._push_scope()

        # Try to determine function name from the node itself
        func_name = "<anonymous>"
        if hasattr(node, "name") and node.name:
            if isinstance(node.name, Name):
                func_name = node.name.id
            elif isinstance(node.name, str):
                func_name = node.name
        elif self._current_function_name:
            func_name = self._current_function_name
            self._current_function_name = None

        # Record this function scope
        if self.scope_info:
            self.scope_info.function_scopes.append((func_name, new_scope))

        # Analyze parameters
        if hasattr(node, "args") and node.args:
            for idx, param in enumerate(node.args):
                if isinstance(param, Name):
                    param_name = param.id

                    # Infer parameter type
                    var_type = self._infer_param_type(func_name, idx, param_name)
                    if var_type is None:
                        var_type = "creature"  # Default fallback

                    # Get renamed name
                    renamed = self._get_renamed_name(param_name, var_type)

                    # Create variable info
                    info = VariableInfo(
                        name=param_name,
                        var_type=var_type,
                        is_param=True,
                        renamed_name=renamed,
                        scope_level=new_scope.level,
                    )

                    # Define in current scope and record
                    new_scope.define(param_name, info)
                    self._record_variable(info)

        # Note: The custom visit() method handles traversal automatically

    def visit_LocalFunction(self, node) -> None:
        """Visit a local function definition and create a new scope.

        Similar to visit_Function but for local function declarations.

        Args:
            node: The LocalFunction AST node
        """
        # Push new scope
        new_scope = self._push_scope()

        # Get function name
        func_name = "<anonymous>"
        if hasattr(node, "name") and node.name:
            if isinstance(node.name, Name):
                func_name = node.name.id
            elif isinstance(node.name, str):
                func_name = node.name
        elif self._current_function_name:
            func_name = self._current_function_name
            self._current_function_name = None

        # Record this function scope
        if self.scope_info:
            self.scope_info.function_scopes.append((func_name, new_scope))

        # Analyze parameters
        if hasattr(node, "args") and node.args:
            for idx, param in enumerate(node.args):
                if isinstance(param, Name):
                    param_name = param.id

                    # Infer parameter type
                    var_type = self._infer_param_type(func_name, idx, param_name)
                    if var_type is None:
                        var_type = "creature"  # Default fallback

                    # Get renamed name
                    renamed = self._get_renamed_name(param_name, var_type)

                    # Create variable info
                    info = VariableInfo(
                        name=param_name,
                        var_type=var_type,
                        is_param=True,
                        renamed_name=renamed,
                        scope_level=new_scope.level,
                    )

                    # Define in current scope and record
                    new_scope.define(param_name, info)
                    self._record_variable(info)

        # Note: The custom visit() method handles traversal automatically

    def visit_AnonymousFunction(self, node: AnonymousFunction) -> None:
        """Visit an anonymous function expression and create a new scope.

        Handles ``onUse = function(cid, ...) end`` assignments where the
        function name is inferred from the enclosing assignment target.

        Args:
            node: The AnonymousFunction AST node
        """
        # Push new scope
        new_scope = self._push_scope()

        # Get function name from previously set context (visit_Assign/_preprocess)
        func_name = "<anonymous>"
        if self._current_function_name:
            func_name = self._current_function_name
            self._current_function_name = None

        # Record this function scope
        if self.scope_info:
            self.scope_info.function_scopes.append((func_name, new_scope))

        # Analyze parameters
        if hasattr(node, "args") and node.args:
            for idx, param in enumerate(node.args):
                if isinstance(param, Name):
                    param_name = param.id

                    var_type = self._infer_param_type(func_name, idx, param_name)
                    if var_type is None:
                        var_type = "creature"

                    renamed = self._get_renamed_name(param_name, var_type)

                    info = VariableInfo(
                        name=param_name,
                        var_type=var_type,
                        is_param=True,
                        renamed_name=renamed,
                        scope_level=new_scope.level,
                    )

                    new_scope.define(param_name, info)
                    self._record_variable(info)

        # Note: The custom visit() method handles traversal automatically

    def visit_LocalAssign(self, node: LocalAssign) -> None:
        """Visit a local variable assignment.

        Tracks local variables that receive creature IDs from function calls.

        Args:
            node: The LocalAssign AST node
        """
        if not hasattr(node, "targets") or not node.targets:
            return

        values = getattr(node, "values", []) or []

        for idx, target in enumerate(node.targets):
            if isinstance(target, Name):
                var_name = target.id

                # Analyze the value being assigned
                var_type = None
                if idx < len(values):
                    var_type = self._analyze_value_type(values[idx])

                # Fall back to name-based guessing
                if var_type is None:
                    var_type = self._guess_type_from_name(var_name)

                # Default to unknown if still not determined
                if var_type is None:
                    var_type = "unknown"

                # Get renamed name
                renamed = self._get_renamed_name(var_name, var_type)

                # Create variable info
                info = VariableInfo(
                    name=var_name,
                    var_type=var_type,
                    is_param=False,
                    renamed_name=renamed,
                    scope_level=self.current_scope.level if self.current_scope else 0,
                )

                # Define in current scope and record
                if self.current_scope:
                    self.current_scope.define(var_name, info)
                self._record_variable(info)

        # Note: The custom visit() method handles traversal automatically

    def visit_Assign(self, node: Assign) -> None:
        """Visit a regular assignment.

        Tracks assignments to existing variables or new global assignments.

        Args:
            node: The Assign AST node
        """
        if not hasattr(node, "targets") or not node.targets:
            return

        values = getattr(node, "values", []) or []

        for idx, target in enumerate(node.targets):
            if isinstance(target, Name):
                var_name = target.id

                # Only process if not already defined in current scope
                if self.current_scope and not self.current_scope.is_defined_locally(
                    var_name
                ):
                    # Analyze the value being assigned
                    var_type = None
                    if idx < len(values):
                        var_type = self._analyze_value_type(values[idx])

                    # Fall back to name-based guessing
                    if var_type is None:
                        var_type = self._guess_type_from_name(var_name)

                    if var_type:
                        # Get renamed name
                        renamed = self._get_renamed_name(var_name, var_type)

                        # Create variable info
                        info = VariableInfo(
                            name=var_name,
                            var_type=var_type,
                            is_param=False,
                            renamed_name=renamed,
                            scope_level=self.current_scope.level
                            if self.current_scope
                            else 0,
                        )

                        # Define in current scope and record
                        self.current_scope.define(var_name, info)
                        self._record_variable(info)

        # Note: The custom visit() method handles traversal automatically

    def visit_Call(self, node: Call) -> None:
        """Visit a function call.

        Analyzes function calls to track variable usage and potentially
        infer types from return values.

        Args:
            node: The Call AST node
        """
        # Continue visiting children
        self.generic_visit(node)

    def visit_Chunk(self, node: Chunk) -> None:
        """Visit the root chunk of the Lua file.

        Args:
            node: The Chunk AST node
        """
        # Process any function assignments at the chunk level
        # to identify function names before visiting them
        if hasattr(node, "body") and hasattr(node.body, "body"):
            for stmt in node.body.body:
                self._preprocess_statement(stmt)

        # Note: The custom visit() method handles traversal automatically

    def _preprocess_statement(self, node: Node) -> None:
        """Preprocess a statement to extract function names.

        This helps identify function names before visiting the function
        nodes themselves, which is useful for parameter type inference.

        Args:
            node: The statement node to preprocess
        """
        # Handle local function declarations
        if isinstance(node, LocalAssign):
            if hasattr(node, "targets") and hasattr(node, "values"):
                for target, value in zip(node.targets, node.values or []):
                    if isinstance(target, Name) and isinstance(value, Function):
                        # Store function name for later use
                        self._current_function_name = target.id

        # Handle global function declarations (assignments to global)
        elif isinstance(node, Assign):
            if hasattr(node, "targets") and hasattr(node, "values"):
                for target, value in zip(node.targets, node.values or []):
                    if isinstance(target, Name) and isinstance(value, Function):
                        self._current_function_name = target.id

    def generic_visit(self, node: Node) -> None:
        """Default visitor that visits all children.

        Args:
            node: The AST node to visit
        """
        # The base ASTVisitor handles child traversal automatically
        # This method is called for nodes without specific visitors
        pass

    def visit(self, root) -> None:
        """Override visit to handle scope management properly.

        We use a custom traversal that pushes scope markers to ensure
        scopes are popped after all children are processed.

        Args:
            root: The root node to visit
        """
        if root is None:
            return

        # Use a special marker object for scope popping
        class ScopePopMarker:
            pass

        # Stack contains tuples of (node, visited_flag)
        # visited_flag is False when first pushed, True after children processed
        node_stack = [(root, False)]

        while len(node_stack) > 0:
            node, visited = node_stack.pop()

            if isinstance(node, ScopePopMarker):
                # Scope marker - pop the scope
                self._pop_scope()
                continue

            if isinstance(node, Node):
                if not visited:
                    # First time seeing this node - process it
                    name = "visit_" + node.__class__.__name__
                    visitor = getattr(self, name, None)

                    # Check if this is a function node that creates a scope
                    # Note: LocalFunction is a separate type in luaparser
                    is_function_node = (
                        isinstance(node, (Function, AnonymousFunction))
                        or node.__class__.__name__ == "LocalFunction"
                    )

                    if is_function_node:
                        # Push a marker to pop scope after children
                        node_stack.append((ScopePopMarker(), False))

                    # Push node back as "visited" to process after children
                    node_stack.append((node, True))

                    # Call the visitor (which may push a new scope)
                    if visitor:
                        visitor(node)

                    # Push children in reverse order so they're processed left-to-right
                    children = [
                        attr
                        for attr in node.__dict__.keys()
                        if not attr.startswith("_")
                    ]
                    for child in reversed(children):
                        node_stack.append((node.__dict__[child], False))

                else:
                    # Node has been processed - nothing to do
                    pass

            elif isinstance(node, list):
                # Push list items in reverse order
                for item in reversed(node):
                    node_stack.append((item, False))


def analyze_scope(tree: Node, signature_map: Optional[Dict] = None) -> ScopeInfo:
    """Convenience function to analyze scope of a Lua AST.

    Args:
        tree: The parsed Lua AST
        signature_map: Optional custom signature map

    Returns:
        ScopeInfo containing all analyzed scope information
    """
    analyzer = ScopeAnalyzer(signature_map)
    return analyzer.analyze(tree)


# Type checking helpers
def is_creature_variable(var_info: Optional[VariableInfo]) -> bool:
    """Check if a variable represents a creature/player.

    Args:
        var_info: The variable information

    Returns:
        True if the variable is a creature type
    """
    if var_info is None:
        return False
    return var_info.var_type in ("player", "creature", "monster", "npc")


def is_player_variable(var_info: Optional[VariableInfo]) -> bool:
    """Check if a variable represents a player.

    Args:
        var_info: The variable information

    Returns:
        True if the variable is a player type
    """
    if var_info is None:
        return False
    return var_info.var_type == "player"


def needs_wrapper(var_info: Optional[VariableInfo]) -> bool:
    """Check if a variable needs a wrapper class (e.g., Player(), Creature()).

    In TFS 1.x, creature IDs from TFS 0.3/0.4 need to be wrapped in
    their appropriate class constructors.

    Args:
        var_info: The variable information

    Returns:
        True if the variable needs wrapping
    """
    if var_info is None:
        return False
    # Parameters typically don't need wrapping (they're already objects in 1.x)
    # Local variables that were assigned from getCreatureByName, etc. need wrapping
    return not var_info.is_param and is_creature_variable(var_info)
