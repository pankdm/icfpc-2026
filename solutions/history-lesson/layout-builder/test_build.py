#!/usr/bin/env python3
"""Structural checks for the pipe-free History Lesson layout builder."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("history_layout_builder", HERE / "build.py")
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


class LayoutBuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.program, cls.metadata = builder.build()

    def test_current_candidate_defaults(self):
        dictionary = self.metadata["dictionary"]
        self.assertEqual(self.metadata["feeder_width"], 81)
        self.assertEqual(dictionary["width"], 52)
        self.assertEqual(dictionary["words"], 44)

    def test_dictionary_is_left_aligned(self):
        dictionary = self.metadata["dictionary"]
        self.assertEqual(dictionary["left_edge"], 0)

    def test_dp_packs_every_constant(self):
        dictionary = self.metadata["dictionary"]
        self.assertEqual(sum(dictionary["constants_per_band"]), 44)
        self.assertEqual(dictionary["bands"], 8)
        # The DP's first tie-break fills earlier bands as much as the fixed
        # width permits.
        self.assertEqual(dictionary["constants_per_band"][:2], [10, 8])

    def test_service_rooms_are_stacked_on_the_right(self):
        rooms = self.metadata["service_rooms"]
        for upper, lower in zip(rooms, rooms[1:]):
            self.assertEqual(
                lower[2], upper[2] + upper[4] + builder.ROOM_GAP
            )
        for _, x, _, width, _ in rooms:
            self.assertEqual(x + width, self.metadata["feeder_width"])

    def test_no_pipes_are_declared(self):
        self.assertEqual(self.metadata["pipes"], 0)

    def test_buffer_loop_follows_all_constant_bands(self):
        dictionary = self.metadata["dictionary"]
        x = dictionary["x"]
        bottom = dictionary["y"] + dictionary["height"] - 1
        self.assertEqual(
            "".join(self.program.get(x + dx, bottom - 2) for dx in range(1, 6)),
            ">>rsv",
        )
        self.assertEqual(
            "".join(self.program.get(x + dx, bottom - 1) for dx in range(1, 6)),
            " ^<<<",
        )


if __name__ == "__main__":
    unittest.main()
