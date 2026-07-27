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
        self.assertEqual(dictionary["width"], 38)
        self.assertEqual(dictionary["requested_words"], 24)
        self.assertEqual(dictionary["words"], 24)

    def test_dictionary_is_left_aligned(self):
        dictionary = self.metadata["dictionary"]
        self.assertEqual(dictionary["left_edge"], 0)

    def test_dp_packs_every_constant(self):
        dictionary = self.metadata["dictionary"]
        self.assertEqual(sum(dictionary["constants_per_band"]), 24)
        self.assertEqual(dictionary["bands"], 4)
        self.assertEqual(dictionary["height"], 10)
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
        wide = builder.pack_dictionary(values, 31)
        self.assertGreater(len(narrow), len(wide))
        self.assertNotEqual(
            [len(band.widths) for band in narrow],
            [len(band.widths) for band in wide],
        )

    def test_raw_dictionary_supports_smaller_budgets(self):
        data = builder.vertical.base.TEXT
        for words in (17, 18, 24, 37):
            symbols, ring, metadata = builder.raw_dictionary.build_encoding(
                data,
                words,
            )
            self.assertTrue(symbols)
            self.assertEqual(len(ring), words)
            self.assertEqual(metadata["catalog"]["minimum_words"], 17)

    def test_budget_17_does_not_displace_apostrophe(self):
        _, ring17, _ = builder.raw_dictionary.build_encoding(
            builder.vertical.base.TEXT,
            17,
        )
        _, ring18, metadata18 = builder.raw_dictionary.build_encoding(
            builder.vertical.base.TEXT,
            18,
        )
        self.assertEqual(ring17[8], builder.raw_dictionary.pack128(b"'"))
        self.assertNotEqual(ring18[8], builder.raw_dictionary.pack128(b"'"))
        self.assertIn("'", metadata18["words"].values())

    def test_order_search_can_be_skipped(self):
        symbols, ring, _ = builder.raw_dictionary.build_encoding(
            builder.vertical.base.TEXT,
            24,
        )
        _, reordered_ring, order, bands = builder.repack_physical_dictionary(
            symbols,
            ring,
            38,
            search_order=False,
        )
        self.assertEqual(order, list(range(1, 25)))
        self.assertEqual(reordered_ring, ring)
        self.assertTrue(bands)

    def test_compact_alphabet_uses_base64_codes_and_round_trips(self):
        catalog = builder.raw_dictionary.load_catalog(
            str(HERE / "dictionary_words_layout_gain.json")
        )
        symbols, _, _ = builder.raw_dictionary.build_encoding(
            builder.vertical.base.TEXT,
            52,
            catalog,
        )
        codes, metadata = builder.compact_alphabet(symbols)
        self.assertEqual(metadata["base"], 64)
        self.assertEqual(metadata["source_symbols"], len(symbols))
        self.assertEqual(metadata["encoded_codes"], len(codes))
        self.assertEqual(len(codes), 2160)
        self.assertTrue(all(1 <= code <= 63 for code in codes))

    def test_folded_dictionary_exactly_fits_55_by_16(self):
        catalog = builder.raw_dictionary.load_catalog(
            str(HERE / "dictionary_words_layout_gain.json")
        )
        symbols, ring, _ = builder.raw_dictionary.build_encoding(
            builder.vertical.base.TEXT,
            52,
            catalog,
        )
        rewritten, packed_ring, order, bands = (
            builder.repack_physical_dictionary(
                symbols,
                ring,
                55,
                preload_bp2=True,
            )
        )
        self.assertEqual(len(order), 52)
        self.assertEqual(len(bands), 7)
        usage = builder.dictionary_usage(rewritten, packed_ring)
        self.assertEqual(usage[16], (17, "0", 40))

    def test_catalog_is_unique_and_residual_occurrence_ordered(self):
        catalog = builder.raw_dictionary.load_catalog()
        phrases = [
            action
            for action in catalog["actions"]
            if "occurrences_at_selection" in action
        ]
        occurrences = [
            action["occurrences_at_selection"]
            for action in phrases
        ]
        self.assertEqual(occurrences, sorted(occurrences, reverse=True))
        words = [action["word"] for action in catalog["actions"]]
        self.assertEqual(len(words), len(set(words)))

        _, _, metadata = builder.raw_dictionary.build_encoding(
            builder.vertical.base.TEXT,
            60,
        )
        usa = next(
            action
            for action in phrases
            if action["word"] == "USA"
        )
        self.assertEqual(usa["slot"], 20)
        self.assertEqual(metadata["references"][usa["slot"]], 11)

    def test_tail_rooms_form_one_row_with_dispatcher_input_gap(self):
        dictionary = self.metadata["dictionary"]
        rooms = self.metadata["service_rooms"]
        self.assertEqual(rooms[0][1], dictionary["x"] + dictionary["width"])
        self.assertTrue(all(room[2] == dictionary["y"] for room in rooms))
        for index, (left, right) in enumerate(zip(rooms, rooms[1:])):
            gap = 2 if index == len(rooms) - 2 else 0
            self.assertEqual(right[1], left[1] + left[3] + gap)

    def test_uses_compact_vertical_p2_dispatcher(self):
        name, x, y, width, height = self.metadata["service_rooms"][-1]
        self.assertEqual(name, "dispatcher")
        self.assertEqual((width, height), (23, 7))
        self.assertEqual(builder.DISP_RING_IN[1], height)
        self.assertEqual(builder.DISP_RING_OUT[1], height)
        for row_offset, expected in enumerate(builder.compact.DISP_ROWS, start=1):
            actual = "".join(
                self.program.get(x + column, y + row_offset)
                for column in range(1, width - 1)
            )
            self.assertEqual(actual, expected)

    def test_only_referenced_dictionary_words_are_physically_placed(self):
        usage = self.metadata["dictionary"]["usage"]
        self.assertEqual(len(usage), 24)
        self.assertTrue(all(entry["references"] > 0 for entry in usage))
        zero_entries = [entry for entry in usage if entry["word"] == "0"]
        self.assertEqual(len(zero_entries), 1)
        self.assertEqual(zero_entries[0]["references"], 40)

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
            self.program.get(x + builder.LATER_START_COLUMN, y + 3),
            "x",
        )
        self.assertEqual(
            self.program.get(x + builder.LATER_START_COLUMN, y + 4),
            "v",
        )
        final_bottom = y + 2 * dictionary["bands"]
        for return_y in range(y + 3, final_bottom):
            self.assertEqual(
                self.program.get(x + builder.RETURN_COLUMN, return_y),
                " ",
            )
        self.assertEqual(
            self.program.get(x + builder.RETURN_COLUMN, final_bottom),
            "^",
        )
        self.assertEqual(
            self.program.get(x + 5, final_bottom),
            "s",
        )
        self.assertEqual(
            self.program.get(x + 6, final_bottom),
            "0",
        )
        self.assertEqual(self.program.get(x + 4, final_bottom), "1")
        self.assertEqual(self.program.get(x + 3, final_bottom), "b")


if __name__ == "__main__":
    unittest.main()
