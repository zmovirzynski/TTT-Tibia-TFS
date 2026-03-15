"""AST-based Lua transformer for TFS script conversion.

This module provides the ASTLuaTransformer class, which is a drop-in replacement
for the regex-based LuaTransformer. It uses AST-based transformation for better
accuracy and scope-aware variable tracking, with automatic fallback to regex
transformation when AST parsing fails.

Features:
    - Accurate parsing using luaparser (no regex limitations)
    - Scope-aware variable tracking for defensive programming
    - Automatic defensive checks for local variables that aren't function parameters
    - Fallback to regex transformer on AST errors
    - Compatible interface with the original LuaTransformer

Example:
    >>> from ttt.converters.ast_lua_transformer import ASTLuaTransformer
    >>> from ttt.mappings.functions import FUNCTION_MAP
    >>>
    >>> transformer = ASTLuaTransformer(FUNCTION_MAP, source_version="tfs03")
    >>> result = transformer.transform(lua_code, filename="test.lua")
    >>> print(transformer.get_summary())
"""

import logging
from typing import Dict, List, Optional

try:
    from luaparser import ast

    LUAPARSER_AVAILABLE = True
except ImportError:
    LUAPARSER_AVAILABLE = False

from .scope_analyzer import ScopeAnalyzer, ScopeInfo
from .ast_transform_visitor import ASTTransformVisitor
from ..mappings.signatures import SIGNATURE_MAP
from .lua_transformer import LuaTransformer

logger = logging.getLogger("ttt")


