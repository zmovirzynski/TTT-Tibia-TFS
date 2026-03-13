-- TFS 0.3 Movement Script: Level Door
-- Typical step-in script

function onStepIn(cid, item, position, fromPosition)
    if not isPlayer(cid) then
        return TRUE
    end

    local requiredLevel = item.actionid - 1000

    if getPlayerLevel(cid) < requiredLevel then
        doPlayerSendCancel(cid, "You need level " .. requiredLevel .. " to pass.")
        doTeleportThing(cid, fromPosition)
        doSendMagicEffect(position, CONST_ME_MAGIC_BLUE)
        return TRUE
    end

    doSendMagicEffect(position, CONST_ME_TELEPORT)
    doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "Welcome! You passed the level door.")
    return TRUE
end
