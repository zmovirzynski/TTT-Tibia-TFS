# Investigation Findings: TFS03 → RevScript Conversion Gap Analysis

**Date:** 2026-03-24
**Sources analyzed:**

- Original scripts: `/home/gaamelu/development/pokemon-invictus/PokeInvictus/data/` (694 files converted)
- Gold standard: `/home/gaamelu/development/PokeQuest/server/data/scripts/` (485 Lua files)
- Gold standard canary: `/home/gaamelu/development/PokeQuest/server/data-canary/scripts/` (25 Lua files)
- C++ API bindings: `/home/gaamelu/development/PokeQuest/server/src/lua/functions/` (52 C++ files)
- Last conversion output: `/home/gaamelu/development/PokeQuest/server/data-invictus-converted/` (694 converted files)

---

## 1. Conversion Quality Snapshot

From `conversion_report.txt` (last run 2026-03-24):

| Metric                                      | Value    |
| ------------------------------------------- | -------- |
| Files processed                             | 694      |
| Function calls converted                    | 6,982    |
| Variables renamed                           | 8,448    |
| Defensive checks added                      | 2,427    |
| **Points needing review (-- TTT:)**         | **202**  |
| Unrecognized calls (per llm_refactor_guide) | 2,029    |
| Estimated confidence                        | 97% HIGH |

---

## 2. Active TTT Review Markers (202 total)

These are inserted as comments in the converted output and require manual attention:

| Count | Marker                                                 | Issue                                                                                                  | Suggested fix                                                                                                 |
| ----- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| 129   | `doSendAnimatedText removed in 1.x`                    | `doSendAnimatedText` was mapped to `sendMagicEffect` but the original behavior (floating text) is gone | Consider mapping to `creature:say(text, TALKTYPE_MONSTER_SAY)` or dropping the call                           |
| 37    | `getTileInfo replaced. Use Tile methods individually.` | `getTileInfo(pos)` returned a table; TFS 1.x splits this into separate Tile methods                    | Replace with `local tile = Tile(pos)` then `tile:getGround()`, `tile:getItemById()`, `tile:hasFlag(...)` etc. |
| 12    | `returns Town object in 1.x, use :getId()`             | `getPlayerTown(cid)` now returns a `Town` object                                                       | Use `player:getTown():getId()` for numeric ID, or `player:getTown():getName()` for name                       |
| 9     | `Returns Group object. Use :getId()`                   | `getPlayerGroupId(cid)` returns `Group` object now                                                     | Use `player:getGroup():getId()`                                                                               |
| 6+1   | `Returns Guild object`                                 | Guild getters return `Guild` object                                                                    | Use `player:getGuild():getId()`, `:getName()`, `:getNick()`                                                   |
| 3     | `Wildcard lookup not directly supported in 1.x`        | `getPlayerByNameWildcard` → `Player.getPlayerByName(wildcard)` fails                                   | Use exact name match; implement client-side fuzzy lookup if needed                                            |
| 2     | `doPlayerSetRate removed`                              | No equivalent in TFS 1.x                                                                               | Remove or reimplement using experience stage config                                                           |
| 1     | `Vocation object: use :getId()`                        | Vocation is an object now                                                                              | Use `player:getVocation():getId()`                                                                            |

---

## 3. Missing Mappings in `tfs03_functions.py`

We currently have **182 mapped functions**. The following appear frequently in original scripts but are **not mapped**.

### 3A. Genuine TFS03 API aliases — should add immediately

These are standard TFS03 functions with known TFS 1.x equivalents:

```python
# Add to PLAYER_SETTERS (or create ALIASES section)
"setPlayerStorageValue": {
    # Used 1,226x in originals — alternate naming for doPlayerSetStorageValue
    # In TFS03: setPlayerStorageValue(cid, key, val) — same as doPlayerSetStorageValue
    "method": "setStorageValue",
    "obj_type": "player",
    "obj_param": 0,
    "drop_params": [0],
},
```

```python
# Add to ITEM_FUNCTIONS or MISC_FUNCTIONS
"getItemNameById": {
    # Used 148x in originals
    # TFS03: getItemNameById(itemId) → string
    # TFS 1.x: ItemType(itemId):getName()
    # Cannot be auto-converted (needs constructor call, different syntax)
    # Mark as manual: note = "-- TTT: Use ItemType(id):getName() in 1.x"
    "note": "-- TTT: Replace with ItemType(id):getName()",
},
```

