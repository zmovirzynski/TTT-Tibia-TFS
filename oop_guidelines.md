# OOP Refactoring Guidelines for LLM Assistants

Generated: 2026-03-15  
Files analyzed: 17  
Files with issues: 11  
Total issues: 60

---

## engine.py  (640 lines)

### Issues Found

**1. Method too long: `__init__` (lines 63–113, 51 lines)**
- Description: `__init__` spans 51 lines (63–113), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `run` (lines 139–221, 83 lines)**
- Description: `run` spans 83 lines (139–221), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**3. Method too long: `_convert_xml_to_revscript` (lines 276–352, 77 lines)**
- Description: `_convert_xml_to_revscript` spans 77 lines (276–352), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**4. Method too long: `_convert_lua_files` (lines 389–515, 127 lines)**
- Description: `_convert_lua_files` spans 127 lines (389–515), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**5. Too many parameters: `__init__` (lines 63–113, 51 lines)**
- Description: `__init__` has 7 parameters (source_version, target_version, input_dir, output_dir, verbose, dry_run, html_diff), exceeding the limit of 5.
- Guideline for LLM: Introduce a parameter object (dataclass or namedtuple) to group related parameters. Consider whether some parameters indicate a missing abstraction or that the method is doing too much.

**6. Dict-as-object pattern: `_convert_xml_to_revscript` (lines 276–352, 77 lines)**
- Description: `_convert_xml_to_revscript` accesses 3 distinct string keys ('errors', 'revscripts_generated', 'xml_files_processed'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**7. Dict-as-object pattern: `_convert_npc_scripts` (lines 354–387, 34 lines)**
- Description: `_convert_npc_scripts` accesses 4 distinct string keys ('errors', 'npcs_converted', 'revscripts_generated', 'scripts_transformed'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**8. Dict-as-object pattern: `_convert_lua_files` (lines 389–515, 127 lines)**
- Description: `_convert_lua_files` accesses 4 distinct string keys ('defensive_checks_added', 'errors', 'lua_files_processed', 'total_functions_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**9. Dict-as-object pattern: `_print_summary` (lines 549–585, 37 lines)**
- Description: `_print_summary` accesses 7 distinct string keys ('defensive_checks_added', 'errors', 'lua_files_processed', 'revscripts_generated', 'time_elapsed', 'total_functions_converted'…), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

### Suggested LLM prompt

> Refactor `engine.py` following these guidelines: address `__init__`, `run`, `_convert_xml_to_revscript`, `_convert_lua_files`, `__init__` and 4 more. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## report.py  (414 lines)

### Issues Found

**1. Method too long: `_build_report` (lines 189–315, 127 lines)**
- Description: `_build_report` spans 127 lines (189–315), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `generate_dry_run` (lines 317–414, 98 lines)**
- Description: `generate_dry_run` spans 98 lines (317–414), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

### Suggested LLM prompt

> Refactor `report.py` following these guidelines: address `_build_report`, `generate_dry_run`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## scanner.py  (287 lines)

### Issues Found

**1. Method too long: `scan_directory` (lines 101–153, 53 lines)**
- Description: `scan_directory` spans 53 lines (101–153), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Too many parameters: `_detect_component` (lines 156–205, 50 lines)**
- Description: `_detect_component` has 7 parameters (result, root_dir, component_name, xml_names, script_subdirs, xml_attr, dir_attr), exceeding the limit of 5.
- Guideline for LLM: Introduce a parameter object (dataclass or namedtuple) to group related parameters. Consider whether some parameters indicate a missing abstraction or that the method is doing too much.

**3. Standalone function outside class: `scan_directory` (lines 101–153, 53 lines)**
- Description: `scan_directory` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**4. Standalone function outside class: `_detect_component` (lines 156–205, 50 lines)**
- Description: `_detect_component` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**5. Standalone function outside class: `_detect_npc_component` (lines 208–237, 30 lines)**
- Description: `_detect_npc_component` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**6. Standalone function outside class: `_detect_version` (lines 240–287, 48 lines)**
- Description: `_detect_version` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

### Suggested LLM prompt

> Refactor `scanner.py` following these guidelines: address `scan_directory`, `_detect_component`, `scan_directory`, `_detect_component`, `_detect_npc_component` and 1 more. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## diff_html.py  (826 lines)

### Issues Found

**1. Method too long: `_build_html` (lines 109–188, 80 lines)**
- Description: `_build_html` spans 80 lines (109–188), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Dict-as-object pattern: `_render_diff_table` (lines 190–221, 32 lines)**
- Description: `_render_diff_table` accesses 5 distinct string keys ('left_line', 'left_num', 'right_line', 'right_num', 'status'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**3. Standalone function outside class: `_esc` (lines 247–248, 2 lines)**
- Description: `_esc` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**4. Standalone function outside class: `_tokenize` (lines 251–253, 3 lines)**
- Description: `_tokenize` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

### Suggested LLM prompt

> Refactor `diff_html.py` following these guidelines: address `_build_html`, `_render_diff_table`, `_esc`, `_tokenize`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## main.py  (346 lines)

### Issues Found

**1. Method too long: `interactive_mode` (lines 57–247, 191 lines)**
- Description: `interactive_mode` spans 191 lines (57–247), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `cli_mode` (lines 250–335, 86 lines)**
- Description: `cli_mode` spans 86 lines (250–335), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

### Suggested LLM prompt

> Refactor `main.py` following these guidelines: address `interactive_mode`, `cli_mode`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## converters/lua_transformer.py  (567 lines)

### Issues Found

**1. Method too long: `_transform_signatures` (lines 49–107, 59 lines)**
- Description: `_transform_signatures` spans 59 lines (49–107), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `_replace_function` (lines 215–280, 66 lines)**
- Description: `_replace_function` spans 66 lines (215–280), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**3. Method too long: `_handle_custom` (lines 374–436, 63 lines)**
- Description: `_handle_custom` spans 63 lines (374–436), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**4. Dict-as-object pattern: `get_summary` (lines 555–567, 13 lines)**
- Description: `get_summary` accesses 4 distinct string keys ('constants_replaced', 'functions_converted', 'signatures_updated', 'variables_renamed'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

### Suggested LLM prompt

> Refactor `converters/lua_transformer.py` following these guidelines: address `_transform_signatures`, `_replace_function`, `_handle_custom`, `get_summary`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## converters/xml_to_revscript.py  (885 lines)

### Issues Found

**1. Method too long: `_convert_actions` (lines 80–143, 64 lines)**
- Description: `_convert_actions` spans 64 lines (80–143), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `_convert_movements` (lines 169–240, 72 lines)**
- Description: `_convert_movements` spans 72 lines (169–240), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**3. Method too long: `_convert_talkactions` (lines 279–342, 64 lines)**
- Description: `_convert_talkactions` spans 64 lines (279–342), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**4. Method too long: `_convert_creaturescripts` (lines 377–443, 67 lines)**
- Description: `_convert_creaturescripts` spans 67 lines (377–443), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**5. Method too long: `_convert_globalevents` (lines 486–570, 85 lines)**
- Description: `_convert_globalevents` spans 85 lines (486–570), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**6. Method too long: `_extract_function_body` (lines 641–728, 88 lines)**
- Description: `_extract_function_body` spans 88 lines (641–728), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**7. Method too long: `_generate_registration_lines` (lines 761–814, 54 lines)**
- Description: `_generate_registration_lines` spans 54 lines (761–814), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**8. Too many parameters: `_generate_creaturescript_revscript` (lines 445–467, 23 lines)**
- Description: `_generate_creaturescript_revscript` has 7 parameters (var_name, entry, func_body, full_code, event_name, event_type, event_method), exceeding the limit of 5.
- Guideline for LLM: Introduce a parameter object (dataclass or namedtuple) to group related parameters. Consider whether some parameters indicate a missing abstraction or that the method is doing too much.

**9. Too many parameters: `_generate_globalevent_revscript` (lines 571–607, 37 lines)**
- Description: `_generate_globalevent_revscript` has 8 parameters (var_name, entry, func_body, full_code, event_name, event_method, interval, time_val), exceeding the limit of 5.
- Guideline for LLM: Introduce a parameter object (dataclass or namedtuple) to group related parameters. Consider whether some parameters indicate a missing abstraction or that the method is doing too much.

**10. Dict-as-object pattern: `_convert_actions` (lines 80–143, 64 lines)**
- Description: `_convert_actions` accesses 3 distinct string keys ('entries_processed', 'errors', 'files_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**11. Dict-as-object pattern: `_convert_movements` (lines 169–240, 72 lines)**
- Description: `_convert_movements` accesses 3 distinct string keys ('entries_processed', 'errors', 'files_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**12. Dict-as-object pattern: `_convert_talkactions` (lines 279–342, 64 lines)**
- Description: `_convert_talkactions` accesses 3 distinct string keys ('entries_processed', 'errors', 'files_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**13. Dict-as-object pattern: `_convert_creaturescripts` (lines 377–443, 67 lines)**
- Description: `_convert_creaturescripts` accesses 3 distinct string keys ('entries_processed', 'errors', 'files_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**14. Dict-as-object pattern: `_convert_globalevents` (lines 486–570, 85 lines)**
- Description: `_convert_globalevents` accesses 3 distinct string keys ('entries_processed', 'errors', 'files_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**15. Dict-as-object pattern: `get_summary` (lines 877–885, 9 lines)**
- Description: `get_summary` accesses 3 distinct string keys ('entries_processed', 'errors', 'files_converted'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

### Suggested LLM prompt

> Refactor `converters/xml_to_revscript.py` following these guidelines: address `_convert_actions`, `_convert_movements`, `_convert_talkactions`, `_convert_creaturescripts`, `_convert_globalevents` and 10 more. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## converters/npc_converter.py  (282 lines)

### Issues Found

**1. Method too long: `_parse_npc_xml` (lines 170–222, 53 lines)**
- Description: `_parse_npc_xml` spans 53 lines (170–222), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Dict-as-object pattern: `get_summary` (lines 49–57, 9 lines)**
- Description: `get_summary` accesses 3 distinct string keys ('errors', 'npcs_converted', 'scripts_transformed'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**3. Dict-as-object pattern: `_convert_single_npc` (lines 82–127, 46 lines)**
- Description: `_convert_single_npc` accesses 3 distinct string keys ('errors', 'npcs_converted', 'xml_copied'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**4. Dict-as-object pattern: `_parse_npc_xml` (lines 170–222, 53 lines)**
- Description: `_parse_npc_xml` accesses 3 distinct string keys ('health', 'look', 'parameters'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

**5. Dict-as-object pattern: `_generate_npc_header` (lines 224–254, 31 lines)**
- Description: `_generate_npc_header` accesses 5 distinct string keys ('body', 'feet', 'head', 'legs', 'type'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

### Suggested LLM prompt

> Refactor `converters/npc_converter.py` following these guidelines: address `_parse_npc_xml`, `get_summary`, `_convert_single_npc`, `_parse_npc_xml`, `_generate_npc_header`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## converters/ast_lua_transformer.py  (319 lines)

### Issues Found

**1. Method too long: `transform` (lines 94–149, 56 lines)**
- Description: `transform` spans 56 lines (94–149), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `_transform_with_ast` (lines 151–213, 63 lines)**
- Description: `_transform_with_ast` spans 63 lines (151–213), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**3. Dict-as-object pattern: `get_summary` (lines 284–319, 36 lines)**
- Description: `get_summary` accesses 5 distinct string keys ('constants_replaced', 'defensive_checks_added', 'functions_converted', 'signatures_updated', 'variables_renamed'), suggesting dict-as-object usage.
- Guideline for LLM: Replace the dict with a dataclass or class that encodes the structure explicitly. This makes fields discoverable, type-checkable, and gives you a natural place for validation and methods.

### Suggested LLM prompt

> Refactor `converters/ast_lua_transformer.py` following these guidelines: address `transform`, `_transform_with_ast`, `get_summary`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## converters/scope_analyzer.py  (871 lines)

### Issues Found

**1. Method too long: `_infer_param_type` (lines 322–384, 63 lines)**
- Description: `_infer_param_type` spans 63 lines (322–384), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `_analyze_value_type` (lines 423–480, 58 lines)**
- Description: `_analyze_value_type` spans 58 lines (423–480), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**3. Method too long: `visit` (lines 741–809, 69 lines)**
- Description: `visit` spans 69 lines (741–809), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**4. Standalone function outside class: `analyze_scope` (lines 812–823, 12 lines)**
- Description: `analyze_scope` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**5. Standalone function outside class: `is_creature_variable` (lines 827–838, 12 lines)**
- Description: `is_creature_variable` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**6. Standalone function outside class: `is_player_variable` (lines 841–852, 12 lines)**
- Description: `is_player_variable` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

**7. Standalone function outside class: `needs_wrapper` (lines 855–871, 17 lines)**
- Description: `needs_wrapper` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

### Suggested LLM prompt

> Refactor `converters/scope_analyzer.py` following these guidelines: address `_infer_param_type`, `_analyze_value_type`, `visit`, `analyze_scope`, `is_creature_variable` and 2 more. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## converters/ast_transform_visitor.py  (824 lines)

### Issues Found

**1. Method too long: `_transform_function_call` (lines 204–325, 122 lines)**
- Description: `_transform_function_call` spans 122 lines (204–325), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**2. Method too long: `visit_Call` (lines 471–529, 59 lines)**
- Description: `visit_Call` spans 59 lines (471–529), exceeding the 50-line limit.
- Guideline for LLM: Break this method into smaller private helper methods, each with a single responsibility. Aim for methods under 20 lines. Use descriptive names that reveal intent without requiring comments.

**3. Standalone function outside class: `transform_ast` (lines 792–824, 33 lines)**
- Description: `transform_ast` is a module-level function in a file that also defines classes.
- Guideline for LLM: Move this function inside the relevant class as a static method, class method, or instance method. If it belongs to none, consider creating a dedicated helper class or moving it to a utils module.

### Suggested LLM prompt

> Refactor `converters/ast_transform_visitor.py` following these guidelines: address `_transform_function_call`, `visit_Call`, `transform_ast`. Apply OOP principles — extract helper methods, introduce dataclasses, reduce parameter lists, and move standalone functions into classes.

---

## Clean files

No OOP issues detected in:

- `converters/ast_utils.py` (67 lines)
- `mappings/tfs03_functions.py` (1320 lines)
- `mappings/tfs04_functions.py` (194 lines)
- `mappings/signatures.py` (283 lines)
- `mappings/constants.py` (302 lines)
- `mappings/xml_events.py` (99 lines)
