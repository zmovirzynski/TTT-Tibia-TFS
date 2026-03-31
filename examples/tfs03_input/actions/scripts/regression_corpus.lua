-- TFS 0.3 Regression Corpus Script
-- Exercises ALL major mapping categories for conversion testing
-- Each section covers a different function group

-- =============================================================================
-- Section 1: Player Getters (basic OOP wrapping)
-- =============================================================================
function onLogin(cid)
    local name = getPlayerName(cid)
    local level = getPlayerLevel(cid)
    local exp = getPlayerExperience(cid)
    local magLevel = getPlayerMagLevel(cid)
    local voc = getPlayerVocation(cid)
    local sex = getPlayerSex(cid)
    local guid = getPlayerGUID(cid)
    local groupId = getPlayerGroupId(cid)
    local ip = getPlayerIp(cid)
    local pos = getPlayerPosition(cid)
    local health = getCreatureHealth(cid)
    local maxHealth = getCreatureMaxHealth(cid)
    local mana = getPlayerMana(cid)
    local maxMana = getPlayerMaxMana(cid)
    local cap = getPlayerFreeCap(cid)
    local soul = getPlayerSoul(cid)
    local stamina = getPlayerStamina(cid)
    local balance = getPlayerBalance(cid)
    local skillLevel = getPlayerSkillLevel(cid, SKILL_SWORD)
    local skillTries = getPlayerSkillTries(cid, SKILL_SWORD)

    -- Town/Guild/Vocation object unwrapping (chain tests)
    local townId = getPlayerTown(cid)
    local guildId = getPlayerGuildId(cid)
    local guildName = getPlayerGuildName(cid)
    local guildNick = getPlayerGuildNick(cid)

    -- Storage
    local val = getPlayerStorageValue(cid, 12345)
    setPlayerStorageValue(cid, 12345, val + 1)

    return TRUE
end

-- =============================================================================
-- Section 2: Player Actions (doPlayer*)
-- =============================================================================
function onUsePotionAction(cid, item, frompos, item2, topos)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "You used a potion.")
    doPlayerSendCancel(cid, "You cannot do that.")
    doPlayerAddItem(cid, 2160, 10)
    doPlayerRemoveItem(cid, 2152, 1)
    doPlayerAddMana(cid, 500)
    doPlayerAddHealth(cid, 300)
    doPlayerAddSoul(cid, 1)
    doPlayerAddMoney(cid, 1000)
    doPlayerRemoveMoney(cid, 500)
    doPlayerFeed(cid, 300)
    doPlayerSetVocation(cid, 2)
    doPlayerSetMaxCapacity(cid, 50000)
    doPlayerAddSkillTry(cid, SKILL_SWORD, 10)
    doPlayerSetBalance(cid, 100000)
    doPlayerSetStamina(cid, 2400)
    doPlayerSetTown(cid, 1)
    doPlayerSave(cid)
    doCreatureAddHealth(cid, 100)
    doRemoveItem(item.uid, 1)
    return TRUE
end

-- =============================================================================
-- Section 3: Creature Functions
-- =============================================================================
function onThinkCreature(cid, interval)
    local name = getCreatureName(cid)
    local pos = getCreaturePosition(cid)
    local speed = getCreatureSpeed(cid)
    local master = getCreatureMaster(cid)
    local summons = getCreatureSummons(cid)
    local outfit = getCreatureOutfit(cid)

    doChangeSpeed(cid, 200)
    setCreatureMaxHealth(cid, 5000)
    doCreatureSetHideHealth(cid, true)
    doCreatureSetNoMove(cid, false)
    doCreatureSetSkullType(cid, SKULL_WHITE)
    doCreatureSetLookDirOk(cid, DIRECTION_NORTH)
    doCreatureSetOutfit(cid, outfit)
    doTeleportThing(cid, {x=100, y=200, z=7})
    registerCreatureEvent(cid, "PlayerDeath")
    return TRUE
end

