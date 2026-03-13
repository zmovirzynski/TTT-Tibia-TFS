-- TFS 0.3 NPC Script: Shopkeeper Tom
-- Equipment shop NPC using NpcHandler + ShopModule

local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Welcome, |PLAYERNAME|! I buy and sell equipment.")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end

    if msgcontains(msg, "balance") then
        local balance = getPlayerBalance(cid)
        selfSay("Your bank balance is " .. balance .. " gold.", cid)
        return true
    end

    if msgcontains(msg, "level") then
        local level = getPlayerLevel(cid)
        selfSay("You are level " .. level .. ".", cid)
        return true
    end

    if msgcontains(msg, "help") then
        local name = getCreatureName(cid)
        doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "Hello " .. name .. "! Say 'trade' to open my shop.")
        return true
    end

    return true
end

npcHandler:addModule(FocusModule:new())
npcHandler:addModule(ShopModule:new())
