"""Mapeamentos XML → RevScript."""

# Actions → Action()

ACTION_REGISTRATION = {
    "class": "Action",
    "event_method": "onUse",
    "id_methods": {
        "itemid": "id",         # action:id(1234)
        "fromid": "id",         # action:id(1234, 5678)  (range)
        "actionid": "aid",      # action:aid(1234)
        "uniqueid": "uid",      # action:uid(1234)
    },
    "extra_attrs": {
        "allowfaruse": "allowFarUse",
        "blockwalls": "blockWalls",
    },
}

# Movements → MoveEvent()

MOVEMENT_TYPES = {
    "StepIn":    "onStepIn",
    "StepOut":   "onStepOut",
    "Equip":     "onEquip",
    "DeEquip":   "onDeEquip",
    "AddItem":   "onAddItem",
    "RemoveItem": "onRemoveItem",
}

MOVEMENT_REGISTRATION = {
    "class": "MoveEvent",
    "id_methods": {
        "itemid": "id",
        "fromid": "id",
        "actionid": "aid",
        "uniqueid": "uid",
        "tileitem": "tileItem",
    },
    "extra_attrs": {},
}

# TalkActions → TalkAction()

TALKACTION_REGISTRATION = {
    "class": "TalkAction",
    "event_method": "onSay",
    "constructor_args": ["words"],  # TalkAction("/command")
    "id_methods": {},
    "extra_attrs": {
        "separator": "separator",
        "access": "access",         # old attr
    },
}

# CreatureScripts → CreatureEvent()

CREATUREEVENT_TYPES = {
    "login":        "onLogin",
    "logout":       "onLogout",
    "death":        "onDeath",
    "kill":         "onKill",
    "preparedeath": "onPrepareDeath",
    "advance":      "onAdvance",
    "textedit":     "onTextEdit",
    "healthchange": "onHealthChange",
    "manachange":   "onManaChange",
    "think":        "onThink",
    "modalwindow":  "onModalWindow",
    "extendedopcode": "onExtendedOpcode",
}

CREATUREEVENT_REGISTRATION = {
    "class": "CreatureEvent",
    "constructor_args": ["name"],  # CreatureEvent("EventName")
    "id_methods": {},
    "extra_attrs": {},
}

# GlobalEvents → GlobalEvent()

GLOBALEVENT_TYPES = {
    "start":    "onStartup",
    "startup":  "onStartup",
    "shutdown": "onShutdown",
    "record":   "onRecord",
    "timer":    "onTime",
    "time":     "onTime",
}

GLOBALEVENT_REGISTRATION = {
    "class": "GlobalEvent",
    "constructor_args": ["name"],  # GlobalEvent("EventName")
    "id_methods": {},
    "extra_attrs": {
        "interval": "interval",
        "time": "time",
    },
}
