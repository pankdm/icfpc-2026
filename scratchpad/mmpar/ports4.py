import itertools, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'solutions', 'matmul'))
from mm2lib import Room
sys.path.insert(0, HERE)
from ports3 import legal, spaced, slots, cell   # noqa