```python
# Add to CREATURE_FUNCTIONS
"doChangeSpeed": {
    # Used 103x in originals
    # TFS03: doChangeSpeed(cid, delta) — adds delta to current speed
    # TFS 1.x: creature:changeSpeed(delta)  ← confirmed in C++ bindings
    "method": "changeSpeed",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
},
```

```python
# Add to MISC_FUNCTIONS
"getTownTemplePosition": {
    # Used 81x in originals
    # TFS03: getTownTemplePosition(townId) → position
    # TFS 1.x: Town(townId):getTemplePosition()
    # Syntax change — needs note, cannot auto-convert cleanly
    "note": "-- TTT: Replace with Town(townId):getTemplePosition()",
},
```

```python
# Add to CREATURE_FUNCTIONS
"doCreatureSetLookDirOk": {
    # Used 47x in originals — same as doCreatureSetLookDir but custom "Ok" variant
    # TFS 1.x: creature:setDirection(dir)
    "method": "setDirection",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
},
```

```python
# isContainer — add to MISC_FUNCTIONS
"isContainer": {
    # Used 53x in originals
    # TFS03: isContainer(uid) — returns bool
    # TFS 1.x: Item(uid):isContainer()  ← confirmed in C++ bindings
    "note": "-- TTT: Replace with Item(uid):isContainer()",
},
```

```python
# isSightClear — add to MISC_FUNCTIONS
"isSightClear": {
    # Used 52x in originals
    # TFS 1.x: pos1:isSightClear(pos2[, sameFloor=true])  ← confirmed in C++ bindings (Position class)
    "note": "-- TTT: Replace with fromPos:isSightClear(toPos)",
},
```

```python
# doSendPlayerExtendedOpcode — add to PLAYER_SETTERS
"doSendPlayerExtendedOpcode": {
    # Used 144x in originals
    # TFS03: doSendPlayerExtendedOpcode(cid, opcode, buffer)
    # TFS 1.x: player:sendExtendedOpcode(opcode, buffer)  ← CreatureEvent.onExtendedOpcode in C++
    # Note: API is via CreatureEvent now, not direct call
    "note": "-- TTT: Use player:sendExtendedOpcode(opcode, buffer) or CreatureEvent:onExtendedOpcode",
},
```

### 3B. Creature setters with TFS 1.x equivalents — add to mappings

These appear in original scripts as custom wrappers but have direct 1.x equivalents:

```python
# In original scripts as game-specific but map cleanly:
"setCreatureMaxHealth": {
    # TFS 1.x: creature:setMaxHealth(health)  ← confirmed in C++
    "method": "setMaxHealth",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
},

"doCreatureSetHideHealth": {
    # TFS 1.x: creature:setHiddenHealth(bool)  ← confirmed in C++
    "method": "setHiddenHealth",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
},

"doCreatureSetNoMove": {
    # TFS 1.x: creature:setMoveLocked(bool)  ← confirmed in C++
    "method": "setMoveLocked",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
},

"doCreatureSetSkullType": {
    # TFS 1.x: creature:setSkull(skullType)  ← confirmed in C++
    "method": "setSkull",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
},

"doCreatureSetNick": {
    # Custom function for setting creature nickname / custom name
    # Likely maps to creature:setDescription() or creature:setName() — needs verification
    "note": "-- TTT: No direct equivalent. Check if creature:setName() or custom solution needed.",
},
```

### 3C. Custom game-specific functions (NOT standard TFS API)

These are defined in the game's `lib/` files and will NOT be in TFS 1.x. They need custom reimplementation:

