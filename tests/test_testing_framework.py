"""Tests for TTT Test Framework (Phase 9)."""

import os
import tempfile
import textwrap
import unittest

from ttt.testing import (
    mockPlayer,
    mockCreature,
    mockItem,
    mockPosition,
    assertPlayerHasLevel,
    assertCreatureAlive,
    assertItemCount,
    assertPositionEqual,
    assertMessageSent,
    run_tests,
    format_test_report,
)


class TestMockApi(unittest.TestCase):
    def test_mock_player_and_inventory(self):
        player = mockPlayer(name="Tom", level=42, money=100)
        item = player.addItem(2160, 2)

        self.assertEqual(player.getName(), "Tom")
        self.assertEqual(player.getLevel(), 42)
        self.assertEqual(item.count, 2)
        self.assertEqual(len(player.inventory), 1)

    def test_mock_creature_and_position(self):
        creature = mockCreature(name="Rat", health=35)
        dest = mockPosition(200, 300, 7)

        self.assertTrue(creature.isAlive())
        creature.teleportTo(dest)
        self.assertEqual(creature.getPosition(), dest)

    def test_mock_item_remove(self):
        item = mockItem(7618, count=3)
        item.remove(1)
        self.assertEqual(item.count, 2)

        item.remove(2)
        self.assertEqual(item.count, 0)
        self.assertTrue(item.removed)


class TestCustomAssertions(unittest.TestCase):
    def test_assertions_pass(self):
        player = mockPlayer(level=20)
        creature = mockCreature(health=100)
        item = mockItem(2148, count=10)
        pos = mockPosition(100, 100, 7)

        player.sendTextMessage(19, "hello world")

        assertPlayerHasLevel(player, 10)
        assertCreatureAlive(creature)
        assertItemCount(item, 10)
        assertPositionEqual(pos, mockPosition(100, 100, 7))
        assertMessageSent(player, "hello")

    def test_assertions_fail(self):
        player = mockPlayer(level=1)
        with self.assertRaises(AssertionError):
            assertPlayerHasLevel(player, 10)

        dead = mockCreature(health=0)
        with self.assertRaises(AssertionError):
            assertCreatureAlive(dead)


class TestRunner(unittest.TestCase):
    def test_run_tests_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test_sample.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(
                    textwrap.dedent("""\
                    import unittest

                    class TestSample(unittest.TestCase):
                        def test_ok(self):
                            self.assertTrue(True)
                """)
                )

            report = run_tests(tmp)
            self.assertEqual(report.tests_run, 1)
            self.assertTrue(report.successful)
            self.assertEqual(report.return_code, 0)

            text = format_test_report(report)
            self.assertIn("TTT Test Report", text)
            self.assertIn("Status:", text)

    def test_run_tests_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test_fail.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(
                    textwrap.dedent("""\
                    import unittest

                    class TestFail(unittest.TestCase):
                        def test_nope(self):
                            self.assertEqual(1, 2)
                """)
                )

            report = run_tests(test_file)
            self.assertEqual(report.tests_run, 1)
            self.assertFalse(report.successful)
            self.assertEqual(report.return_code, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
