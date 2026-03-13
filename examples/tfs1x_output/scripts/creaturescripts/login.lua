local login = CreatureEvent("PlayerLogin")

function login.onLogin(player)
	local playerName = player:getName()
	local playerLevel = player:getLevel()

	player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Welcome, " .. playerName .. "!")

	if playerLevel < 8 then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "You are still a rookie. Visit the training area!")
	end

	-- Premium check
	if player:isPremium() then
		player:sendTextMessage(MESSAGE_INFO_DESCR, "Your premium account is active.")
		local premDays = player:getPremiumDays()
		player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Premium days remaining: " .. premDays)
	end

	-- Register death event
	player:registerEvent("PlayerDeath")

	-- Set login storage
	player:setStorageValue(50000, 1)

	return true
end

login:register()
