-- TFS 0.3 CreatureScript: Player Login
-- Typical login script with messages and storage checks

function onLogin(cid)
    local playerName = getCreatureName(cid)
    local playerLevel = getPlayerLevel(cid)

    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Welcome, " .. playerName .. "!")

    if playerLevel < 8 then
        doPlayerSendTextMessage(cid, MESSAGE_EVENT_ADVANCE, "You are still a rookie. Visit the training area!")
    end

    -- Premium check
    if isPremium(cid) then
        doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "Your premium account is active.")
        local premDays = getPlayerPremiumDays(cid)
        doPlayerSendTextMessage(cid, MESSAGE_STATUS_CONSOLE_BLUE, "Premium days remaining: " .. premDays)
    end

    -- Register death event
    registerCreatureEvent(cid, "PlayerDeath")

    -- Set login storage
    doPlayerSetStorageValue(cid, 50000, 1)

    return TRUE
end
