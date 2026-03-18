export type ApiMethodDoc = {
  method: string;
  detail: string;
  description: string;
};

export type ApiObjectType = "player" | "creature" | "item" | "position" | "game" | "npc";

export const TFS_API: Record<ApiObjectType, ApiMethodDoc[]> = {
  player: [
    { method: "getLevel", detail: "player:getLevel() -> number", description: "Returns player level." },
    { method: "getName", detail: "player:getName() -> string", description: "Returns player name." },
    { method: "getHealth", detail: "player:getHealth() -> number", description: "Returns player health." },
    { method: "addHealth", detail: "player:addHealth(amount)", description: "Adds health to player." },
    { method: "addItem", detail: "player:addItem(itemId, count?) -> Item", description: "Adds an item to player inventory." },
    { method: "removeItem", detail: "player:removeItem(itemId, count?)", description: "Removes item from player inventory." },
    { method: "removeMoney", detail: "player:removeMoney(amount) -> boolean", description: "Tries to remove money from player." },
    { method: "addMoney", detail: "player:addMoney(amount)", description: "Adds money to player." },
    { method: "say", detail: "player:say(text, type)", description: "Makes player say a message." },
    { method: "sendTextMessage", detail: "player:sendTextMessage(type, text)", description: "Sends a text message to the player." },
    { method: "sendCancelMessage", detail: "player:sendCancelMessage(text)", description: "Sends a cancel message to the player." },
    { method: "isPremium", detail: "player:isPremium() -> boolean", description: "Returns whether player has premium account." },
    { method: "teleportTo", detail: "player:teleportTo(position)", description: "Teleports the player to a position." },
    { method: "getPosition", detail: "player:getPosition() -> Position", description: "Returns the player position." },
    { method: "getStorageValue", detail: "player:getStorageValue(key) -> number", description: "Reads a storage value." },
    { method: "setStorageValue", detail: "player:setStorageValue(key, value)", description: "Writes a storage value." },
    { method: "registerEvent", detail: "player:registerEvent(name)", description: "Registers a creature event for the player." },
    { method: "addExperience", detail: "player:addExperience(amount)", description: "Adds experience to player." },
    { method: "getVocation", detail: "player:getVocation() -> Vocation", description: "Returns player vocation." }
  ],
  creature: [
    { method: "getName", detail: "creature:getName() -> string", description: "Returns creature name." },
    { method: "getHealth", detail: "creature:getHealth() -> number", description: "Returns creature current health." },
    { method: "addHealth", detail: "creature:addHealth(amount)", description: "Adds health to creature." },
    { method: "getPosition", detail: "creature:getPosition() -> Position", description: "Returns creature position." },
    { method: "teleportTo", detail: "creature:teleportTo(position)", description: "Teleports creature to position." },
    { method: "say", detail: "creature:say(text, type)", description: "Makes creature say a message." }
  ],
  item: [
    { method: "getId", detail: "item:getId() -> number", description: "Returns item id." },
    { method: "getCount", detail: "item:getCount() -> number", description: "Returns stack count." },
    { method: "remove", detail: "item:remove(count?)", description: "Removes item or reduces stack count." },
    { method: "transform", detail: "item:transform(itemId)", description: "Transforms item into another id." },
    { method: "getPosition", detail: "item:getPosition() -> Position", description: "Returns item position." }
  ],
  position: [
    { method: "sendMagicEffect", detail: "position:sendMagicEffect(effect)", description: "Sends a magic effect at this position." },
    { method: "sendDistanceEffect", detail: "position:sendDistanceEffect(toPosition, effect)", description: "Sends a projectile effect." },
    { method: "isSightClear", detail: "position:isSightClear(toPosition) -> boolean", description: "Checks line of sight to another position." }
  ],
  game: [
    { method: "broadcastMessage", detail: "Game.broadcastMessage(text, type?)", description: "Broadcasts a message to all players." },
    { method: "createItem", detail: "Game.createItem(itemId, count?, position?)", description: "Creates an item in game world." },
    { method: "getPlayers", detail: "Game.getPlayers() -> Player[]", description: "Returns all players online." },
    { method: "getSpectators", detail: "Game.getSpectators(position, ...)", description: "Returns creatures around a position." },
    { method: "setStorageValue", detail: "Game.setStorageValue(key, value)", description: "Sets global game storage value." },
    { method: "getStorageValue", detail: "Game.getStorageValue(key) -> number", description: "Gets global game storage value." }
  ],
  npc: [
    { method: "getName", detail: "Npc():getName() -> string", description: "Returns NPC name." },
    { method: "say", detail: "Npc():say(text)", description: "Makes NPC say a message." },
    { method: "move", detail: "Npc():move(direction)", description: "Moves NPC in a direction." }
  ]
};

export function findMethodDoc(objectType: string, method: string): ApiMethodDoc | undefined {
  const entries = TFS_API[objectType.toLowerCase() as ApiObjectType];
  if (!entries) {
    return undefined;
  }
  return entries.find((m) => m.method === method);
}

export function getMethodsForType(objectType: string): ApiMethodDoc[] {
  return TFS_API[objectType.toLowerCase() as ApiObjectType] ?? [];
}

export function getAllMethods(): ApiMethodDoc[] {
  const dedup = new Map<string, ApiMethodDoc>();
  for (const methods of Object.values(TFS_API)) {
    for (const method of methods) {
      if (!dedup.has(method.method)) {
        dedup.set(method.method, method);
      }
    }
  }
  return [...dedup.values()];
}
