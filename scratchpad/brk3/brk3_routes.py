#!/usr/bin/env python3
"""The four ways brackets reaches 16x16, ranked by how many rooms must be re-laid.

Constraints (live floorplan: P east of M, C south spanning right, I/O in margins):
    width  = M_w + P_w              <= 16
    height = max(M_h, P_h) + C_h    <= 16
    C_w <= 16

Nothing else binds -- I and O sit inside margins the other rooms already force.
Cell counts are unchanged in every route below; only rectangles change.

  python3 brk3_routes.py
"""

TODAY = {"M": (11, 11, 56), "P": (6, 8, 20), "C": (12, 6, 28)}


def fill(w, h, n):
    return n / ((w - 2) * (h - 2))


ROUTES = [
    ("D  one room: M only",
     {"M": (10, 10), "P": (6, 8), "C": (12, 6)},
     "M loses a column AND a row; P and C untouched."),
    ("C  two rooms: M + C",
     {"M": (10, 11), "P": (6, 8), "C": (14, 5)},
     "M loses a column; C loses a row and gains two columns."),
    ("B  two rooms: M + P",
     {"M": (11, 10), "P": (5, 10), "C": (12, 6)},
     "M loses a row; P loses a column and gains two rows; C untouched."),
    ("A  two rooms: P + C",
     {"M": (11, 11), "P": (5, 11), "C": (15, 5)},
     "M UNTOUCHED; P loses a column, C loses a row."),
]

print("today:  " + "  ".join(
    f"{k} {w}x{h} interior {w-2}x{h-2} {fill(w,h,n):.0%}"
    for k, (w, h, n) in TODAY.items()))
print(f"        width {TODAY['M'][0]+TODAY['P'][0]}  "
      f"height {max(TODAY['M'][1],TODAY['P'][1])+TODAY['C'][1]}  -> 17x17 = 289\n")

for name, shape, note in ROUTES:
    w = shape["M"][0] + shape["P"][0]
    h = max(shape["M"][1], shape["P"][1]) + shape["C"][1]
    parts = []
    worst = 0.0
    for k in ("M", "P", "C"):
        rw, rh = shape[k]
        n = TODAY[k][2]
        f = fill(rw, rh, n)
        worst = max(worst, f)
        chg = "" if (rw, rh) == TODAY[k][:2] else "*"
        parts.append(f"{k}{chg} {rw}x{rh} ({rw-2}x{rh-2}) {f:.0%}")
    print(f"{name}\n    {'   '.join(parts)}")
    print(f"    box {w}x{h} = {max(w,h)**2}   worst fill {worst:.0%}   {note}")

print("""
P's walk, decomposed per arm -- the input a re-lay needs (interior 4x6 today):
    spine       @(1,6) glides E, ^(2,6) turns N, r(2,5), X(2,4)
    X heading N: A>0 -> E, A=0 -> N, A<0 -> W
    A>0 arm     ops [1, +, M]
    A=0 arm     ops [s, 0, M, +, M]
    A<0 arm     ops [1, +, s, 0, M, +, M]
    shared tail M(4,3) then +(4,5) then M(3,6); the A>0 arm joins BELOW the M,
    at the +, which is why the tail cannot simply be read in one direction.
A 3-wide interior suits the branch itself perfectly -- X in the middle column
puts the two turning arms in columns 1 and 3 -- but the shared tail then has to
share a column with an arm, and the A>0 arm's late join is what makes that hard.
""")
