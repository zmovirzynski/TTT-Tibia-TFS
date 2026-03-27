--[[
    TTT Compatibility Library for TFS 0.3.6 → TFS 1.x conversions
    
    This file provides Lua implementations of common TFS 0.3.6 functions
    that don't have direct equivalents in TFS 1.x API. These implementations
    use the TFS 1.x OOP API to emulate the old behavior.
    
    Usage: Include this file in your TFS 1.x server's data/lib/ folder
    and require it in your main lib file.
]]

-- ============================================
-- Creature / Player Utilities
-- ============================================

function isSummon(creature)
    if not creature then
        return false
    end
    local c = Creature(creature)
    return c ~= nil and c:getMaster() ~= nil
end

function isPlayerSummon(creature)
    if not creature then
        return false
    end
    local c = Creature(creature)
    if not c then
        return false
    end
    local master = c:getMaster()
    return master ~= nil and master:isPlayer()
end

function getCreatureHealthSecurity(creature)
    if not creature then
        return 0
    end
    local c = Creature(creature)
    if not c then
        return 0
    end
    return math.max(0, c:getHealth())
end

-- ============================================
-- Position / Tile Utilities
-- ============================================

function getHouseFromPos(pos)
    local tile = Tile(pos)
    if not tile then
        return nil
    end
    local house = tile:getHouse()
    return house and house:getId() or nil
end

function isWalkable(pos)
    local tile = Tile(pos)
    if not tile then
        return false
    end
    -- Check if tile has blocking flags
    return not tile:hasFlag(TILESTATE_BLOCKSOLID)
end

function isSightClear(fromPos, toPos, sameFloor)
    local from = Position(fromPos)
    return from:isSightClear(toPos, sameFloor ~= false)
end

function getClosestFreeTile(creature, pos, radius)
    radius = radius or 1
    local center = Position(pos)
    
    for dx = -radius, radius do
        for dy = -radius, radius do
            local checkPos = Position(center.x + dx, center.y + dy, center.z)
            local tile = Tile(checkPos)
            if tile and not tile:hasFlag(TILESTATE_BLOCKSOLID) then
                return checkPos
            end
        end
    end
    return nil
end

-- ============================================
-- Town Utilities
-- ============================================

function getTownTemplePosition(townId)
    local town = Town(townId)
    if not town then
        return nil
    end
    return town:getTemplePosition()
end

-- ============================================
-- Item Utilities
-- ============================================

function isContainer(uid)
    local item = Item(uid)
    if not item then
        return false
    end
    return item:isContainer()
end

function getItemNameById(itemId)
    local itemType = ItemType(itemId)
    if not itemType then
        return ""
    end
    return itemType:getName()
end

-- ============================================
-- Table / Array Utilities
-- ============================================

function isInArray(array, value)
    if type(array) ~= "table" then
        return false
    end
    for _, v in ipairs(array) do
        if v == value then
            return true
        end
    end
    return false
end

-- ============================================
-- Debug / Development Utilities
-- ============================================

function getThingPosWithDebug(thing)
    -- Same as getThingPos but with debug logging
    -- In TFS 1.x, we just use getPosition directly
    local c = Creature(thing)
    if c then
        return c:getPosition()
    end
    local i = Item(thing)
    if i then
        return i:getPosition()
    end
    return Position(0, 0, 0)
end

-- ============================================
-- Compatibility Aliases
-- ============================================

-- Alias for backward compatibility
getThingPos = getThingPos or function(thing)
    local c = Creature(thing)
    if c then
        return c:getPosition()
    end
    local i = Item(thing)
    if i then
        return i:getPosition()
    end
    return Position(0, 0, 0)
end
