local leveldoor = MoveEvent()

function leveldoor.onStepIn(creature, item, position, fromPosition)
	if not creature:isPlayer() then
		return true
	end

	local requiredLevel = item.actionid - 1000

	if creature:getLevel() < requiredLevel then
		creature:sendCancelMessage("You need level " .. requiredLevel .. " to pass.")
		creature:teleportTo(fromPosition)
		position:sendMagicEffect(CONST_ME_MAGIC_BLUE)
		return true
	end

	position:sendMagicEffect(CONST_ME_TELEPORT)
	creature:sendTextMessage(MESSAGE_INFO_DESCR, "Welcome! You passed the level door.")
	return true
end

leveldoor:type("stepin")
leveldoor:aid(1001)
leveldoor:aid(1002)
leveldoor:aid(1003)
leveldoor:aid(1004)
leveldoor:aid(1005)
leveldoor:register()
