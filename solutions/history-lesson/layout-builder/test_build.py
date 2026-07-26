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
        self.assertEqual(dictionary["bands"], 6)
        self.assertEqual(
            dictionary["constants_per_band"],
            [8, 12, 6, 6, 6, 6],
        )
        self.assertEqual(
            len(dictionary["slots_per_band"]),
            dictionary["bands"],
        )

    def test_dp_changes_layout_with_available_width(self):
        values = [
            1,
            22,
            333,
            4444,
            55555,
            666666,
            7777777,
            88888888,
        ]
        narrow = builder.pack_dictionary(values, 24)
        wide = builder.pack_dictionary(values, 30)
        self.assertGreater(len(narrow), len(wide))
        self.assertNotEqual(
            [len(band.widths) for band in narrow],
            [len(band.widths) for band in wide],
        )

    def test_all_tail_rooms_form_one_touching_row(self):
        dictionary = self.metadata["dictionary"]
        rooms = self.metadata["service_rooms"]
        self.assertEqual(rooms[0][1], dictionary["x"] + dictionary["width"])
        self.assertTrue(all(room[2] == dictionary["y"] for room in rooms))
        for left, right in zip(rooms, rooms[1:]):
            self.assertEqual(right[1], left[1] + left[3])

    def test_tail_touches_feeder_bottom(self):
        dictionary = self.metadata["dictionary"]
        feeder_bottom = self.metadata["feeder_rows"] + 1
        self.assertEqual(dictionary["y"], feeder_bottom + 1)

    def test_no_pipes_are_declared(self):
        self.assertEqual(self.metadata["pipes"], 0)
        self.assertFalse(self.metadata["connected"])

    def test_top_left_pump_and_return_follow_all_constant_bands(self):
        dictionary = self.metadata["dictionary"]
        x = dictionary["x"]
        y = dictionary["y"]
        bottom = dictionary["y"] + dictionary["height"] - 1
        actual = tuple(
            "".join(
                self.program.get(x + dx, y)
                for dx in range(1, builder.TOP_LEFT_BLOCK_WIDTH + 1)
            )
            for y in range(y + 1, y + 3)
        )
        self.assertEqual(actual, builder.TOP_LEFT_BLOCK_ROWS)
        self.assertEqual(
            self.program.get(x + builder.START_COLUMN, y + 1),
            "@",
        )
        self.assertEqual(
            self.program.get(x + builder.START_COLUMN, y + 3),
            "<",
        )
        self.assertEqual(
            self.program.get(x + builder.LATER_START_COLUMN, y + 3),
            "v",
        )
        self.assertEqual(
            self.program.get(x + builder.LATER_START_COLUMN, y + 4),
            ">",
        )
        for return_y in range(y + 2, bottom):
            self.assertEqual(
                self.program.get(x + builder.RETURN_COLUMN, return_y),
                "^",
            )
        self.assertEqual(
            self.program.get(x + 2, bottom - 1),
            "s",
        )
        self.assertEqual(
            self.program.get(x + 3, bottom - 1),
            "0",
        )


if __name__ == "__main__":
    unittest.main()
