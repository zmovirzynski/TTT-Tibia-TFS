local broadcast = TalkAction("/bc")

function broadcast.onSay(player, words, param)
	if player:getGroup()  -- TTT: Returns Group object. Use :getId() for numeric ID < 3 then
		player:sendCancelMessage("You do not have permission to use this command.")
		return true
	end

	if param == "" then
		player:sendCancelMessage("Usage: /bc message")
		return true
	end

	Game.broadcastMessage(param, MESSAGE_STATUS_WARNING)
	player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Broadcast sent: " .. param)

	return true
end

broadcast:access(3)
broadcast:register()
