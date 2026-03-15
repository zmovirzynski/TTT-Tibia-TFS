"""AST Transform Visitor for TFS Lua code conversion.

This module provides the ASTTransformVisitor class that transforms Lua AST
from TFS 0.3/0.4 format to TFS 1.x format using defensive programming techniques.
"""

from typing import Dict, List, Optional, Tuple, Any
from luaparser import ast
from luaparser.astnodes import (
    Node,
    Function,
    AnonymousFunction,
    LocalFunction,
    Call,
    Invoke,
    Name,
    Index,
    LocalAssign,
    Assign,
    Block,
    If,
    ElseIf,
    Return,
    String,
    Number,
    Table,
    TrueExpr,
    FalseExpr,
    Nil,
    Chunk,
    While,
    Repeat,
    Fornum,
    Forin,
    ULNotOp,
)

from .scope_analyzer import ScopeAnalyzer, ScopeInfo, VariableInfo, Scope
from .ast_utils import get_function_name, get_base_name, get_wrapper_class
from ..mappings.signatures import SIGNATURE_MAP, PARAM_RENAME_MAP
from ..mappings.constants import ALL_CONSTANTS
from ..mappings.tfs03_functions import TFS03_TO_1X


class ASTTransformVisitor(ast.ASTVisitor):
    """Transforms Lua AST from TFS 0.3/0.4 to TFS 1.x format.

    This visitor applies transformations with defensive programming:
    - Function parameters are used directly as objects
    - Local variables get wrapped with type checking

    Attributes:
        scope_info: ScopeInfo from ScopeAnalyzer
        function_map: Mapping of old function names to new method mappings
        stats: Dictionary to track transformation statistics
        current_function_scope: Current function scope being processed
        temp_var_counter: Counter for generating unique temp variable names
        defensive_checks: List of defensive check statements to insert
        warnings: List of warning messages from transformations
        param_renames: Dictionary mapping old param names to new names in current function
    """

    def __init__(self, scope_info: ScopeInfo, function_map: Dict, stats: Dict):
        """Initialize the AST transform visitor.

        Args:
            scope_info: ScopeInfo from ScopeAnalyzer containing variable information
            function_map: Mapping of old function names to transformation mappings
            stats: Dictionary to track transformation statistics
        """
        self.scope_info = scope_info
        self.function_map = function_map
        self.stats = stats
        self.current_function_scope: Optional[Scope] = None
        self.current_function_name: str = ""
        self.temp_var_counter = 0
        self.defensive_checks: List = []
        self.warnings: List[str] = []
        self.param_renames: Dict[str, str] = {}
        self.scope_stack: List[Scope] = []
        self.notes: List[str] = []
        self._function_scope_index = 0

    def transform(self, tree: Node) -> None:
        """Main entry point - transforms the AST in place.

        Args:
            tree: The Lua AST to transform
        """
        self.visit(tree)

    def _get_next_temp_var(self, var_type: str) -> str:
        """Generate a unique temporary variable name.

        Args:
            var_type: The type of variable (e.g., 'player', 'creature')

        Returns:
            A unique variable name like '__ast_player_1'
        """
        self.temp_var_counter += 1
        return f"__ast_{var_type}_{self.temp_var_counter}"

    def _create_defensive_wrapper(
        self, var_name: str, var_type: str, obj_arg: Node
    ) -> Tuple[str, List]:
        """Create defensive wrapper for a variable.

        Creates statements that:
        1. Create a wrapper object (e.g., Player(target))
        2. Check if it's nil
        3. Print error message and return true if nil

        Args:
            var_name: The original variable name (for error message)
            var_type: The type of object to wrap
            obj_arg: The AST node representing the argument to wrap

        Returns:
            Tuple of (temp_var_name, list_of_statements)
        """
        temp_var = self._get_next_temp_var(var_type)
        wrapper_class = get_wrapper_class(var_type)

        # Create: local __ast_player_1 = Player(target)
        local_assign = LocalAssign(
            targets=[Name(temp_var)],
            values=[Call(func=Name(wrapper_class), args=[obj_arg])],
        )

        # Create: if not __ast_player_1 then ... end
        error_msg = f"[AST] Failed to create {wrapper_class} from {var_name}"
        if_node = If(
            test=ULNotOp(operand=Name(temp_var)),
            body=Block(
                body=[
                    # print("[AST] Failed to create Player from target")
                    Call(
                        func=Name("print"),
                        args=[String(error_msg.encode("utf-8"), error_msg)],
                    ),
                    # return true
                    Return([TrueExpr()]),
                ]
            ),
            orelse=None,
        )

        statements = [local_assign, if_node]

        self.stats["defensive_checks_added"] += 1
        return temp_var, statements

    def _is_parameter(self, var_name: str) -> bool:
        """Check if a variable is a function parameter.

        Args:
            var_name: The variable name to check

        Returns:
            True if the variable is a parameter in current scope
        """
        if not self.current_function_scope:
            return False
        var_info = self.current_function_scope.lookup(var_name)
        if var_info:
            return var_info.is_param
        return False

    def _get_variable_info(self, var_name: str) -> Optional[VariableInfo]:
        """Get variable info from current scope.

        Args:
            var_name: The variable name to look up

        Returns:
            VariableInfo if found, None otherwise
        """
        if not self.current_function_scope:
            return self.scope_info.global_scope.lookup(var_name)
        return self.current_function_scope.lookup(var_name)

    def _get_renamed_variable(self, var_name: str) -> Optional[str]:
        """Get the renamed version of a variable if it exists.

        Args:
            var_name: Original variable name

        Returns:
            Renamed variable name or None if not renamed
        """
        # Check param_renames first
        if var_name in self.param_renames:
            return self.param_renames[var_name]

        # Check PARAM_RENAME_MAP and verify it's a parameter
        if var_name in PARAM_RENAME_MAP:
            var_info = self._get_variable_info(var_name)
            if var_info and var_info.is_param:
                return PARAM_RENAME_MAP[var_name]

        return None

    def _transform_function_call(
        self, node: Call, func_name: str, mapping: Dict
    ) -> Optional[List]:
        """Transform a single function call.

        Transforms a function call from TFS 0.3/0.4 format to TFS 1.x format.
        For parameters: direct method call (player:getLevel())
        For local vars: defensive wrapper with nil check

        Args:
            node: The Call AST node
            func_name: The original function name
            mapping: The transformation mapping

        Returns:
            List of statements to insert before the call (defensive checks),
            or None if no transformation needed.
        """
        statements_to_insert = []

        # Get object parameter index
        obj_param_idx = mapping.get("obj_param", 0)
        if obj_param_idx is None:
            # Static function call (e.g., Game.createItem)
            return None

        # Get the object argument
        args = getattr(node, "args", []) or []
        if obj_param_idx >= len(args):
            self.warnings.append(
                f"Function {func_name} missing object parameter at index {obj_param_idx}"
            )
            return None

        obj_arg = args[obj_param_idx]

        # Determine if we need defensive wrapper
        needs_wrapper = False
        var_name = None
        var_type = mapping.get("obj_type", "creature")

        if isinstance(obj_arg, Name):
            var_name = obj_arg.id

            # FIX: Check if variable was renamed and use new name
            renamed_name = self._get_renamed_variable(var_name)
            if renamed_name:
                var_name = renamed_name
                # Update the argument to use renamed variable
                obj_arg.id = var_name

            if self._is_parameter(var_name):
                # It's a parameter - use directly
                needs_wrapper = False
            else:
                # It's a local variable - need wrapper
                var_info = self._get_variable_info(var_name)
                if var_info and not var_info.is_param:
                    needs_wrapper = True
                    var_type = var_info.var_type or var_type
        elif isinstance(obj_arg, Call):
            # Nested call - need to transform it first and wrap result
            nested_statements = self._transform_call_recursive(obj_arg)
            if nested_statements:
                statements_to_insert.extend(nested_statements)

            # Create wrapper for the nested call result
            temp_var, wrapper_statements = self._create_defensive_wrapper(
                "result", var_type, obj_arg
            )
            statements_to_insert.extend(wrapper_statements)

            # Replace the argument with the temp variable
            node.args[obj_param_idx] = Name(temp_var)
            needs_wrapper = False  # Already wrapped

        if needs_wrapper and var_name:
            # Create defensive wrapper
            temp_var, wrapper_statements = self._create_defensive_wrapper(
                var_name, var_type, Name(var_name)
            )
            statements_to_insert.extend(wrapper_statements)

            # Replace the argument with the temp variable
            node.args[obj_param_idx] = Name(temp_var)

        # Transform the call to method invocation
        method_name = mapping.get("method")
        if method_name:
            # Create method invocation: obj:method(args...)
            new_args = [
                arg
                for i, arg in enumerate(args)
                if i not in mapping.get("drop_params", [])
            ]

            # Replace the function call with method invocation
            obj_node = (
                node.args[obj_param_idx] if obj_param_idx < len(node.args) else obj_arg
            )

            # Create the method invoke node
            method_invoke = Invoke(
                source=obj_node, func=Name(method_name), args=new_args
            )

            # --- Node-class mutation: luaparser serializes by __class__.__name__, so we
            # must change the class to produce "obj:method()" output.  We also set every
            # attribute that Invoke.__init__ would set so the node is fully valid.
            # isinstance() checks on this node will return True for Invoke after this.
            node.__class__ = Invoke
            node.source = obj_node
            node.func = Name(method_name)
            node.args = new_args

            self.stats["functions_converted"] += 1

            note = mapping.get("note")
            if note:
                self.notes.append(note)

        return statements_to_insert if statements_to_insert else None

    def _transform_call_recursive(self, node: Call) -> Optional[List]:
        """Recursively transform nested calls.

        Args:
            node: The Call AST node

        Returns:
            List of statements to insert
        """
        func_name = get_function_name(node.func)
        if not func_name:
            return None

        if func_name in self.function_map:
            mapping = self.function_map[func_name]
            return self._transform_function_call(node, func_name, mapping)

        return None

    def _enter_function_scope(self, func_name: str, params) -> None:
        """Set up scope tracking and apply signature transformation for a function.

        Args:
            func_name: The function name (or '<anonymous>').
            params: The mutable parameter node list from the function AST node.
        """
        self.current_function_name = func_name

        # Try to find the scope by name first (robust against traversal-order differences)
        matched_scope = self._find_scope_for_function(func_name)
        if matched_scope is not None:
            self.current_function_scope = matched_scope
        else:
            # Fall back to sequential index (handles anonymous functions with no name)
            if self._function_scope_index < len(self.scope_info.function_scopes):
                _, self.current_function_scope = self.scope_info.function_scopes[
                    self._function_scope_index
                ]
                self._function_scope_index += 1
            else:
                self.current_function_scope = Scope(
                    parent=self.scope_info.global_scope, level=1
                )

        self.scope_stack.append(self.current_function_scope)

        if func_name in SIGNATURE_MAP and params is not None:
            old_sig, new_sig = SIGNATURE_MAP[func_name]
            old_params = old_sig.get("params", [])
            new_params = new_sig.get("params", [])

            for i, param in enumerate(params):
                if isinstance(param, Name) and i < len(old_params):
                    old_name = old_params[i]
                    if i < len(new_params):
                        new_name = new_params[i]
                        if old_name != new_name:
                            self.param_renames[old_name] = new_name
                            param.id = new_name
                            self.stats["signatures_updated"] += 1

            current_count = len(params)
            for i in range(current_count, len(new_params)):
                params.append(Name(new_params[i]))
                self.stats["signatures_updated"] += 1

    def _exit_function_scope(self) -> None:
        """Tear down scope tracking after visiting a function's body."""
        if self.scope_stack:
            self.scope_stack.pop()
        self.current_function_scope = self.scope_stack[-1] if self.scope_stack else None
        self.param_renames = {}

    def _find_scope_for_function(self, func_name: str) -> Optional[Scope]:
        """Find the scope entry matching func_name, skipping already-consumed entries.

        Uses a per-name counter so that two functions with the same name get
        different scopes in the order they were visited during analysis.

        Args:
            func_name: The function name to look up.

        Returns:
            The matching Scope, or None if not found.
        """
        if func_name == "<anonymous>":
            return None  # Can't disambiguate anonymous functions by name alone

        if not hasattr(self, "_scope_name_counters"):
            self._scope_name_counters: Dict[str, int] = {}

        visit_count = self._scope_name_counters.get(func_name, 0)
        matches = [
            scope
            for name, scope in self.scope_info.function_scopes
            if name == func_name
        ]

        if visit_count < len(matches):
            self._scope_name_counters[func_name] = visit_count + 1
            return matches[visit_count]

        return None

    def visit_Function(self, node: Function) -> None:
        func_name = "<anonymous>"
        if hasattr(node, "name") and node.name:
            if isinstance(node.name, Name):
                func_name = node.name.id
            elif isinstance(node.name, str):
                func_name = node.name
        elif hasattr(self, "_current_function_name") and self._current_function_name:
            func_name = self._current_function_name
            self._current_function_name = None
        params = node.args if hasattr(node, "args") and node.args is not None else []
        self._enter_function_scope(func_name, params)
        self.generic_visit(node)
        self._exit_function_scope()

    def visit_LocalFunction(self, node) -> None:
        func_name = "<anonymous>"
        if hasattr(node, "name") and node.name:
            if isinstance(node.name, Name):
                func_name = node.name.id
            elif isinstance(node.name, str):
                func_name = node.name
        elif hasattr(self, "_current_function_name") and self._current_function_name:
            func_name = self._current_function_name
            self._current_function_name = None
        params = node.args if hasattr(node, "args") and node.args is not None else []
        self._enter_function_scope(func_name, params)
        self.generic_visit(node)
        self._exit_function_scope()

    def visit_AnonymousFunction(self, node: AnonymousFunction) -> None:
        func_name = "<anonymous>"
        if hasattr(self, "_current_function_name") and self._current_function_name:
            func_name = self._current_function_name
            self._current_function_name = None
        params = node.args if hasattr(node, "args") and node.args is not None else []
        self._enter_function_scope(func_name, params)
        self.generic_visit(node)
        self._exit_function_scope()

    def visit_Call(self, node: Call) -> None:
        """Transform function calls with defensive checks.

        Checks if the function is in the function_map and applies
        appropriate transformations with defensive programming.

        Args:
            node: The Call AST node
        """
        func_name = get_function_name(node.func)
        if not func_name:
            self.generic_visit(node)
            return

        if func_name in self.function_map:
            mapping = self.function_map[func_name]

            # TRACKING: Check for old API calls with suspicious variable names
            obj_param_idx = mapping.get("obj_param", 0)
            if obj_param_idx is not None:
                args = getattr(node, "args", []) or []
                if obj_param_idx < len(args):
                    obj_arg = args[obj_param_idx]
                    if isinstance(obj_arg, Name):
                        var_name = obj_arg.id
                        # Check if variable should have been renamed but wasn't
                        if var_name in PARAM_RENAME_MAP:
                            var_info = self._get_variable_info(var_name)
                            if not var_info:
                                self.warnings.append(
                                    f"Function '{func_name}' called with '{var_name}' "
                                    f"which should be renamed but scope info not found"
                                )

            # Check if it's a static call
            if mapping.get("static"):
                # Transform to static call (e.g., Game.createItem)
                static_class = mapping.get("static_class", "Game")
                method_name = mapping.get("method", func_name)

                # Replace with Class.method(args)
                node.func = Index(
                    value=Name(static_class),
                    idx=String(method_name.encode("utf-8"), method_name),
                )

                self.stats["functions_converted"] += 1
            else:
                # Transform to method call with potential defensive wrapper
                statements = self._transform_function_call(node, func_name, mapping)
                if statements:
                    # Store defensive checks to be inserted by parent
                    self.defensive_checks.extend(statements)
        else:
            # Check for custom transformations
            self._handle_custom_transformations(node, func_name)

        # Continue visiting children
        self.generic_visit(node)

    def _handle_custom_transformations(self, node: Call, func_name: str) -> None:
        """Handle custom transformation cases.

        Args:
            node: The Call AST node
            func_name: The function name
        """
        # Handle type check functions (isPlayer, isCreature, etc.)
        if func_name in ("isPlayer", "isCreature", "isMonster", "isNpc"):
            custom_class = TFS03_TO_1X.get(func_name, {}).get("custom_class")
            if custom_class:
                args = getattr(node, "args", []) or []
                if args:
                    # Transform to: obj:isPlayer() or Player(obj) ~= nil
                    obj_arg = args[0]
                    node.func = Index(
                        value=obj_arg,
                        idx=String(
                            f"is{custom_class}".encode("utf-8"), f"is{custom_class}"
                        ),
                    )
                    node.args = []
                    self.stats["functions_converted"] += 1

    def visit_Name(self, node: Name) -> None:
        """Rename variables and replace constants."""
        # Check for constant replacement first
        if node.id in ALL_CONSTANTS:
            node.id = ALL_CONSTANTS[node.id]
            self.stats["constants_replaced"] += 1
            self.generic_visit(node)
            return

        # Check if this name was renamed in current function
        if node.id in self.param_renames:
            node.id = self.param_renames[node.id]
            self.stats["variables_renamed"] += 1
        elif node.id in PARAM_RENAME_MAP:
            # Check if it's a parameter in current scope
            var_info = self._get_variable_info(node.id)
            if var_info and var_info.is_param:
                node.id = PARAM_RENAME_MAP[node.id]
                self.stats["variables_renamed"] += 1

        # Continue visiting children
        self.generic_visit(node)

    def visit_Index(self, node: Index) -> None:
        """Replace constants using ALL_CONSTANTS mapping.

        Transforms table access like CONST_ME_MAGIC to new constant names.

        Args:
            node: The Index AST node
        """
        # Check if this is a constant access (e.g., CONST_ME_MAGIC)
        if isinstance(node.value, Name):
            base_name = node.value.id
            if isinstance(node.idx, String):
                const_name = f"{base_name}.{node.idx.s}"
            else:
                const_name = base_name

            # Check for constant replacement
            if const_name in ALL_CONSTANTS:
                new_const = ALL_CONSTANTS[const_name]
                if "." in new_const:
                    # Split into table and field
                    parts = new_const.split(".")
                    node.value = Name(parts[0])
                    node.idx = String(parts[1].encode("utf-8"), parts[1])
                else:
                    # Just a name replacement
                    node.value = Name(new_const)
                    # Keep the same idx if it's a simple rename
                self.stats["constants_replaced"] += 1
            elif base_name in ALL_CONSTANTS:
                # Direct name replacement
                node.value = Name(ALL_CONSTANTS[base_name])
                self.stats["constants_replaced"] += 1

        # Continue visiting children
        self.generic_visit(node)

    def visit_Table(self, node: Table) -> None:
        """Transform position tables to Position constructor.

        Transforms {x=100, y=100, z=7} to Position(100, 100, 7).

        Args:
            node: The Table AST node
        """
        # Check if this looks like a position table
        if hasattr(node, "fields") and node.fields:
            field_names = set()
            field_values = {}

            for field in node.fields:
                if hasattr(field, "key") and field.key:
                    if isinstance(field.key, Name):
                        field_names.add(field.key.id)
                        field_values[field.key.id] = field.value
                    elif isinstance(field.key, String):
                        field_names.add(field.key.s)
                        field_values[field.key.s] = field.value

            # Check for position pattern {x=..., y=..., z=...}
            if "x" in field_names and "y" in field_names and "z" in field_names:
                # Transform to Position(x, y, z)
                x_val = field_values.get("x", Number(0))
                y_val = field_values.get("y", Number(0))
                z_val = field_values.get("z", Number(0))

                # Create Position constructor call
                position_call = Call(func=Name("Position"), args=[x_val, y_val, z_val])

                # --- Node-class mutation: transform table literal into a constructor call.
                # luaparser serializes Call nodes as "func(args)", which gives us Position(x,y,z).
                node.__class__ = Call
                node.func = Name("Position")
                node.args = [x_val, y_val, z_val]
                # Clear the 'fields' attribute so the serializer doesn't see stale Table data.
                node.fields = []

                self.stats["functions_converted"] += 1

        # Continue visiting children
        self.generic_visit(node)

    def visit_Block(self, node: Block) -> None:
        """Visit a block and insert defensive checks.

        This is where we insert any accumulated defensive checks.

        Args:
            node: The Block AST node
        """
        if not hasattr(node, "body"):
            return

        # Process each statement in the block individually
        # to properly insert defensive checks BEFORE the statement that needs them
        i = 0
        while i < len(node.body):
            stmt = node.body[i]

            # Clear defensive checks before visiting this statement
            old_checks = self.defensive_checks
            self.defensive_checks = []

            # Visit the statement
            self.visit(stmt)

            # If defensive checks were generated during this statement's visitation,
            # insert them BEFORE this statement
            if self.defensive_checks:
                # Insert defensive checks before the current statement
                node.body[i:i] = self.defensive_checks
                # Move index past the inserted checks and the original statement
                i += len(self.defensive_checks) + 1
            else:
                i += 1

            # Restore any accumulated checks from parent context
            self.defensive_checks = old_checks

    def visit_Assign(self, node: Assign) -> None:
        """Visit an assignment and handle special cases.

        Args:
            node: The Assign AST node
        """
        # Handle function assignments (e.g., function onUse(cid, item) ... end)
        if hasattr(node, "values") and node.values:
            for value in node.values:
                if isinstance(value, Function):
                    # This is a function assignment, the name is in targets
                    if hasattr(node, "targets") and node.targets:
                        for target in node.targets:
                            if isinstance(target, Name):
                                # Set function name for scope tracking
                                self._current_function_name = target.id

        # Continue visiting children
        self.generic_visit(node)

    def visit_LocalAssign(self, node: LocalAssign) -> None:
        """Visit a local assignment and handle special cases.

        Args:
            node: The LocalAssign AST node
        """
        # Similar to visit_Assign for local functions
        if hasattr(node, "values") and node.values:
            for value in node.values:
                if isinstance(value, Function):
                    if hasattr(node, "targets") and node.targets:
                        for target in node.targets:
                            if isinstance(target, Name):
                                self._current_function_name = target.id

        # Continue visiting children - defensive checks are handled by visit_Block
        self.generic_visit(node)

    def generic_visit(self, node: Node) -> None:
        """Default visitor that visits all children.

        Args:
            node: The AST node to visit
        """
        # Visit all child nodes
        for attr_name in dir(node):
            if attr_name.startswith("_"):
                continue
            # Skip properties that access _tokens (luaparser 4.0.0 compatibility)
            if attr_name in ("line", "column", "linespan"):
                continue
            try:
                attr = getattr(node, attr_name)
            except AttributeError:
                continue
            if isinstance(attr, Node):
                self.visit(attr)
            elif isinstance(attr, list):
                for item in attr:
                    if isinstance(item, Node):
                        self.visit(item)

    def visit(self, root) -> None:
        """Override visit to handle the traversal properly.

        Args:
            root: The root node to visit
        """
        if root is None:
            return

        # Use iterative traversal to avoid stack overflow
        stack = [root]
        visited = set()

        while stack:
            node = stack.pop()

            if isinstance(node, Node):
                node_id = id(node)
                if node_id in visited:
                    continue
                visited.add(node_id)

                # Call the specific visitor
                name = "visit_" + node.__class__.__name__
                visitor = getattr(self, name, self.generic_visit)
                visitor(node)

            elif isinstance(node, list):
                # Push list items in reverse order
                for item in reversed(node):
                    stack.append(item)


def transform_ast(
    tree: Node,
    scope_info: ScopeInfo,
    function_map: Optional[Dict] = None,
    stats: Optional[Dict] = None,
) -> Tuple[Node, Dict]:
    """Convenience function to transform a Lua AST.

    Args:
        tree: The parsed Lua AST
        scope_info: ScopeInfo from ScopeAnalyzer
        function_map: Optional custom function map. Defaults to TFS03_TO_1X.
        stats: Optional stats dictionary. Will be created if not provided.

    Returns:
        Tuple of (transformed_tree, stats_dict)
    """
    if function_map is None:
        function_map = TFS03_TO_1X

    if stats is None:
        stats = {
            "functions_converted": 0,
            "signatures_updated": 0,
            "constants_replaced": 0,
            "variables_renamed": 0,
            "defensive_checks_added": 0,
        }

    visitor = ASTTransformVisitor(scope_info, function_map, stats)
    visitor.transform(tree)

    return tree, stats
