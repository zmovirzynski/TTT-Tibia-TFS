"""Assinaturas de callback TFS 0.3/0.4 → 1.x."""

# onUse (Actions)

ONUSE_OLD = {
    "params": ["cid", "item", "frompos", "item2", "topos"],
    "alt_params": [
        ["cid", "item", "fromPosition", "itemEx", "toPosition"],
        ["cid", "item", "frompos", "itemEx", "topos"],
        ["player", "item", "frompos", "item2", "topos"],
    ],
}

ONUSE_NEW = {
    "params": ["player", "item", "fromPosition", "target", "toPosition", "isHotkey"],
}

# onStepIn / onStepOut (Movements)

ONSTEPIN_OLD = {
    "params": ["cid", "item", "position", "fromPosition"],
    "alt_params": [
        ["cid", "item", "pos", "fromPos"],
        ["cid", "item", "position", "lastPosition"],
        ["cid", "item", "pos", "lastPos"],
    ],
}

ONSTEPIN_NEW = {
    "params": ["creature", "item", "position", "fromPosition"],
}

ONSTEPOUT_OLD = {
    "params": ["cid", "item", "position", "toPosition"],
    "alt_params": [
        ["cid", "item", "pos", "toPos"],
    ],
}

ONSTEPOUT_NEW = {
    "params": ["creature", "item", "position", "toPosition"],
}

# onEquip / onDeEquip (Movements)

ONEQUIP_OLD = {
    "params": ["cid", "item", "slot"],
    "alt_params": [
        ["cid", "item", "slot", "isCheck"],
    ],
}

ONEQUIP_NEW = {
    "params": ["player", "item", "slot", "isCheck"],
}

ONDEEQUIP_OLD = {
    "params": ["cid", "item", "slot"],
    "alt_params": [
        ["cid", "item", "slot", "isCheck"],
    ],
}

ONDEEQUIP_NEW = {
    "params": ["player", "item", "slot", "isCheck"],
}

# onAddItem / onRemoveItem (Movements)

ONADDITEM_OLD = {
    "params": ["moveitem", "tileitem", "position"],
    "alt_params": [],
}

ONADDITEM_NEW = {
    "params": ["moveitem", "tileitem", "position"],
}

# onSay (TalkActions)

ONSAY_OLD = {
    "params": ["cid", "words", "param"],
    "alt_params": [
        ["cid", "words", "param", "channel"],
    ],
}

ONSAY_NEW = {
    "params": ["player", "words", "param"],
}

# CreatureScripts

ONLOGIN_OLD = {
    "params": ["cid"],
    "alt_params": [],
}

ONLOGIN_NEW = {
    "params": ["player"],
}

ONLOGOUT_OLD = {
    "params": ["cid"],
    "alt_params": [],
}

ONLOGOUT_NEW = {
    "params": ["player"],
}

ONDEATH_OLD = {
    "params": [
        "cid",
        "corpse",
        "killer",
        "mostDamage",
        "unjustified",
        "mostDamage_unjustified",
    ],
    "alt_params": [
        ["cid", "corpse", "killer", "mostDamage"],
        ["cid", "corpse", "lastHitKiller", "mostDamageKiller"],
    ],
}

ONDEATH_NEW = {
    "params": [
        "creature",
        "corpse",
        "killer",
        "mostDamageKiller",
        "lastHitUnjustified",
        "mostDamageUnjustified",
    ],
}

ONKILL_OLD = {
    "params": ["cid", "target"],
    "alt_params": [
        ["cid", "target", "lastHit"],
    ],
}

ONKILL_NEW = {
    "params": ["creature", "target"],
}

ONPREPAREDDEATH_OLD = {
    "params": ["cid", "killer"],
    "alt_params": [],
}

ONPREPAREDDEATH_NEW = {
    "params": ["creature", "killer"],
}

ONHEALTHCHANGE_OLD = {
    "params": [
        "creature",
        "attacker",
        "primaryDamage",
        "primaryType",
        "secondaryDamage",
        "secondaryType",
        "origin",
    ],
    "alt_params": [],
}

ONHEALTHCHANGE_NEW = {
    "params": [
        "creature",
        "attacker",
        "primaryDamage",
        "primaryType",
        "secondaryDamage",
        "secondaryType",
        "origin",
    ],
}

ONMANACHANGE_OLD = {
    "params": [
        "creature",
        "attacker",
        "primaryDamage",
        "primaryType",
        "secondaryDamage",
        "secondaryType",
        "origin",
    ],
    "alt_params": [],
}

