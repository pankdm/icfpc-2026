#!/usr/bin/env python3
"""Standalone probe for tools/packed_ram_proxy.py."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm
import packed_ram_proxy


p = lm.Program()
proxy = packed_ram_proxy.build(p, 10, 5)
p.input_room(12, 0)
p.output_room(21, 14)
p.pipe([(13, 3), proxy["command"]])
p.pipe([proxy["expanded"], (20, 15)])
p.save(os.path.join(os.path.dirname(__file__), "packed-ram-proxy.man"))
