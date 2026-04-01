"""Mocks para APIs comuns do TFS (Player, Creature, Item, Position)."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(eq=True, frozen=True)
class MockPosition:
    """Mock simples de Position(x, y, z)."""

    x: int
    y: int
    z: int

    def sendMagicEffect(self, effect_id: int) -> int:
        return effect_id


@dataclass
class MockItem:
    """Mock de item com contagem e uid."""

    item_id: int
    count: int = 1
    uid: int = 0
    removed: bool = False

    _uid_counter: int = 1000

    def __post_init__(self):
        if not self.uid:
            MockItem._uid_counter += 1
            self.uid = MockItem._uid_counter

    def remove(self, amount: int = 1) -> bool:
        if amount <= 0:
            return True
        if amount >= self.count:
            self.count = 0
            self.removed = True
            return True
        self.count -= amount
        return True


@dataclass
class MockCreature:
    """Mock base para entidades vivas."""

    name: str = "Creature"
    health: int = 100
    position: MockPosition = field(default_factory=lambda: MockPosition(100, 100, 7))
    storage: Dict[int, int] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)

    def getName(self) -> str:
        return self.name

    def getHealth(self) -> int:
        return self.health

    def addHealth(self, amount: int) -> int:
        self.health += amount
        return self.health

    def isAlive(self) -> bool:
        return self.health > 0

    def getPosition(self) -> MockPosition:
        return self.position

    def teleportTo(self, position: MockPosition) -> bool:
        self.position = position
        return True

    def setStorageValue(self, key: int, value: int) -> bool:
        self.storage[int(key)] = int(value)
        return True

    def getStorageValue(self, key: int) -> int:
        return self.storage.get(int(key), -1)

    def say(self, message: str) -> bool:
        self.messages.append(message)
        return True


@dataclass
class MockPlayer(MockCreature):
    """Mock de Player com inventário, dinheiro e mensagens."""

    name: str = "Player"
    level: int = 1
    health: int = 100
    money: int = 0
    premium: bool = False
    inventory: List[MockItem] = field(default_factory=list)
    registered_events: List[str] = field(default_factory=list)

    def getLevel(self) -> int:
        return self.level

    def addItem(self, item_id: int, count: int = 1) -> MockItem:
        item = MockItem(item_id=item_id, count=count)
        self.inventory.append(item)
        return item

    def sendTextMessage(self, _msg_type: int, text: str) -> bool:
        self.messages.append(text)
        return True

    def sendCancelMessage(self, text: str) -> bool:
        self.messages.append(text)
        return True

    def removeMoney(self, amount: int) -> bool:
        if amount <= self.money:
            self.money -= amount
            return True
        return False

    def addMoney(self, amount: int) -> bool:
        self.money += amount
        return True

    def registerEvent(self, event_name: str) -> bool:
        self.registered_events.append(event_name)
        return True

    def isPremium(self) -> bool:
        return self.premium


def mockPlayer(
    name: str = "Player",
    level: int = 1,
    health: int = 100,
    money: int = 0,
    premium: bool = False,
    position: Optional[MockPosition] = None,
    **_kwargs,
) -> MockPlayer:
    """Factory helper for mock Player."""
    return MockPlayer(
        name=name,
        level=level,
        health=health,
        money=money,
        premium=premium,
        position=position or MockPosition(100, 100, 7),
    )


def mockCreature(
    name: str = "Creature",
    health: int = 100,
    position: Optional[MockPosition] = None,
    **_kwargs,
) -> MockCreature:
    """Factory helper for mock Creature."""
    return MockCreature(
        name=name, health=health, position=position or MockPosition(100, 100, 7)
    )


def mockItem(item_id: int, count: int = 1, uid: int = 0, **_kwargs) -> MockItem:
    """Factory helper for mock Item."""
    return MockItem(item_id=item_id, count=count, uid=uid)


def mockPosition(x: int, y: int, z: int, **_kwargs) -> MockPosition:
    """Factory helper for mock Position."""
    return MockPosition(x=x, y=y, z=z)
