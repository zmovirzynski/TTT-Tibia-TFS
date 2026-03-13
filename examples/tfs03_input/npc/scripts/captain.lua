-- TFS 0.3 NPC Script: Captain (Travel NPC)
-- Typical travel NPC using NpcHandler module

local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Hello |PLAYERNAME|! Do you want to {travel}?")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end

    if msgcontains(msg, "travel") then
        if getPlayerLevel(cid) < 20 then
            selfSay("You need level 20 to travel.", cid)
            return true
        end

        if not isPremium(cid) then
            selfSay("You need a premium account to travel.", cid)
            return true
        end

        local price = 100
        if doPlayerRemoveMoney(cid, price) then
            doTeleportThing(cid, {x=1000, y=1000, z=7})
            doSendMagicEffect(getCreaturePosition(cid), CONST_ME_TELEPORT)
            selfSay("Here we go!", cid)
        else
            selfSay("You don't have " .. price .. " gold.", cid)
        end
    end

    if msgcontains(msg, "name") then
        selfSay("My name is " .. getNpcName() .. ".", cid)
    end

    return true
end

npcHandler:addModule(FocusModule:new())
