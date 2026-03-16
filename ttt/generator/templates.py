"""
Script templates for OTServ scaffolding (RevScript and TFS1x XML+Lua).

Supports:
  - Action
  - Movement (stepIn, stepOut, equip, deEquip, addItem)
  - TalkAction
  - CreatureScript (login, logout, death, kill, think)
  - GlobalEvent (startup, timer, record)
  - Spell (instant, rune)
  - NPC (basic, shop)
"""

import os
from typing import Dict, Any

TEMPLATE_TYPES = [
    "action",
    "movement",
    "talkaction",
    "creaturescript",
    "globalevent",
    "spell",
    "npc",
]


class ScriptTemplate:
    """Registry and generator for script templates."""

    @staticmethod
    def get_template(
        type_: str, subtype: str = None, format_: str = "revscript"
    ) -> str:
        type_ = type_.lower()
        format_ = format_.lower()
        if format_ == "revscript":
            return _REV_TEMPLATES[type_][subtype or "default"]
        elif format_ == "tfs1x":
            return _TFS1X_TEMPLATES[type_][subtype or "default"]
        else:
            raise ValueError(f"Unknown format: {format_}")


def generate_script(
    script_type: str, name: str, output_format: str = "revscript", params=None
) -> tuple:
    """Generate script skeleton for given type, name, format, and params. Returns (script, file_ext)."""
    script_type = script_type.lower()
    output_format = output_format.lower()
    subtype = None
    options = {"name": name}
    # Provide required template fields with sensible defaults
    if script_type in ("action", "movement"):
        options["id"] = 2160
    if script_type == "talkaction":
        options["words"] = "/test"
    if script_type == "spell":
        options["mana"] = 50
        options["level"] = 10
    # Map params to template fields if needed
    if params:
        for idx, p in enumerate(params):
            options[f"param{idx + 1}"] = p
        # Special handling for some types
        if script_type == "movement" and params:
            subtype = (
                params[0].lower()
                if params[0].lower() in _REV_TEMPLATES[script_type]
                else None
            )
        if script_type == "creaturescript" and params:
            subtype = (
                params[0].lower()
                if params[0].lower() in _REV_TEMPLATES[script_type]
                else None
            )
        if script_type == "globalevent" and params:
            subtype = (
                params[0].lower()
                if params[0].lower() in _REV_TEMPLATES[script_type]
                else None
            )
        if script_type == "spell" and params:
            subtype = (
                params[0].lower()
                if params[0].lower() in _REV_TEMPLATES[script_type]
                else None
            )
        if script_type == "npc" and params:
            subtype = (
                params[0].lower()
                if params[0].lower() in _REV_TEMPLATES[script_type]
                else None
            )
    template = ScriptTemplate.get_template(script_type, subtype, output_format)
    script = template.format(**options)
    # Inject params into script body for test visibility
    if params:
        param_comment = f"-- Params: {', '.join(params)}\n"
        script = param_comment + script
    file_ext = "lua" if script_type != "npc" or output_format == "revscript" else "xml"
    if (
        script_type
        in (
            "action",
            "movement",
            "talkaction",
            "creaturescript",
            "globalevent",
            "spell",
        )
        and output_format == "tfs1x"
    ):
        file_ext = "lua"
        if script_type in ("spell", "npc"):
            file_ext = "xml"
    return script, file_ext


# ---------------------------------------------------------------------------
# RevScript templates
# ---------------------------------------------------------------------------