ONMANACHANGE_NEW = {
    "params": [
        "creature",
        "attacker",
        "primaryDamage",
        "primaryType",
        "secondaryDamage",
        "secondaryType",
        "origin",
    ],
}

ONTEXTEDIT_OLD = {
    "params": ["cid", "item", "newText"],
    "alt_params": [],
}

ONTEXTEDIT_NEW = {
    "params": ["player", "item", "text"],
}

ONTHINK_OLD = {
    "params": ["cid", "interval"],
    "alt_params": [],
}

ONTHINK_NEW = {
    "params": ["creature", "interval"],
}

ONMODALWINDOW_OLD = {
    "params": ["cid", "modalWindowId", "buttonId", "choiceId"],
    "alt_params": [],
}

ONMODALWINDOW_NEW = {
    "params": ["player", "modalWindowId", "buttonId", "choiceId"],
}

# GlobalEvents

ONSTARTUP_OLD = {
    "params": [],
    "alt_params": [],
}

ONSTARTUP_NEW = {
    "params": [],
}

ONSHUTDOWN_OLD = {
    "params": [],
    "alt_params": [],
}

ONSHUTDOWN_NEW = {
    "params": [],
}

ONRECORD_OLD = {
    "params": ["current", "old", "cid"],
    "alt_params": [
        ["current", "old"],
    ],
}

ONRECORD_NEW = {
    "params": ["current", "old"],
}

ONTIMER_OLD = {
    "params": ["interval"],
    "alt_params": [
        [],
    ],
}

ONTIMER_NEW = {
    "params": ["interval"],
}

ONGLOBALEVENT_OLD = {
    "params": ["interval"],
    "alt_params": [
        [],
    ],
}

ONGLOBALEVENT_NEW = {
    "params": ["interval"],
}

# Master mapping: event_name → (old_signature, new_signature)

SIGNATURE_MAP = {
    "onUse": (ONUSE_OLD, ONUSE_NEW),
    "onStepIn": (ONSTEPIN_OLD, ONSTEPIN_NEW),
    "onStepOut": (ONSTEPOUT_OLD, ONSTEPOUT_NEW),
    "onEquip": (ONEQUIP_OLD, ONEQUIP_NEW),
    "onDeEquip": (ONDEEQUIP_OLD, ONDEEQUIP_NEW),
    "onAddItem": (ONADDITEM_OLD, ONADDITEM_NEW),
    "onSay": (ONSAY_OLD, ONSAY_NEW),
    "onLogin": (ONLOGIN_OLD, ONLOGIN_NEW),
    "onLogout": (ONLOGOUT_OLD, ONLOGOUT_NEW),
    "onDeath": (ONDEATH_OLD, ONDEATH_NEW),
    "onKill": (ONKILL_OLD, ONKILL_NEW),
    "onPrepareDeath": (ONPREPAREDDEATH_OLD, ONPREPAREDDEATH_NEW),
    "onHealthChange": (ONHEALTHCHANGE_OLD, ONHEALTHCHANGE_NEW),
    "onManaChange": (ONMANACHANGE_OLD, ONMANACHANGE_NEW),
    "onTextEdit": (ONTEXTEDIT_OLD, ONTEXTEDIT_NEW),
    "onThink": (ONTHINK_OLD, ONTHINK_NEW),
    "onModalWindow": (ONMODALWINDOW_OLD, ONMODALWINDOW_NEW),
    "onStartup": (ONSTARTUP_OLD, ONSTARTUP_NEW),
    "onShutdown": (ONSHUTDOWN_OLD, ONSHUTDOWN_NEW),
    "onRecord": (ONRECORD_OLD, ONRECORD_NEW),
    "onTime": (ONTIMER_OLD, ONTIMER_NEW),
    "onTimer": (ONTIMER_OLD, ONTIMER_NEW),
    "onGlobalEvent": (ONGLOBALEVENT_OLD, ONGLOBALEVENT_NEW),
}

# Variable rename map: old param name → new param name
# Used to rename variables throughout the function body

PARAM_RENAME_MAP = {
    "cid": "player",  # Most common: creature ID → Player object
    "frompos": "fromPosition",
    "topos": "toPosition",
    "fromPos": "fromPosition",
    "toPos": "toPosition",
    "item2": "target",
    "itemEx": "target",
    "lastPos": "fromPosition",
    "lastPosition": "fromPosition",
}