| Function                          | Count | Nature                                     | Notes                                                                   |
| --------------------------------- | ----- | ------------------------------------------ | ----------------------------------------------------------------------- |
| `getThingPosWithDebug`            | 1,602 | Custom debug wrapper                       | Same as `getThingPos` but with logging. Map to `getThingPos` + note     |
| `isInArray`                       | 884   | Custom table utility                       | No stdlib equiv in Lua 5.1. Needs custom lib function in TFS 1.x too    |
| `isSummon`                        | 876   | Custom creature check                      | `creature:getMaster() ~= nil` in 1.x                                    |
| `getSubName`                      | 324   | Custom Pokemon function                    | Reads pokemon subspecies name from custom storage                       |
| `doDanoWithProtect`               | 243   | Custom combat wrapper                      | Wraps `doAreaCombatHealth`/`doTargetCombatHealth` with protection logic |
| `doCorrectString`                 | 242   | Custom string utility                      | Likely string normalization (trim, lower, etc.)                         |
| `isWild`                          | 173   | Custom Pokemon function                    | Checks if pokemon is wild (storage-based)                               |
| `isMega`                          | 160   | Custom Pokemon function                    | Checks if pokemon is mega evolved                                       |
| `isPlayerSummon`                  | 159   | Custom: `creature:getMaster()` is a player | `local m = creature:getMaster(); return m and m:isPlayer()`             |
| `getRealCreatureName`             | 137   | Custom name formatter                      | Gets display name stripping suffixes                                    |
| `isGod`                           | 127   | Custom: checks player access               | `player:hasGroupFlag(PlayerFlag_IsAdmin)` or similar                    |
| `getCreatureDirectionToTarget`    | 127   | Custom math utility                        | Computes direction from position delta                                  |
| `isSleeping`                      | 99    | Custom Pokemon status                      | Checks sleeping condition via storage                                   |
| `doDanoInTargetWithDelay`         | 93    | Custom combat with addEvent                | Delayed combat wrapper                                                  |
| `getDataInt`                      | 92    | Custom: reads integer from DB              | Database helper                                                         |
| `getClosestFreeTile`              | 87    | Custom pathfinding                         | No direct 1.x equivalent; may use `Game.getSpectators` or position math |
| `doSendMsg`                       | 83    | Custom broadcast helper                    | Thin wrapper around `doCreatureSay` or `sendTextMessage`                |
| `getTownTemplePosition` (via lib) | 81    | Custom alias                               | Wraps `Town(id):getTemplePosition()`                                    |
| `getID`                           | 80    | Custom: returns item unique ID             | `item:getUniqueId()` or `item:getId()`                                  |
| `getResult`                       | 68    | Custom: DB result helper                   | `db.storeQuery` result handling                                         |
| `doTeleportThingOk`               | 62    | Custom OK variant                          | Same as `doTeleportThing` but returns status                            |
| `getHouseFromPos`                 | 56    | Gets house from tile                       | `Tile(pos):getHouse()` in 1.x                                           |
| `doRegainSpeed`                   | 55    | Custom: restores speed                     | Reverses `doChangeSpeed`, use `creature:changeSpeed(+delta)`            |
| `getCreatureHealthSecurity`       | 53    | Custom: safe health getter                 | `math.max(0, creature:getHealth())`                                     |
| `doMoveInAreaMulti`               | 53    | Custom: moves items in area                | No direct 1.x equivalent                                                |
| `isWalkable`                      | 51    | Custom tile check                          | `Tile(pos):queryAdd(FLAG_NOLIMIT)` or custom logic                      |

---

## 4. `doSendAnimatedText` — Critical Volume Issue

**129 occurrences** in converted files, all marked `-- TTT:`. This is the single biggest review burden.

**Root cause:** TFS03 `doSendAnimatedText(pos, text, color)` showed colored floating text above a position. In TFS 1.x, this API was **removed**. We currently emit a warning but still try to use it.

**Recommendation:** Change the mapping to actively comment out the call and suggest `sendMagicEffect`:

```python
"doSendAnimatedText": {
    "note": "-- TTT: doSendAnimatedText removed. Use creature:say(text, TALKTYPE_MONSTER_SAY) or sendMagicEffect.",
    "drop_entirely": True,  # or add a "disabled" flag
},
```

Or — since many of these are visual feedback — provide a comment-out with the effect color ID:
`-- REMOVED: doSendAnimatedText(pos, "{text}", {color}) — no TFS 1.x equivalent`

---

## 5. `getTileInfo` — 37 Occurrences

**Pattern:** `getTileInfo(pos)` returned a table `{ground, items, top, creature, ...}`.
**TFS 1.x:** Use `local tile = Tile(pos)` then call individual methods.

Suggested TTT improvement: emit scaffolding code:

```lua
-- TTT: getTileInfo replaced. Use:
-- local tile = Tile(pos)
-- tile:getGround(), tile:getItems(), tile:getCreatures(), tile:getTopVisibleCreature()
```

---

## 6. OOP API Catalog — New Methods Available in TFS 1.x (Not Yet Targeted)

From C++ bindings, these methods exist in the new engine and are commonly used in gold standard scripts but have **no current outbound mapping**:

### Player

