# Npcs

2 entries

| Name | Script | Keywords | Description |
|------|--------|------|-------------|
| Captain | captain.lua | travel, name | Hello \|PLAYERNAME\|! Do you want to {travel}? |
| Shopkeeper Tom | shopkeeper.lua | balance, level, help | Welcome, \|PLAYERNAME\|! I buy and sell equipment. |

### Captain

- **look_type:** 128
- **health:** 100
- **greet:** Hello \|PLAYERNAME\|! Do you want to {travel}?
- **keywords:** travel, name

```lua
-- TFS 0.3 NPC Script: Captain (Travel NPC)
-- Typical travel NPC using NpcHandler module

local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Hello |PLAYERNAME|! Do you want to {travel}?")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end

    if msgcontains(msg, "travel") then
        if getPlayerLevel(cid) < 20 then
            selfSay("You need level 20 to travel.", cid)
            return true
        end

        if not isPremium(cid) then
            selfSay("You need a premium account to travel.", cid)
            return true
        end

        local price = 100
        if doPlayerRemoveMoney(cid, price) then
            doTeleportThing(cid, {x=1000, y=1000, z=7})
            doSendMagicEffect(getCreaturePosition(cid), CONST_ME_TELEPORT)
            selfSay("Here we go!", cid)
        else
            selfSay("You don't have " .. price .. " gold.", cid)
        end
    end

    if msgcontains(msg, "name") then
        selfSay("My name is " .. getNpcName() .. ".", cid)
    end

    return true
end

npcHandler:addModule(FocusModule:new())
```

### Shopkeeper Tom

- **look_type:** 130
- **health:** 100
- **greet:** Welcome, \|PLAYERNAME\|! I buy and sell equipment.
- **keywords:** balance, level, help
- **shop_buyable:** 2400,sword,100;2383,spear,50
- **shop_sellable:** 2400,sword,50;2383,spear,25

```lua
-- TFS 0.3 NPC Script: Shopkeeper Tom
-- Equipment shop NPC using NpcHandler + ShopModule

local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:setMessage(MESSAGE_GREET, "Welcome, |PLAYERNAME|! I buy and sell equipment.")

function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end

    if msgcontains(msg, "balance") then
        local balance = getPlayerBalance(cid)
        selfSay("Your bank balance is " .. balance .. " gold.", cid)
        return true
    end

    if msgcontains(msg, "level") then
        local level = getPlayerLevel(cid)
        selfSay("You are level " .. level .. ".", cid)
        return true
    end

    if msgcontains(msg, "help") then
        local name = getCreatureName(cid)
        doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "Hello " .. name .. "! Say 'trade' to open my shop.")
        return true
    end

    return true
end

npcHandler:addModule(FocusModule:new())
npcHandler:addModule(ShopModule:new())
```
