# Actions

2 entries

| Name | Script | Item ID | Action ID | Description |
|------|--------|------|------|-------------|
| healing_potion | healing_potion.lua | 2274 |  | TFS 0.3 Action Script: Example Healing Potion |
| teleport_scroll | teleport_scroll.lua | 2275 |  | TFS 0.3 Action Script: Teleport Scroll |

### healing_potion

- **itemid:** 2274

```lua
-- TFS 0.3 Action Script: Example Healing Potion
-- This is a typical TFS 0.3 style script using procedural API

function onUse(cid, item, frompos, item2, topos)
    if getPlayerLevel(cid) < 10 then
        doPlayerSendCancel(cid, "You need level 10 to use this item.")
        doSendMagicEffect(getCreaturePosition(cid), CONST_ME_POFF)
        return TRUE
    end

    local health = getCreatureHealth(cid)
    local maxHealth = getCreatureMaxHealth(cid)

    if health >= maxHealth then
        doPlayerSendTextMessage(cid, MESSAGE_STATUS_SMALL, "You are already at full health.")
        return TRUE
    end

    local healAmount = math.random(100, 200)
    doCreatureAddHealth(cid, healAmount)
    doSendMagicEffect(getCreaturePosition(cid), CONST_ME_MAGIC_BLUE)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "You healed " .. healAmount .. " health.")

    doRemoveItem(item.uid, 1)
    return TRUE
end
```

### teleport_scroll

- **itemid:** 2275

```lua
-- TFS 0.3 Action Script: Teleport Scroll
-- Complex example with multiple function calls and storage usage

local STORAGE_COOLDOWN = 45001
local COOLDOWN_TIME = 60

function onUse(cid, item, frompos, item2, topos)
    if getPlayerStorageValue(cid, STORAGE_COOLDOWN) > os.time() then
        doPlayerSendCancel(cid, "You must wait before using this again.")
        doSendMagicEffect(getCreaturePosition(cid), CONST_ME_POFF)
        return TRUE
    end

    if isPremium(cid) == FALSE then
        doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "This item requires premium account.")
        return TRUE
    end

    local destination = {x = 1000, y = 1000, z = 7}
    local playerPos = getPlayerPosition(cid)

    doSendMagicEffect(playerPos, CONST_ME_TELEPORT)
    doTeleportThing(cid, destination)
    doSendMagicEffect(destination, CONST_ME_TELEPORT)

    doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "You have been teleported!")
    doPlayerSetStorageValue(cid, STORAGE_COOLDOWN, os.time() + COOLDOWN_TIME)

    doCreatureSay(cid, "Woosh!", TALKTYPE_ORANGE_1)
    doRemoveItem(item.uid, 1)

    return TRUE
end
```