```
player:getCapacity()          -- replaces getPlayerFreeCap (we map to getFreeCapacity, but getCapacity also exists)
player:getFreeCapacity()      -- confirmed alias
player:getHouse()             -- new in 1.x, no TFS03 equiv
player:isPzLocked()           -- new, useful for scripts
player:isPromoted()           -- new
player:hasGroupFlag(flag)     -- replaces isGod/access checks
player:getGuild():getId()     -- pattern for guild access (instead of getPlayerGuildId)
player:getTown():getId()      -- pattern for town (instead of getPlayerTown returning ID)
player:getVocation():getId()  -- pattern for vocation (instead of getPlayerVocation returning ID)
player:sendExtendedOpcode(opcode, buffer) -- replaces doSendPlayerExtendedOpcode
player:addAchievement(name)   -- new
player:addMount(mountId)      -- new (was not in TFS03)
player:getFamiliarLooktype()  -- new (Pokemon-relevant)
player:setFamiliarLooktype()  -- new
```

### Creature

```
creature:changeSpeed(delta)   -- replaces doChangeSpeed
creature:setSpeed(speed)      -- absolute version, no TFS03 equiv
creature:setMaxHealth(health) -- replaces setCreatureMaxHealth
creature:setHiddenHealth(bool)-- replaces doCreatureSetHideHealth
creature:setMoveLocked(bool)  -- replaces doCreatureSetNoMove
creature:setSkull(type)       -- replaces doCreatureSetSkullType
creature:hasBeenSummoned()    -- cleaner check than isSummon
creature:isInGhostMode()      -- new
creature:isDirectionLocked()  -- new
creature:canSee(pos)          -- new
creature:getZones()           -- new
```

### Item

```
item:isContainer()            -- replaces isContainer(uid)
item:getAttribute(key)        -- same as getItemAttribute but OOP
item:setAttribute(key, val)   -- same as doItemSetAttribute but OOP
item:decay()                  -- replaces doDecayItem
item:transform(newId)         -- replaces doTransformItem
item:remove(count)            -- replaces doRemoveItem
item:moveTo(pos)              -- replaces doMoveCreature for items
```

### Game (global)

```
Game.getSpectators(pos, multiFloor, onlyPlayers, minRangeX, maxRangeX, minRangeY, maxRangeY)
Game.createItem(itemId, count, pos)   -- replaces doCreateItem
Game.createMonster(name, pos)         -- replaces doCreateMonster
Game.getHouses()                      -- replaces getHouseByPlayerGUID pattern
Game.getTowns()                       -- list all towns
```

### Tile

```
Tile(pos):getGround()                 -- replaces getTileInfo .ground
Tile(pos):getItems()                  -- replaces getTileInfo .items
Tile(pos):getCreatures()              -- replaces getTileInfo .creature
Tile(pos):getHouse()                  -- replaces getHouseFromPos
Tile(pos):hasFlag(TILESTATE_...)      -- replaces getTilePzInfo etc
Tile(pos):queryAdd(flags)             -- replaces isWalkable checks
Tile(pos):getItemById(id)             -- replaces getTileItemById
Tile(pos):getItemByType(type)         -- replaces getTileItemByType
```

### Position (new OOP wrapper)

```
pos:isSightClear(pos2)                -- replaces isSightClear(fromPos, toPos)
pos:getDistance(pos2)                 -- replaces getDistanceBetween
pos:getTile()                         -- shortcut to Tile(pos)
```

### Town

```
Town(id):getTemplePosition()          -- replaces getTownTemplePosition
Town(id):getName()
Town(id):getId()
```

---

## 7. Recommended Mapping Additions (Python dict format, ready to paste)

Add to `ttt/mappings/tfs03_functions.py`:

### Section: CREATURE_SETTERS (new dict or add to CREATURE_FUNCTIONS)

```python
CREATURE_SETTERS = {
    "doChangeSpeed": {
        "method": "changeSpeed",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "setCreatureMaxHealth": {
        "method": "setMaxHealth",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCreatureSetHideHealth": {
        "method": "setHiddenHealth",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCreatureSetNoMove": {
        "method": "setMoveLocked",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCreatureSetSkullType": {
        "method": "setSkull",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
    "doCreatureSetLookDirOk": {
        # Custom OK-variant of doCreatureSetLookDir — same mapping
        "method": "setDirection",
        "obj_type": "creature",
        "obj_param": 0,
        "drop_params": [0],
    },
}
```

### Add to PLAYER_GETTERS / PLAYER_SETTERS

