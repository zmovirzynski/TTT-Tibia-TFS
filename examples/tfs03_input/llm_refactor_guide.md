# LLM Refactoring Guide

Generated: 2026-04-01  
Conversion: TFS 0.3.6 → TFS 1.3+ (RevScript)  
Files analyzed: 8  
Files needing attention: 7  
Lua OOP issues: 16  
TTT review markers: 7  
Unrecognized calls: 0

---

## `npc\scripts\captain.lua`  (42 lines)

**Priority: MEDIUM** · Confidence: MEDIUM · 5 TTT marker(s)

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 3 old-style procedural call(s) (3 unique): 1 on Creature, 2 on Player. Sample: `doPlayerRemoveMoney`, `getCreaturePosition`, `getPlayerLevel`.
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

- 5 line(s) marked with `-- TTT:` require manual review.

### Suggested LLM prompt

> Refactor `npc\scripts\captain.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls. Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## `npc\scripts\shopkeeper.lua`  (36 lines)

**Priority: MEDIUM** · Confidence: MEDIUM · 2 TTT marker(s)

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 4 old-style procedural call(s) (4 unique): 1 on Creature, 3 on Player. Sample: `doPlayerSendTextMessage`, `getCreatureName`, `getPlayerBalance`, `getPlayerLevel`.
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

- 2 line(s) marked with `-- TTT:` require manual review.

### Suggested LLM prompt

> Refactor `npc\scripts\shopkeeper.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls. Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## `actions\scripts\teleport_scroll.lua`  (33 lines)

**Priority: MEDIUM** · Confidence: HIGH

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 8 old-style procedural call(s) (7 unique): 2 on Creature, 5 on Player. Sample: `doCreatureSay`, `doPlayerSendCancel`, `doPlayerSendTextMessage`, `doPlayerSetStorageValue`, `getCreaturePosition`, `getPlayerPosition` (+1 more).
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

**3. Storage key table**
- 1 storage key table(s) with 2 total key(s): `destination` (2 keys).
- Guideline: `getPlayerStorageValue(cid, TABLE.key)` → `player:getStorageValue(TABLE.key)`. `setPlayerStorageValue(cid, TABLE.key, val)` → `player:setStorageValue(TABLE.key, val)`. The table structure itself can stay unchanged.

### Suggested LLM prompt

> Refactor `actions\scripts\teleport_scroll.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls; Storage key table. Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## `movements\scripts\leveldoor.lua`  (21 lines)

**Priority: MEDIUM** · Confidence: HIGH

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 3 old-style procedural call(s) (3 unique): 3 on Player. Sample: `doPlayerSendCancel`, `doPlayerSendTextMessage`, `getPlayerLevel`.
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

**3. Nil guard migration (isCreature/isPlayer)**
- 1 `isCreature`/`isPlayer` guard(s) on variable(s) `cid` need migration to OOP nil checks.
- Guideline: After creating the OOP object (`local player = Player(cid)`), replace `if not isCreature(cid) then return end` with `if not player then return end`. For creatures: `local creature = Creature(cid); if not creature then return end`.

### Suggested LLM prompt

> Refactor `movements\scripts\leveldoor.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls; Nil guard migration (isCreature/isPlayer). Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## `actions\scripts\healing_potion.lua`  (26 lines)

**Priority: MEDIUM** · Confidence: HIGH

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 9 old-style procedural call(s) (7 unique): 4 on Creature, 3 on Player. Sample: `doCreatureAddHealth`, `doPlayerSendCancel`, `doPlayerSendTextMessage`, `getCreatureHealth`, `getCreatureMaxHealth`, `getCreaturePosition` (+1 more).
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

### Suggested LLM prompt

> Refactor `actions\scripts\healing_potion.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls. Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## `talkactions\scripts\broadcast.lua`  (19 lines)

**Priority: MEDIUM** · Confidence: HIGH

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 4 old-style procedural call(s) (3 unique): 3 on Player. Sample: `doPlayerSendCancel`, `doPlayerSendTextMessage`, `getPlayerGroupId`.
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

### Suggested LLM prompt

> Refactor `talkactions\scripts\broadcast.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls. Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## `creaturescripts\scripts\login.lua`  (28 lines)

**Priority: MEDIUM** · Confidence: HIGH

### Lua OOP Issues

**1. Player/cid → OOP object**
- 1 function(s) receive `cid` as a player/creature identifier instead of an OOP object.
- Guideline: At the top of each function add `local player = Player(cid)` and guard with `if not player then return end`. Replace all `doPlayerXxx(cid, ...)` / `getPlayerXxx(cid, ...)` calls with `player:xxx(...)` method calls.

**2. Old procedural API calls**
- 8 old-style procedural call(s) (5 unique): 1 on Creature, 4 on Player. Sample: `doPlayerSendTextMessage`, `doPlayerSetStorageValue`, `getCreatureName`, `getPlayerLevel`, `getPlayerPremiumDays`.
- Guideline: Cache each entity object once per function: `local player = Player(cid)`, `local item = Item(uid)`, `local target = Creature(targetId)`. Then use OOP methods: `player:getLevel()` instead of `getPlayerLevel(cid)`, `player:sendTextMessage(...)` instead of `doPlayerSendTextMessage(cid, ...)`. Each entity needs its own local variable.

### Suggested LLM prompt

> Refactor `creaturescripts\scripts\login.lua` for TFS 1.x/RevScript OOP style: Player/cid → OOP object; Old procedural API calls. Cache entity objects as locals, use method calls instead of global functions, and handle nil player guards.

---

## Clean files

No issues detected in:

- `globalevents\scripts\startup.lua` (9 lines · confidence: HIGH)
