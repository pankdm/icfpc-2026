import tempfile
import unittest
from pathlib import Path

import fetch_best_submissions as fetcher


class SelectionTests(unittest.TestCase):
    def test_prefers_correctness_then_lowest_score(self):
        rows = [
            {
                "id": "partial-fast",
                "problemName": "A",
                "status": "done",
                "casesPassed": 4,
                "casesTotal": 5,
                "score": 1,
            },
            {
                "id": "complete-slow",
                "problemName": "A",
                "status": "done",
                "casesPassed": 5,
                "casesTotal": 5,
                "score": "200",
            },
            {
                "id": "complete-fast",
                "problemName": "A",
                "status": "done",
                "casesPassed": 5,
                "casesTotal": 5,
                "score": "100",
            },
        ]
        self.assertEqual(fetcher.select_best(rows)["A"]["id"], "complete-fast")

    def test_ignores_pending_and_zero_score_rows(self):
        rows = [
            {
                "id": "pending",
                "problemName": "A",
                "status": "pending",
                "casesPassed": 5,
                "casesTotal": 5,
                "score": 1,
            },
            {
                "id": "invalid",
                "problemName": "A",
                "status": "done",
                "casesPassed": 5,
                "casesTotal": 5,
                "score": 0,
            },
        ]
        self.assertEqual(fetcher.select_best(rows), {})


class ProgramTests(unittest.TestCase):
    def test_dimensions_use_non_space_bounding_box(self):
        self.assertEqual(fetcher.dimensions("\n  +-+  \n  |@|  \n  +-+  \n\n"), (3, 3))

    def test_decode_preserves_missing_final_newline(self):
        row = {"id": "x", "width": 3, "height": 3}
        text = fetcher.decode_program(b"+-+\n|@|\n+-+", row)
        self.assertFalse(text.endswith("\n"))

    def test_decode_rejects_dimension_mismatch(self):
        row = {"id": "x", "width": 4, "height": 3}
        with self.assertRaises(fetcher.FetchError):
            fetcher.decode_program(b"+-+\n|@|\n+-+\n", row)

    def test_replace_directory_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            output = parent / "best"
            output.mkdir()
            (output / "stale.man").write_text("old")
            staged = parent / "stage"
            staged.mkdir()
            (staged / "fresh.man").write_text("new")
            fetcher.replace_directory(staged, output)
            self.assertEqual((output / "fresh.man").read_text(), "new")
            self.assertFalse((output / "stale.man").exists())
            self.assertFalse((parent / "best.previous").exists())

    def test_compact_score_matches_dashboard_style(self):
        self.assertEqual(fetcher.compact_score(832), "832")
        self.assertEqual(fetcher.compact_score(6_400), "6.40K")
        self.assertEqual(fetcher.compact_score(262_915), "263K")
        self.assertEqual(fetcher.compact_score(20_569_275), "20.6M")
        self.assertEqual(fetcher.compact_score(16_192_622_871), "16.2B")
        self.assertEqual(fetcher.compact_score(2_798_366_124_328), "2.80T")


if __name__ == "__main__":
    unittest.main()
