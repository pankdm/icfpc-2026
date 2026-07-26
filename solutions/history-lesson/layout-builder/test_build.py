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
            [9, 9, 6, 6, 6, 8],
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
        narrow = builder.pack_dictionary(values, 18)
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

    def test_buffer_loop_follows_all_constant_bands(self):
        dictionary = self.metadata["dictionary"]
        x = dictionary["x"]
        bottom = dictionary["y"] + dictionary["height"] - 1
        self.assertEqual(
            "".join(self.program.get(x + dx, bottom - 3) for dx in range(1, 5)),
            "vs0s",
        )
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
