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
