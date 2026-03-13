local STORAGE_COOLDOWN = 45001
local COOLDOWN_TIME = 60

local teleport_scroll = Action()

function teleport_scroll.onUse(player, item, fromPosition, target, toPosition, isHotkey)
	if player:getStorageValue(STORAGE_COOLDOWN) > os.time() then
		player:sendCancelMessage("You must wait before using this again.")
		player:getPosition():sendMagicEffect(CONST_ME_POFF)
		return true
	end

	if player:isPremium() == false then
		player:sendTextMessage(MESSAGE_INFO_DESCR, "This item requires premium account.")
		return true
	end

	local destination = Position(1000, 1000, 7)
	local playerPos = player:getPosition()

	playerPos:sendMagicEffect(CONST_ME_TELEPORT)
	player:teleportTo(destination)
	destination:sendMagicEffect(CONST_ME_TELEPORT)

	player:sendTextMessage(MESSAGE_INFO_DESCR, "You have been teleported!")
	player:setStorageValue(STORAGE_COOLDOWN, os.time() + COOLDOWN_TIME)

	player:say("Woosh!", TALKTYPE_MONSTER_SAY)
	Item(item.uid):remove(1)

	return true
end

teleport_scroll:id(2275)
teleport_scroll:register()
