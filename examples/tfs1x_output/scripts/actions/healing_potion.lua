local healing_potion = Action()

function healing_potion.onUse(player, item, fromPosition, target, toPosition, isHotkey)
	if player:getLevel() < 10 then
		player:sendCancelMessage("You need level 10 to use this item.")
		player:getPosition():sendMagicEffect(CONST_ME_POFF)
		return true
	end

	local health = player:getHealth()
	local maxHealth = player:getMaxHealth()

	if health >= maxHealth then
		player:sendTextMessage(MESSAGE_STATUS_SMALL, "You are already at full health.")
		return true
	end

	local healAmount = math.random(100, 200)
	player:addHealth(healAmount)
	player:getPosition():sendMagicEffect(CONST_ME_MAGIC_BLUE)
	player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "You healed " .. healAmount .. " health.")

	Item(item.uid):remove(1)
	return true
end

healing_potion:id(2274)
healing_potion:register()