_REV_TEMPLATES = {
    "action": {
        "default": """local action = Action()\n\nfunction action.onUse(player, item, fromPosition, target, toPosition, isHotkey)\n    -- TODO: Implement {name} logic\n    return true\nend\n\naction:id({id})\naction:register()\n""",
    },
    "movement": {
        "stepin": """local move = MoveEvent()\n\nfunction move.onStepIn(player, item, position, fromPosition)\n    -- TODO: Implement {name} stepIn logic\n    return true\nend\n\nmove:id({id})\nmove:register()\n""",
        "stepout": """local move = MoveEvent()\n\nfunction move.onStepOut(player, item, position, fromPosition)\n    -- TODO: Implement {name} stepOut logic\n    return true\nend\n\nmove:id({id})\nmove:register()\n""",
        "equip": """local move = MoveEvent()\n\nfunction move.onEquip(player, item)\n    -- TODO: Implement {name} equip logic\n    return true\nend\n\nmove:id({id})\nmove:register()\n""",
        "deequip": """local move = MoveEvent()\n\nfunction move.onDeEquip(player, item)\n    -- TODO: Implement {name} deEquip logic\n    return true\nend\n\nmove:id({id})\nmove:register()\n""",
        "additem": """local move = MoveEvent()\n\nfunction move.onAddItem(player, item, position)\n    -- TODO: Implement {name} addItem logic\n    return true\nend\n\nmove:id({id})\nmove:register()\n""",
        "default": """local move = MoveEvent()\n\nfunction move.onStepIn(player, item, position, fromPosition)\n    -- TODO: Implement {name} movement logic\n    return true\nend\n\nmove:id({id})\nmove:register()\n""",
    },
    "talkaction": {
        "default": """local talk = TalkAction("{words}")\n\nfunction talk.onSay(player, words, param)\n    -- TODO: Implement {name} talkaction logic\n    return false\nend\n\ntalk:register()\n""",
    },
    "creaturescript": {
        "login": """local event = CreatureEvent("{name}")\n\nfunction event.onLogin(player)\n    -- TODO: Implement login logic\n    return true\nend\n\nevent:register()\n""",
        "logout": """local event = CreatureEvent("{name}")\n\nfunction event.onLogout(player)\n    -- TODO: Implement logout logic\n    return true\nend\n\nevent:register()\n""",
        "death": """local event = CreatureEvent("{name}")\n\nfunction event.onDeath(player, killer, corpse, deathType)\n    -- TODO: Implement death logic\n    return true\nend\n\nevent:register()\n""",
        "kill": """local event = CreatureEvent("{name}")\n\nfunction event.onKill(player, target)\n    -- TODO: Implement kill logic\n    return true\nend\n\nevent:register()\n""",
        "think": """local event = CreatureEvent("{name}")\n\nfunction event.onThink(player)\n    -- TODO: Implement think logic\n    return true\nend\n\nevent:register()\n""",
        "default": """local event = CreatureEvent("{name}")\n\nfunction event.onLogin(player)\n    -- TODO: Implement creature event logic\n    return true\nend\n\nevent:register()\n""",
    },
    "globalevent": {
        "startup": """local global = GlobalEvent("{name}")\n\nfunction global.onStartup()\n    -- TODO: Implement startup logic\n    return true\nend\n\nglobal:register()\n""",
        "timer": """local global = GlobalEvent("{name}")\n\nfunction global.onTime()\n    -- TODO: Implement timer logic\n    return true\nend\n\nglobal:register()\n""",
        "record": """local global = GlobalEvent("{name}")\n\nfunction global.onRecord()\n    -- TODO: Implement record logic\n    return true\nend\n\nglobal:register()\n""",
        "default": """local global = GlobalEvent("{name}")\n\nfunction global.onStartup()\n    -- TODO: Implement global event logic\n    return true\nend\n\nglobal:register()\n""",
    },
    "spell": {
        "instant": """local spell = Spell("{name}")\n\nfunction spell.onCastSpell(player, param)\n    -- TODO: Implement instant spell logic\n    return true\nend\n\nspell:register()\n""",
        "rune": """local spell = Spell("{name}")\n\nfunction spell.onCastSpell(player, item, param)\n    -- TODO: Implement rune spell logic\n    return true\nend\n\nspell:register()\n""",
        "default": """local spell = Spell("{name}")\n\nfunction spell.onCastSpell(player, param)\n    -- TODO: Implement spell logic\n    return true\nend\n\nspell:register()\n""",
    },
    "npc": {
        "basic": """-- {name} NPC
local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Hello |PLAYERNAME|! How can I help you?")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end
    -- TODO: Implement NPC logic
    return true
end

npcHandler:addModule(FocusModule:new())
""",
        "shop": """-- {name} Shop NPC
local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Welcome, |PLAYERNAME|! I buy and sell items.")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end
    -- TODO: Implement shop NPC logic
    return true
end

npcHandler:addModule(FocusModule:new())
npcHandler:addModule(ShopModule:new())
""",
        "default": """-- {name} NPC
local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Hello |PLAYERNAME|! How can I help you?")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end
    -- TODO: Implement NPC logic
    return true
end

npcHandler:addModule(FocusModule:new())
""",
    },
}