-- =============================================================================
-- Section 4: Item Functions
-- =============================================================================
function onUseItem(cid, item, frompos, item2, topos)
    local name = getItemName(item.uid)
    local nameById = getItemNameById(2160)
    local weight = getItemWeight(item.uid)
    local desc = getItemDescriptions(item.uid)
    local idByName = getItemIdByName("magic plate armor")

    doTransformItem(item.uid, 2153)
    doItemSetAttribute(item.uid, "description", "Modified item")
    doItemEraseAttribute(item.uid, "description")
    doSetItemActionId(item.uid, 1000)
    doSetItemText(item.uid, "Hello world")
    doDecayItem(item.uid)
    doRemoveItem(item.uid, 1)

    if isContainer(item.uid) then
        doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "This is a container!")
    end
    return TRUE
end

-- =============================================================================
-- Section 5: Game / World Functions (static calls)
-- =============================================================================
function onSayGlobal(cid, words, param)
    broadcastMessage("Server announcement: " .. param, MESSAGE_STATUS_WARNING)
    doCreateItem(2160, 10, getPlayerPosition(cid))
    doCreateMonster("Demon", {x=100, y=200, z=7})
    doCreateNpc("Merchant", {x=101, y=200, z=7})
    doSummonCreature("Dragon", {x=102, y=200, z=7})

    local target = getPlayerByName(param)
    local time = getWorldTime()
    local uptime = getWorldUpTime()
    local online = getPlayersOnline()

    return TRUE
end

-- =============================================================================
-- Section 6: Position/Effect Functions
-- =============================================================================
function onMoveEffect(cid)
    local pos = getCreaturePosition(cid)
    doSendMagicEffect(pos, CONST_ME_TELEPORT)
    doSendDistanceShoot(pos, {x=105, y=200, z=7}, CONST_ANI_FIRE)
    doSendAnimatedText(pos, "Critical!", 180)
    local dist = getDistanceBetween(pos, {x=100, y=200, z=7})
    return TRUE
end

-- =============================================================================
-- Section 7: Tile Functions (with getTileInfo strategy)
-- =============================================================================
function onMoveTile(cid, item, frompos, item2, topos)
    local itemOnTile = getTileItemById(topos, 1387)
    local pzInfo = getTilePzInfo(topos)
    local topThing = getTileThingByPos(topos)
    local info = getTileInfo(topos)
    local house = getHouseFromPos(topos)
    doCleanTile(topos)

    if isSightClear(frompos, topos) then
        doTeleportThing(cid, topos)
    end
    return TRUE
end

-- =============================================================================
-- Section 8: House Functions
-- =============================================================================
function onSayHouse(cid, words, param)
    local house = getHouseByPlayerGUID(getPlayerGUID(cid))
    local owner = getHouseOwner(house)
    local hname = getHouseName(house)
    local rent = getHouseRent(house)
    local entry = getHouseEntry(house)
    local town = getHouseTown(house)
    setHouseOwner(house, 0)
    return TRUE
end

-- =============================================================================
-- Section 9: doSendAnimatedText (129 occurrences in real corpus)
-- Should now produce a clear removal note, not a broken conversion
-- =============================================================================
function onCombatAnimatedText(cid, target)
    local pos = getCreaturePosition(cid)
    doSendAnimatedText(pos, "MISS", 215)
    doSendAnimatedText(getCreaturePosition(target), tostring(damage), 180)
    doSendAnimatedText({x=100,y=200,z=7}, "TEST", 35)
    return TRUE
end

-- =============================================================================
-- Section 10: New mappings from investigation-findings
-- =============================================================================
function onUseExtended(cid, item, frompos, item2, topos)
    doSendPlayerExtendedOpcode(cid, 100, "data")
    local pos = getThingPosWithDebug(cid)
    local templePos = getTownTemplePosition(1)
    return TRUE
end

-- =============================================================================
-- Section 11: Constants
-- =============================================================================
function onUseConstants(cid, item, frompos, item2, topos)
    if TRUE then
        doPlayerSendTextMessage(cid, TALKTYPE_ORANGE_1, "Hello")
    end
    if FALSE then
        return TRUE
    end
    return FALSE
end