```python
# In PLAYER_SETTERS:
"setPlayerStorageValue": {
    # Used 1,226x — alternate naming convention for doPlayerSetStorageValue
    "method": "setStorageValue",
    "obj_type": "player",
    "obj_param": 0,
    "drop_params": [0],
},
```

### Add to MISC_FUNCTIONS (note-only, cannot auto-convert syntax)

```python
"getItemNameById": {
    "note": "-- TTT: Replace with ItemType(itemId):getName()",
},
"getTownTemplePosition": {
    "note": "-- TTT: Replace with Town(townId):getTemplePosition()",
},
"isContainer": {
    "note": "-- TTT: Replace with Item(uid):isContainer()",
},
"isSightClear": {
    "note": "-- TTT: Replace with fromPos:isSightClear(toPos[, sameFloor])",
},
"getHouseFromPos": {
    "note": "-- TTT: Replace with Tile(pos):getHouse()",
},
"isSummon": {
    "note": "-- TTT: Replace with creature:getMaster() ~= nil",
},
"isPlayerSummon": {
    "note": "-- TTT: Replace with (function() local m = creature:getMaster(); return m and m:isPlayer() end)()",
},
"doSendPlayerExtendedOpcode": {
    "note": "-- TTT: Replace with player:sendExtendedOpcode(opcode, buffer)",
},
"getThingPosWithDebug": {
    # Same as getThingPos but with debug logging — treat as alias
    "method": "getPosition",
    "obj_type": "creature",
    "obj_param": 0,
    "drop_params": [0],
    "note": "-- TTT: getThingPosWithDebug treated as getThingPos; remove debug logging if present",
},
```

---

## 8. Patterns Needing Manual Conversion (LLM Prompt Targets)

These patterns are too complex for regex auto-conversion and require LLM-assisted refactoring:

### 8A. Town/Vocation/Guild object unwrapping (202 occurrences total)

```lua
-- BEFORE (after TTT conversion):
local townId = player:getTown()  -- TTT: returns Town object
-- AFTER:
local townId = player:getTown():getId()
```

Also: `player:getVocation():getId()`, `player:getGroup():getId()`, `player:getGuild():getId()`.

### 8B. `getTileInfo` decomposition (37 occurrences)

```lua
-- BEFORE:
local tile = getTileInfo(pos)
if tile.creature then doSomething(tile.creature) end

-- AFTER:
local tile = Tile(pos)
if tile then
    local creature = tile:getTopCreature()
    if creature then doSomething(creature) end
end
```

### 8C. `addEvent` safety (895 calls in largest file alone)

```lua
-- BEFORE (crash risk):
addEvent(myCallback, 300, cid, target)

-- AFTER:
addEvent(function(cid, targetId)
    local creature = Creature(cid)
    if not creature then return end
    local target = Creature(targetId)
    if not target then return end
    myCallback(creature, target)
end, 300, cid, target)
```

### 8D. `isCreature`/`isPlayer` guard migration (987+451 occurrences)

```lua
-- BEFORE:
if not isCreature(cid) then return end

-- AFTER:
local creature = Creature(cid)
if not creature then return end
```

---

## 9. Priority Summary

| Priority | Action                                                                                                                  | Impact                                         |
| -------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| HIGH     | Add `setPlayerStorageValue` mapping                                                                                     | Removes 747 residual calls in converted output |
| HIGH     | Add `doChangeSpeed` → `creature:changeSpeed()`                                                                          | 103 occurrences in originals                   |
| HIGH     | Add creature setter mappings (setMaxHealth, setHiddenHealth, setMoveLocked, setSkull, setSkullType)                     | Reduces unrecognized count                     |
| HIGH     | Fix `doSendAnimatedText` handling (129 TTT marks)                                                                       | Largest single TTT marker volume               |
| MEDIUM   | Add note-only mappings for `getItemNameById`, `getTownTemplePosition`, `isContainer`, `isSightClear`, `getHouseFromPos` | Better guidance on 500+ occurrences            |
| MEDIUM   | Town/Guild/Vocation object unwrapping (12+9+6 TTT marks)                                                                | Already marked, need LLM refactor pass         |
| LOW      | `getTileInfo` decomposition scaffold (37 TTT marks)                                                                     | Complex but low volume                         |
| LOW      | Custom game functions (isWild, isMega, isSummon etc.)                                                                   | Game-specific, need custom lib in target       |
