# Global Events

1 entries

| Name | Script | Type | Description |
|------|--------|------|-------------|
| ServerStart | startup.lua | start | TFS 0.3 GlobalEvent: Server Startup |

### ServerStart

- **name:** ServerStart
- **type:** start

```lua
-- TFS 0.3 GlobalEvent: Server Startup
-- Runs when server starts

function onStartup()
    broadcastMessage("Server is now online!", MESSAGE_STATUS_WARNING)
    setGlobalStorageValue(50001, os.time())
    print("[ServerStart] Server initialized at " .. os.date())
    return TRUE
end
```
