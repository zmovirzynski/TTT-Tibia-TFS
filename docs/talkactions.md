# Talkactions

1 entries

| Name | Script | Words | Description |
|------|--------|------|-------------|
| /bc | broadcast.lua | /bc | TFS 0.3 TalkAction: Broadcast command |

### /bc

- **words:** /bc
- **access:** 3

```lua
-- TFS 0.3 TalkAction: Broadcast command
-- Admin command example

function onSay(cid, words, param)
    if getPlayerGroupId(cid) < 3 then
        doPlayerSendCancel(cid, "You do not have permission to use this command.")
        return TRUE
    end

    if param == "" then
        doPlayerSendCancel(cid, "Usage: /bc message")
        return TRUE
    end

    broadcastMessage(param, MESSAGE_STATUS_WARNING)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_CONSOLE_BLUE, "Broadcast sent: " .. param)

    return TRUE
end
```