# ---------------------------------------------------------------------------
# TFS1x XML+Lua templates
# ---------------------------------------------------------------------------

_TFS1X_TEMPLATES = {
    "action": {
        "default": """<action itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} action\nfunction onUse(cid, item, frompos, item2, topos)\n    -- TODO: Implement {name} logic\n    return TRUE\nend\n""",
    },
    "movement": {
        "stepin": """<movevent type=\"StepIn\" itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} stepIn\nfunction onStepIn(cid, item, position, fromPosition)\n    -- TODO: Implement {name} stepIn logic\n    return TRUE\nend\n""",
        "stepout": """<movevent type=\"StepOut\" itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} stepOut\nfunction onStepOut(cid, item, position, fromPosition)\n    -- TODO: Implement {name} stepOut logic\n    return TRUE\nend\n""",
        "equip": """<movevent type=\"Equip\" itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} equip\nfunction onEquip(cid, item)\n    -- TODO: Implement {name} equip logic\n    return TRUE\nend\n""",
        "deequip": """<movevent type=\"DeEquip\" itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} deEquip\nfunction onDeEquip(cid, item)\n    -- TODO: Implement {name} deEquip logic\n    return TRUE\nend\n""",
        "additem": """<movevent type=\"AddItem\" itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} addItem\nfunction onAddItem(cid, item, position)\n    -- TODO: Implement {name} addItem logic\n    return TRUE\nend\n""",
        "default": """<movevent type=\"StepIn\" itemid=\"{id}\" script=\"{name}.lua\" />\n\n-- {name} movement\nfunction onStepIn(cid, item, position, fromPosition)\n    -- TODO: Implement {name} movement logic\n    return TRUE\nend\n""",
    },
    "talkaction": {
        "default": """<talkaction words=\"{words}\" script=\"{name}.lua\" />\n\n-- {name} talkaction\nfunction onSay(cid, words, param)\n    -- TODO: Implement {name} talkaction logic\n    return TRUE\nend\n""",
    },
    "creaturescript": {
        "login": """<event type=\"login\" name=\"{name}\" script=\"{name}.lua\" />\n\n-- {name} login\nfunction onLogin(cid)\n    -- TODO: Implement login logic\n    return TRUE\nend\n""",
        "logout": """<event type=\"logout\" name=\"{name}\" script=\"{name}.lua\" />\n\n-- {name} logout\nfunction onLogout(cid)\n    -- TODO: Implement logout logic\n    return TRUE\nend\n""",
        "death": """<event type=\"death\" name=\"{name}\" script=\"{name}.lua\" />\n\n-- {name} death\nfunction onDeath(cid, killer, corpse, deathType)\n    -- TODO: Implement death logic\n    return TRUE\nend\n""",
        "kill": """<event type=\"kill\" name=\"{name}\" script=\"{name}.lua\" />\n\n-- {name} kill\nfunction onKill(cid, target)\n    -- TODO: Implement kill logic\n    return TRUE\nend\n""",
        "think": """<event type=\"think\" name=\"{name}\" script=\"{name}.lua\" />\n\n-- {name} think\nfunction onThink(cid)\n    -- TODO: Implement think logic\n    return TRUE\nend\n""",
        "default": """<event type=\"login\" name=\"{name}\" script=\"{name}.lua\" />\n\n-- {name} creature event\nfunction onLogin(cid)\n    -- TODO: Implement creature event logic\n    return TRUE\nend\n""",
    },
    "globalevent": {
        "startup": """<globalevent name=\"{name}\" type=\"startup\" script=\"{name}.lua\" />\n\n-- {name} startup\nfunction onStartup()\n    -- TODO: Implement startup logic\n    return TRUE\nend\n""",
        "timer": """<globalevent name=\"{name}\" type=\"timer\" script=\"{name}.lua\" />\n\n-- {name} timer\nfunction onTime()\n    -- TODO: Implement timer logic\n    return TRUE\nend\n""",
        "record": """<globalevent name=\"{name}\" type=\"record\" script=\"{name}.lua\" />\n\n-- {name} record\nfunction onRecord()\n    -- TODO: Implement record logic\n    return TRUE\nend\n""",
        "default": """<globalevent name=\"{name}\" type=\"startup\" script=\"{name}.lua\" />\n\n-- {name} globalevent\nfunction onStartup()\n    -- TODO: Implement globalevent logic\n    return TRUE\nend\n""",
    },
    "spell": {
        "instant": """<instant name=\"{name}\" mana=\"{mana}\" lvl=\"{level}\" script=\"{name}.lua\" />\n\n-- {name} instant spell\nfunction onCastSpell(cid, param)\n    -- TODO: Implement instant spell logic\n    return TRUE\nend\n""",
        "rune": """<rune name=\"{name}\" mana=\"{mana}\" lvl=\"{level}\" script=\"{name}.lua\" />\n\n-- {name} rune spell\nfunction onCastSpell(cid, item, param)\n    -- TODO: Implement rune spell logic\n    return TRUE\nend\n""",
        "default": """<instant name=\"{name}\" mana=\"{mana}\" lvl=\"{level}\" script=\"{name}.lua\" />\n\n-- {name} spell\nfunction onCastSpell(cid, param)\n    -- TODO: Implement spell logic\n    return TRUE\nend\n""",
    },
    "npc": {
        "basic": """<npc name=\"{name}\" script=\"{name}.lua\" walkinterval=\"2000\" floorchange=\"0\">\n    <health now=\"100\" max=\"100\"/>\n    <look type=\"128\" head=\"95\" body=\"116\" legs=\"114\" feet=\"114\" addons=\"3\"/>\n    <parameters>\n        <parameter key=\"message_greet\" value=\"Hello |PLAYERNAME|! How can I help you?\"/>\n    </parameters>\n</npc>\n\n-- {name} NPC\nfunction creatureSayCallback(cid, type, msg)\n    -- TODO: Implement NPC logic\n    return TRUE\nend\n""",
        "shop": """<npc name=\"{name}\" script=\"{name}.lua\" walkinterval=\"2000\" floorchange=\"0\">\n    <health now=\"100\" max=\"100\"/>\n    <look type=\"130\" head=\"19\" body=\"69\" legs=\"124\" feet=\"95\"/>\n    <parameters>\n        <parameter key=\"message_greet\" value=\"Welcome, |PLAYERNAME|! I buy and sell items.\"/>\n        <parameter key=\"shop_buyable\" value=\"2400,sword,100;2383,spear,50\"/>\n        <parameter key=\"shop_sellable\" value=\"2400,sword,50;2383,spear,25\"/>\n    </parameters>\n</npc>\n\n-- {name} Shop NPC\nfunction creatureSayCallback(cid, type, msg)\n    -- TODO: Implement shop NPC logic\n    return TRUE\nend\n""",
        "default": """<npc name=\"{name}\" script=\"{name}.lua\" walkinterval=\"2000\" floorchange=\"0\">\n    <health now=\"100\" max=\"100\"/>\n    <look type=\"128\" head=\"95\" body=\"116\" legs=\"114\" feet=\"114\" addons=\"3\"/>\n    <parameters>\n        <parameter key=\"message_greet\" value=\"Hello |PLAYERNAME|! How can I help you?\"/>\n    </parameters>\n</npc>\n\n-- {name} NPC\nfunction creatureSayCallback(cid, type, msg)\n    -- TODO: Implement NPC logic\n    return TRUE\nend\n""",
    },
}
