#!/usr/bin/env python3
"""Z3-backed coarse floorplanner for Littleman rooms and components.

This deliberately solves the discrete geometry above exact routing: rectangle
position/orientation, non-overlap, relative order, max-dimension, and weighted
connection length.  The existing router/reflow tools materialize and validate
the resulting placement.

Input is JSON:

{
  "components": [
    {"name": "controller", "w": 120, "h": 80},
    {"name": "display", "w": 18, "h": 18, "rotate": false}
  ],
  "edges": [
    {"a": "controller", "b": "display", "weight": 100,
     "min_length": 4, "max_length": 200}
  ],
  "left_of": [["controller", "display"]],
  "gap": 2
}

Usage:

  python3 tools/smt_layout.py emit spec.json > model.smt2
  python3 tools/smt_layout.py solve spec.json
"""

import argparse
import json
import re
import subprocess
import sys


def symbol(name):
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not safe or safe[0].isdigit():
        safe = f"c_{safe}"
    return safe


class Model:
    def __init__(self, spec):
        self.spec = spec
        self.components = spec.get("components") or []
        if not self.components:
            raise ValueError("spec needs at least one component")
        names = [component["name"] for component in self.components]
        if len(names) != len(set(names)):
            raise ValueError("component names must be unique")
        self.by_name = {component["name"]: component for component in self.components}
        self.ids = {name: symbol(name) for name in names}
        if len(set(self.ids.values())) != len(self.ids):
            raise ValueError("component names collide after SMT symbol sanitization")

    def var(self, prefix, name):
        return f"{prefix}_{self.ids[name]}"

    def x(self, name):
        return self.var("x", name)

    def y(self, name):
        return self.var("y", name)

    def rot(self, name):
        return self.var("rot", name)

    def variant(self, name):
        return self.var("variant", name)

    def variants(self, name):
        return self.by_name[name].get("variants") or []

    def variant_expr(self, name, value_fn):
        variants = self.variants(name)
        if not variants:
            raise ValueError(f"{name} has no variants")
        expr = str(int(value_fn(variants[-1])))
        for index in range(len(variants) - 2, -1, -1):
            expr = (
                f"(ite (= {self.variant(name)} {index}) "
                f"{int(value_fn(variants[index]))} {expr})"
            )
        return expr

    def width(self, name):
        component = self.by_name[name]
        if self.variants(name):
            return self.variant_expr(name, lambda variant: variant["w"])
        if component.get("rotate", False) and component["w"] != component["h"]:
            return f"(ite {self.rot(name)} {int(component['h'])} {int(component['w'])})"
        return str(int(component["w"]))

    def height(self, name):
        component = self.by_name[name]
        if self.variants(name):
            return self.variant_expr(name, lambda variant: variant["h"])
        if component.get("rotate", False) and component["w"] != component["h"]:
            return f"(ite {self.rot(name)} {int(component['w'])} {int(component['h'])})"
        return str(int(component["h"]))

    def center2_x(self, name):
        return f"(+ (* 2 {self.x(name)}) {self.width(name)})"

    def center2_y(self, name):
        return f"(+ (* 2 {self.y(name)}) {self.height(name)})"

    def point2_x(self, name, port):
        """Twice the absolute x of a local attachment point."""
        if port is None:
            return self.center2_x(name)
        component = self.by_name[name]
        if isinstance(port, str):
            if not self.variants(name):
                port = component.get("ports", {}).get(port)
                if port is None:
                    raise ValueError(f"{name} has no named port {port!r}")
                px, py = int(port["x"]), int(port["y"])
            else:
                px = self.variant_expr(
                    name,
                    lambda variant: variant["ports"][port]["x"],
                )
                return f"(* 2 (+ {self.x(name)} {px}))"
        else:
            px, py = int(port["x"]), int(port["y"])
        if component.get("rotate", False) and component["w"] != component["h"]:
            # Clockwise rotation in grid coordinates: (x,y) -> (h-1-y,x).
            local = f"(ite {self.rot(name)} {int(component['h']) - 1 - py} {px})"
        else:
            local = str(px)
        return f"(* 2 (+ {self.x(name)} {local}))"

    def point2_y(self, name, port):
        """Twice the absolute y of a local attachment point."""
        if port is None:
            return self.center2_y(name)
        component = self.by_name[name]
        if isinstance(port, str):
            if not self.variants(name):
                port = component.get("ports", {}).get(port)
                if port is None:
                    raise ValueError(f"{name} has no named port {port!r}")
                px, py = int(port["x"]), int(port["y"])
            else:
                py = self.variant_expr(
                    name,
                    lambda variant: variant["ports"][port]["y"],
                )
                return f"(* 2 (+ {self.y(name)} {py}))"
        else:
            px, py = int(port["x"]), int(port["y"])
        if component.get("rotate", False) and component["w"] != component["h"]:
            local = f"(ite {self.rot(name)} {px} {py})"
        else:
            local = str(py)
        return f"(* 2 (+ {self.y(name)} {local}))"

    def emit(self):
        lines = [
            "(set-option :produce-models true)",
            "(set-option :opt.priority lex)",
            "(set-logic QF_LIA)",
        ]
        for component in self.components:
            name = component["name"]
            lines.append(f"(declare-const {self.x(name)} Int)")
            lines.append(f"(declare-const {self.y(name)} Int)")
            variants = self.variants(name)
            if variants:
                if component.get("rotate", False):
                    raise ValueError(
                        f"{name}: encode rotated forms as variants, not rotate=true"
                    )
                for variant in variants:
                    if "w" not in variant or "h" not in variant:
                        raise ValueError(f"{name}: every variant needs w and h")
                lines.append(f"(declare-const {self.variant(name)} Int)")
                lines.append(f"(assert (>= {self.variant(name)} 0))")
                lines.append(
                    f"(assert (< {self.variant(name)} {len(variants)}))"
                )
            elif component.get("rotate", False) and component["w"] != component["h"]:
                lines.append(f"(declare-const {self.rot(name)} Bool)")
            lines.append(f"(assert (>= {self.x(name)} 0))")
            lines.append(f"(assert (>= {self.y(name)} 0))")
            if "x" in component:
                lines.append(f"(assert (= {self.x(name)} {int(component['x'])}))")
            if "y" in component:
                lines.append(f"(assert (= {self.y(name)} {int(component['y'])}))")

        gap = int(self.spec.get("gap", 0))
        for i, left in enumerate(self.components):
            for right in self.components[i + 1:]:
                a, b = left["name"], right["name"]
                lines.append(
                    "(assert (or "
                    f"(<= (+ {self.x(a)} {self.width(a)} {gap}) {self.x(b)}) "
                    f"(<= (+ {self.x(b)} {self.width(b)} {gap}) {self.x(a)}) "
                    f"(<= (+ {self.y(a)} {self.height(a)} {gap}) {self.y(b)}) "
                    f"(<= (+ {self.y(b)} {self.height(b)} {gap}) {self.y(a)})))"
                )

        for key, axis in (("left_of", "x"), ("above", "y")):
            for a, b in self.spec.get(key, []):
                if a not in self.by_name or b not in self.by_name:
                    raise ValueError(f"unknown component in {key}: {a}, {b}")
                pos = self.x if axis == "x" else self.y
                extent = self.width if axis == "x" else self.height
                lines.append(
                    f"(assert (<= (+ {pos(a)} {extent(a)} {gap}) {pos(b)}))"
                )

        lines.extend([
            "(declare-const bbox_w Int)",
            "(declare-const bbox_h Int)",
            "(declare-const max_dim Int)",
            "(assert (>= bbox_w 0))",
            "(assert (>= bbox_h 0))",
            "(assert (>= max_dim bbox_w))",
            "(assert (>= max_dim bbox_h))",
        ])
        for component in self.components:
            name = component["name"]
            lines.append(
                f"(assert (>= bbox_w (+ {self.x(name)} {self.width(name)})))"
            )
            lines.append(
                f"(assert (>= bbox_h (+ {self.y(name)} {self.height(name)})))"
            )
        if "max_width" in self.spec:
            lines.append(f"(assert (<= bbox_w {int(self.spec['max_width'])}))")
        if "max_height" in self.spec:
            lines.append(f"(assert (<= bbox_h {int(self.spec['max_height'])}))")

        wire_terms = []
        for edge_i, edge in enumerate(self.spec.get("edges", [])):
            a, b = edge["a"], edge["b"]
            if a not in self.by_name or b not in self.by_name:
                raise ValueError(f"unknown edge endpoint: {a}, {b}")
            dx, dy = f"edge_{edge_i}_dx2", f"edge_{edge_i}_dy2"
            length = f"edge_{edge_i}_length2"
            ax = self.point2_x(a, edge.get("a_port"))
            ay = self.point2_y(a, edge.get("a_port"))
            bx = self.point2_x(b, edge.get("b_port"))
            by = self.point2_y(b, edge.get("b_port"))
            lines.extend([
                f"(declare-const {dx} Int)",
                f"(declare-const {dy} Int)",
                f"(declare-const {length} Int)",
                f"(assert (>= {dx} (- {ax} {bx})))",
                f"(assert (>= {dx} (- {bx} {ax})))",
                f"(assert (>= {dy} (- {ay} {by})))",
                f"(assert (>= {dy} (- {by} {ay})))",
                f"(assert (= {length} (+ {dx} {dy})))",
            ])
            if "min_length" in edge:
                lines.append(
                    f"(assert (>= {length} {2 * int(edge['min_length'])}))"
                )
            if "max_length" in edge:
                lines.append(
                    f"(assert (<= {length} {2 * int(edge['max_length'])}))"
                )
            wire_terms.append(f"(* {int(edge.get('weight', 1))} {length})")

        wire_expr = "(+ " + " ".join(wire_terms) + ")" if wire_terms else "0"
        lines.extend([
            "(declare-const wire_cost Int)",
            f"(assert (= wire_cost {wire_expr}))",
            "(minimize max_dim)",
            "(minimize wire_cost)",
            "(minimize (+ bbox_w bbox_h))",
            "(check-sat)",
        ])
        values = ["max_dim", "bbox_w", "bbox_h", "wire_cost"]
        for component in self.components:
            name = component["name"]
            values.extend([self.x(name), self.y(name)])
            if self.variants(name):
                values.append(self.variant(name))
            elif component.get("rotate", False) and component["w"] != component["h"]:
                values.append(self.rot(name))
        lines.append(f"(get-value ({' '.join(values)}))")
        return "\n".join(lines) + "\n"

    def decode(self, stdout):
        if not stdout.startswith("sat\n"):
            raise RuntimeError(f"z3 did not find a model: {stdout[:400]}")
        values = {
            name: value
            for name, value in re.findall(
                r"\(([A-Za-z0-9_]+)\s+(-?[0-9]+|true|false)\)",
                stdout,
            )
        }
        result = {
            "max_dim": int(values["max_dim"]),
            "width": int(values["bbox_w"]),
            "height": int(values["bbox_h"]),
            "wire_cost2": int(values["wire_cost"]),
            "components": [],
        }
        for component in self.components:
            name = component["name"]
            variants = self.variants(name)
            chosen_variant = None
            if variants:
                chosen_variant = variants[int(values[self.variant(name)])]
                rotated = False
                width = int(chosen_variant["w"])
                height = int(chosen_variant["h"])
            else:
                rotated = values.get(self.rot(name), "false") == "true"
                width = int(component["h"] if rotated else component["w"])
                height = int(component["w"] if rotated else component["h"])
            decoded = {
                "name": name,
                "x": int(values[self.x(name)]),
                "y": int(values[self.y(name)]),
                "w": width,
                "h": height,
                "rotated": rotated,
            }
            if chosen_variant is not None:
                decoded["variant"] = chosen_variant.get(
                    "name",
                    str(int(values[self.variant(name)])),
                )
            result["components"].append(decoded)
        return result


def solve(spec, z3="z3"):
    model = Model(spec)
    process = subprocess.run(
        [z3, "-in"],
        input=model.emit(),
        text=True,
        capture_output=True,
        timeout=float(spec.get("timeout_seconds", 60)),
    )
    if process.returncode:
        raise RuntimeError((process.stderr or process.stdout)[:1000])
    return model.decode(process.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("emit", "solve"))
    parser.add_argument("spec")
    parser.add_argument("--z3", default="z3")
    args = parser.parse_args()
    with open(args.spec, encoding="utf-8") as handle:
        spec = json.load(handle)
    model = Model(spec)
    if args.command == "emit":
        sys.stdout.write(model.emit())
    else:
        print(json.dumps(solve(spec, args.z3), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
