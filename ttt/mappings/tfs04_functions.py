"""Mapeamento de funções TFS 0.4 → TFS 1.x (herda do 0.3 e adiciona/sobrescreve)."""

from .tfs03_functions import TFS03_TO_1X

# Start with all 0.3 mappings (most are the same)
TFS04_TO_1X = dict(TFS03_TO_1X)

# TFS 0.4 SPECIFIC FUNCTIONS (additions and overrides)

TFS04_SPECIFIC = {
    "getPlayerLossPercent": {
        "method": "getDeathPenalty",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
        "note": "-- TTT: Death penalty system changed in 1.x. Review this.",
    },
    "doPlayerSetLossPercent": {
        "method": "setDeathPenalty",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
        "note": "-- TTT: Death penalty system changed in 1.x. Review this.",
    },
    "getPlayerLossSkill": {
        "method": "getDeathPenalty",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
        "note": "-- TTT: Death penalty system changed in 1.x. Review this.",
    },
    "getCreatureNoMove": {
        "method": "isMovementBlocked",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCreatureSetNoMove": {
        "method": "setMovementBlocked",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "getCreatureSkull": {
        "method": "getSkull",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCreatureSetSkullType": {
        "method": "setSkull",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCombat": {
        "method": "execute",
        "obj_type": "combat",
        "obj_param": None,
        "drop_params": [],
        "note": "-- TTT: Use Combat:execute() in 1.x",
        "custom": "combat_passthrough",
    },
    "doCreatureCastSpell": {
        "method": "castSpell",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
        "note": "-- TTT: Review spell casting API in 1.x",
    },
    "getContainerSize": {
        "method": "getSize",
        "obj_type": "container",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Container",
    },
    "getContainerCap": {
        "method": "getCapacity",
        "obj_type": "container",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Container",
    },
    "getContainerItem": {
        "method": "getItem",
        "obj_type": "container",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Container",
    },
    "doItemSetActionId": {
        "method": "setActionId",
        "obj_type": "item",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Item",
    },
    "getTileHouseInfo": {
        "method": "getHouse",
        "obj_type": "tile",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Tile",
    },
    "getTileCreatures": {
        "method": "getCreatures",
        "obj_type": "tile",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Tile",
    },
    "getTileItems": {
        "method": "getItems",
        "obj_type": "tile",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Tile",
    },
    "getTownId": {
        "method": "getId",
        "obj_type": "town",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Town",
    },
    "getTownName": {
        "method": "getName",
        "obj_type": "town",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Town",
    },
    "getTownTemplePosition": {
        "method": "getTemplePosition",
        "obj_type": "town",
        "obj_param": 0,
        "drop_params": [0],
        "wrapper": "Town",
    },
    "getCreatureByName": {
        "method": "getCreatureByName",
        "obj_type": "game",
        "obj_param": None,
        "drop_params": [],
        "static": True,
        "static_class": "Creature",
    },
    "doPlayerSendModalWindow": {
        "method": "sendModalWindow",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
    },
    "getPlayerDepotItems": {
        "method": "getDepotChest",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
        "note": "-- TTT: In 1.x use player:getDepotChest(depotId)",
    },
    "doPlayerOpenChannel": {
        "method": "openChannel",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doPlayerSetStorageValue": {
        "method": "setStorageValue",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
    },
    "getPlayerStorageValue": {
        "method": "getStorageValue",
        "obj_type": "player",
        "obj_param": 0,
        "drop_params": [0],
    },
}

TFS04_TO_1X.update(TFS04_SPECIFIC)
