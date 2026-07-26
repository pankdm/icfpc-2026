#!/usr/bin/env python3
"""Profile semantic Flow tokens and blocks for one cached public case."""

from collections import Counter
import argparse
import importlib
import json
import os
import sys


HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from verify_subset import run_flow  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("--builder", default="build_banked")
    parser.add_argument("--rounds", type=int)
    args = parser.parse_args()
    builder = importlib.import_module(args.builder)
    with open(os.path.join(HERE, "..", "..", "tests", "little-little-man.json")) as stream:
        spec = json.load(stream)
    case = next(item for item in spec["publicTestData"] if item["name"] == args.case)
    rounds = case["rounds"][: args.rounds]
    tokens = Counter()
    blocks = Counter()

    def observe(label, token):
        blocks[label] += 1
        tokens[token[0] if isinstance(token, tuple) else token] += 1

    _, total = run_flow(rounds, limit=10_000_000, builder=builder, token_hook=observe)
    print("total", total)
    print("tokens")
    for token, count in tokens.most_common():
        print(f"{token!s:8} {count:8}")
    print("blocks")
    for label, count in blocks.most_common(30):
        print(f"{label:28} {count:8}")


if __name__ == "__main__":
    main()