class ASTLuaTransformer:
    """Transforms Lua code using AST analysis for better accuracy.

    This transformer uses luaparser to build an AST, analyzes scopes to track
    variable types, and applies transformations with defensive programming
    for variables that are not function parameters.

    The transformer implements a dual-strategy approach:
    1. First attempts AST-based transformation for maximum accuracy
    2. Falls back to regex-based transformation if AST parsing fails

    This ensures robustness while providing better results when possible.

    Attributes:
        function_map: Dictionary mapping old function names to new ones
        source_version: Source TFS version (e.g., "tfs03", "tfs04")
        warnings: List of warning messages from transformation
        stats: Dictionary tracking transformation statistics

    Example:
        >>> transformer = ASTLuaTransformer(FUNCTION_MAP, "tfs03")
        >>> result = transformer.transform("local cid = doPlayerAddItem(uid, 2160, 100)")
        >>> print(transformer.stats["functions_converted"])
        1
    """

    def __init__(self, function_map: Dict, source_version: str = "tfs03"):
        """Initialize the AST Lua transformer.

        Args:
            function_map: Dictionary mapping old function names to new ones.
                         Keys are old function names, values are new names.
            source_version: Source TFS version ("tfs03" or "tfs04").
                          Determines which compatibility transformations to apply.

        Example:
            >>> function_map = {"doPlayerAddItem": "Player.addItem"}
            >>> transformer = ASTLuaTransformer(function_map, "tfs03")
        """
        self.function_map = function_map
        self.source_version = source_version
        self.warnings: List[str] = []
        self.stats = {
            "functions_converted": 0,
            "signatures_updated": 0,
            "constants_replaced": 0,
            "variables_renamed": 0,
            "defensive_checks_added": 0,
        }
        self._fallback_transformer: Optional[LuaTransformer] = None
        self._notes: List[str] = []

    def transform(self, code: str, filename: str = "") -> str:
        """Transform Lua code from TFS 0.3/0.4 to TFS 1.x format.

        This is the main entry point for code transformation. It implements
        a dual-strategy approach:
        1. First attempts AST-based transformation for accuracy
        2. Falls back to regex-based transformation if AST fails

        The method handles various error conditions gracefully and always
        attempts to produce valid output, even if it means using the less
        accurate regex transformer.

        Args:
            code: The Lua source code to transform.
            filename: Optional filename for error reporting and context.
                     Used in warning messages to help identify problematic files.

        Returns:
            Transformed Lua code in TFS 1.x format.

        Raises:
            Does not raise exceptions. All errors are caught and result in
            fallback to regex transformer.

        Example:
            >>> code = "local cid = doPlayerAddItem(uid, 2160, 100)"
            >>> result = transformer.transform(code, "items.lua")
            >>> print(result)
            local cid = Player(uid):addItem(2160, 100)
        """
        self.warnings = []
        self._reset_stats()

        # Check if luaparser is available
        if not LUAPARSER_AVAILABLE:
            logger.warning("luaparser not available, using regex transformer")
            self.warnings.append("luaparser not available. Used regex fallback.")
            return self._transform_with_regex(code, filename)

        try:
            return self._transform_with_ast(code, filename)
        except ImportError as e:
            # luaparser not available or missing components
            logger.warning(f"luaparser import error for {filename}: {e}")
            self.warnings.append(f"luaparser import error: {e}. Used regex fallback.")
            return self._transform_with_regex(code, filename)
        except SyntaxError as e:
            # Invalid Lua syntax that parser can't handle
            logger.warning(f"Syntax error in {filename}: {e}")
            self.warnings.append(f"Syntax error: {e}. Used regex fallback.")
            return self._transform_with_regex(code, filename)
        except Exception as e:
            # Any other error during AST transformation
            logger.error(f"AST transformation error in {filename}: {e}")
            self.warnings.append(f"AST transformation error: {e}. Used regex fallback.")
            return self._transform_with_regex(code, filename)

    def _transform_with_ast(self, code: str, filename: str) -> str:
        """Transform Lua code using AST-based approach.

        This internal method performs the actual AST-based transformation:
        1. Parses the code into an AST
        2. Analyzes scopes to track variable types and origins
        3. Applies transformations using the visitor pattern
        4. Generates transformed code from the modified AST
        5. Post-processes the result for clean output

        Args:
            code: The Lua source code to transform.
            filename: Filename for context in error messages.

        Returns:
            Transformed Lua code.

        Raises:
            SyntaxError: If the Lua code has syntax errors.
            Exception: For other parsing or transformation errors.
        """
        logger.debug(f"Starting AST transformation for {filename}")

        # 1. Parse code to AST
        try:
            tree = ast.parse(code)
        except Exception as e:
            raise SyntaxError(f"Failed to parse Lua code: {e}")

        # 2. Analyze scopes to track variable types and origins
        scope_analyzer = ScopeAnalyzer(SIGNATURE_MAP)
        scope_info = scope_analyzer.analyze(tree)

        logger.debug(
            f"Scope analysis complete: {len(scope_info.function_scopes)} scope(s) found"
        )

        # 3. Transform AST using visitor pattern
        visitor = ASTTransformVisitor(
            scope_info=scope_info, function_map=self.function_map, stats=self.stats
        )
        visitor.transform(tree)

        # Transfer visitor warnings and notes to transformer
        self.warnings.extend(visitor.warnings)
        self._notes = getattr(visitor, "notes", [])

        logger.debug(
            f"AST transformation complete: {self.stats['functions_converted']} function(s) converted"
        )

        # 4. Generate code from transformed AST
        result = ast.to_lua_source(tree)

        # 5. Post-process (cleanup formatting)
        result = self._post_process(result)

        # Append collected notes as TTT comments
        if self._notes:
            notes_block = "\n".join(f"-- {note}" for note in self._notes)
            result = result + "\n\n" + notes_block

        return result

    def _transform_with_regex(self, code: str, filename: str) -> str:
        """Transform Lua code using regex-based fallback.

        This method is called when AST transformation fails. It uses the
        original LuaTransformer to provide a best-effort transformation.

        Stats and warnings from the fallback transformer are merged into
        this transformer's state.

        Args:
            code: The Lua source code to transform.
            filename: Filename for context.

        Returns:
            Transformed Lua code using regex-based approach.
        """
        logger.info(f"Using regex fallback for {filename}")

        # Lazy initialization of fallback transformer
        if self._fallback_transformer is None:
            self._fallback_transformer = LuaTransformer(
                self.function_map, self.source_version
            )

        # Perform regex-based transformation
        result = self._fallback_transformer.transform(code, filename)

        # Merge stats from fallback transformer
        for key in self.stats:
            if key in self._fallback_transformer.stats:
                self.stats[key] = self._fallback_transformer.stats[key]

        # Merge warnings from fallback transformer
        self.warnings.extend(self._fallback_transformer.warnings)

        return result

    def _reset_stats(self):
        """Reset all statistics counters to zero.

        This is called at the beginning of each transform operation
        to ensure stats are fresh for the current file.
        """
        for key in self.stats:
            self.stats[key] = 0

    def _post_process(self, code: str) -> str:
        """Post-process generated code for clean formatting.

        Applies formatting cleanup to the generated code:
        - Removes excessive blank lines (more than 2 consecutive newlines)
        - Ensures consistent line endings

        Args:
            code: The generated Lua code.

        Returns:
            Cleaned up Lua code.
        """
        # Remove excessive blank lines (more than 2 consecutive)
        while "\n\n\n" in code:
            code = code.replace("\n\n\n", "\n\n")

        # Strip trailing whitespace from lines
        lines = [line.rstrip() for line in code.split("\n")]
        code = "\n".join(lines)

        return code

    def get_summary(self) -> str:
        """Get a summary of transformations applied.

        Returns a human-readable string describing what transformations
        were applied during the last transform operation. Only includes
        non-zero statistics.

        Returns:
            Summary string describing transformations, or "No changes" if
            nothing was transformed.

        Example:
            >>> result = transformer.transform(code, "test.lua")
            >>> print(transformer.get_summary())
            "3 function call(s) converted, 1 signature(s) updated, 2 defensive check(s) added"
        """
        parts = []

        if self.stats["signatures_updated"]:
            parts.append(f"{self.stats['signatures_updated']} signature(s) updated")
        if self.stats["functions_converted"]:
            parts.append(
                f"{self.stats['functions_converted']} function call(s) converted"
            )
        if self.stats["constants_replaced"]:
            parts.append(f"{self.stats['constants_replaced']} constant(s) replaced")
        if self.stats["variables_renamed"]:
            parts.append(f"{self.stats['variables_renamed']} variable(s) renamed")
        if self.stats["defensive_checks_added"]:
            parts.append(
                f"{self.stats['defensive_checks_added']} defensive check(s) added"
            )
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")

        return ", ".join(parts) if parts else "No changes"
