local startup = GlobalEvent("ServerStart")

function startup.onStartup()
	Game.broadcastMessage("Server is now online!", MESSAGE_STATUS_WARNING)
	Game.setStorageValue(50001, os.time())
	print("[ServerStart] Server initialized at " .. os.date())
	return true
end

startup:register()
