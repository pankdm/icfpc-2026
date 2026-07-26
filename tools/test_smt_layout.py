import unittest

import smt_layout


class SmtLayoutTest(unittest.TestCase):
    def test_rotates_and_packs_hot_components(self):
        spec = {
            "gap": 1,
            "components": [
                {"name": "controller", "w": 8, "h": 3},
                {"name": "display", "w": 2, "h": 5, "rotate": True},
                {"name": "ram", "w": 4, "h": 4},
            ],
            "edges": [
                {"a": "controller", "b": "display", "weight": 20},
                {"a": "controller", "b": "ram", "weight": 5},
            ],
        }
        result = smt_layout.solve(spec)
        self.assertLessEqual(result["max_dim"], 10)
        self.assertEqual({c["name"] for c in result["components"]},
                         {"controller", "display", "ram"})
        for i, a in enumerate(result["components"]):
            for b in result["components"][i + 1:]:
                separated = (
                    a["x"] + a["w"] + 1 <= b["x"]
                    or b["x"] + b["w"] + 1 <= a["x"]
                    or a["y"] + a["h"] + 1 <= b["y"]
                    or b["y"] + b["h"] + 1 <= a["y"]
                )
                self.assertTrue(separated, (a, b))

    def test_honors_order_and_length_bound(self):
        spec = {
            "components": [
                {"name": "a", "w": 3, "h": 3},
                {"name": "b", "w": 3, "h": 3},
            ],
            "left_of": [["a", "b"]],
            "edges": [{
                "a": "a",
                "b": "b",
                "a_port": {"x": 3, "y": 1},
                "b_port": {"x": -1, "y": 1},
                "max_length": 1,
            }],
        }
        result = smt_layout.solve(spec)
        by_name = {c["name"]: c for c in result["components"]}
        self.assertLessEqual(by_name["a"]["x"] + 3, by_name["b"]["x"])

    def test_selects_variant_and_routes_named_pin(self):
        spec = {
            "max_height": 5,
            "components": [
                {
                    "name": "memory",
                    "variants": [
                        {
                            "name": "wide",
                            "w": 8,
                            "h": 2,
                            "ports": {"reply": {"x": 8, "y": 1}},
                        },
                        {
                            "name": "tall",
                            "w": 2,
                            "h": 8,
                            "ports": {"reply": {"x": 2, "y": 4}},
                        },
                    ],
                },
                {
                    "name": "consumer",
                    "w": 2,
                    "h": 2,
                    "ports": {"request": {"x": -1, "y": 1}},
                },
            ],
            "left_of": [["memory", "consumer"]],
            "edges": [{
                "a": "memory",
                "b": "consumer",
                "a_port": "reply",
                "b_port": "request",
                "max_length": 1,
            }],
        }
        result = smt_layout.solve(spec)
        by_name = {c["name"]: c for c in result["components"]}
        self.assertEqual(by_name["memory"]["variant"], "wide")


if __name__ == "__main__":
    unittest.main()
