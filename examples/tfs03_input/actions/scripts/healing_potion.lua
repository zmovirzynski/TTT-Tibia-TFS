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
