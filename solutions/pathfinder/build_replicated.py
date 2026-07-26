#!/usr/bin/env python3
"""Four-mirror Pathfinder wrapper for semantic verification."""

from build_async import *  # noqa: F401,F403
import build_async as _async


def build_flow():
    return _async.build_flow(4)


def build(belt_count=9, code_x=100):
    return _async.build(belt_count, code_x, 4)
