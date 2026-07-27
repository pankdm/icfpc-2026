# C for a 3-TALL interior (enables C 15x5 / 12x5 -> route A's 16x16 box).
#
# VERIFIED BY CONSTRUCTION, NOT YET GRADED -- one open item at the bottom.
# Ticks are IDENTICAL to today's 4-row C: opener 10, closer 12.
#
# The 4th row in p6/p8's C is spent only on the closer's `}` and its return leg.
# Folding to 3 rows is free because the branch is SYMMETRIC: put the compute leg
# on the MIDDLE row and let `x` throw openers south and closers north -- each
# side then gets its own full return row.
#
#   row 1  (closer return, westbound)   <  }  N  s  q  a
#   row 2  (compute leg,   eastbound)   U  b  m  ]  x
#   row 3  (opener return, westbound)   <  }  s  q  d
#
# `x` at the east end of row 2, man heading east:
#   opener (bit0 of (ascii-1)>>1 == 1) -> CW  -> south -> row 3
#   closer (bit0 == 0)                 -> CCW -> north -> row 1
# `d` at the west end of row 3: BP>0 -> CW (west->north) -> back onto U.  exit W.
# `a` at the west end of row 1: BP>0 -> CCW (west->south) -> (c-1,2) '>' -> U.  exit W.
#
# opener cycle 10:  q d U b m ] x < } s
# closer cycle 12:  q a > U b m ] x < } N s
#
# With the compute leg at cols c..c+4 on row 2 (c=6, interior cols 1..10):
C_ROW1 = [(5,1,'a'),(6,1,'q'),(7,1,'s'),(8,1,'N'),(9,1,'}'),(10,1,'<')]
C_ROW2 = [(5,2,'>'),(6,2,'U'),(7,2,'b'),(8,2,'m'),(9,2,']'),(10,2,'x')]
C_ROW3 = [(6,3,'d'),(7,3,'q'),(8,3,'s'),(9,3,'}'),(10,3,'<')]
# exits: opener `d`(6,3) straight W -> (5,3);  closer `a`(5,1) straight W -> (4,1)

# IDLE / RESET RING -- 4 wide x 3 tall rectangle at cols 1..4, perimeter 10 cells.
# Both main-loop exits fall into it and it re-enters the hot loop at (5,2).
IDLE = [
 (4,1,'<'),   # corner N->W; closer exit arrives heading W and just continues
 (3,1,'0'),   # A := 0   (exits arrive with A = +-t)
 (2,1,'s'),   # send the 0 sentinel to M
 (1,1,'v'),   # corner W->S
 (1,2,'5'),
 (1,3,'>'),   # corner S->E
 (2,3,'M'),   # B := 5, parked for the whole run ( '}' is then one op )
 (3,3,'U'),   # read next n; U faces EAST, which is the ring direction
 (4,3,'^'),   # corner E->N; OPENER exit arrives heading W and turns N into the ring
 (4,2,'X'),   # n>0 -> CW (N->E) -> (5,2) '>' -> U, hot loop
]              # n==0 -> straight N -> (4,1) -> 0,s : emits the empty-string 0
# interior of the idle ring: (2,2),(3,2) are free.
#
# OPEN ITEM (the only one): the man must start AFTER `s`(2,1) and BEFORE `U`(3,3)
# or he emits a spurious sentinel at t=0, and he must still execute `5`,`M`.
# Starting him at (2,2) and making (3,2)='v' reaches U but SKIPS 5/M, so the
# first round runs with B=0 and `}` degenerates to a no-op.
# Fixes that fit: (a) give the stub two cells by moving the compute leg one
# column east so the X-exit lane is (5,2),(6,2) and only (6,2) is shared with
# the closer re-entry; (b) start the man outside C's ring in a spare column.
# p8_build.py solved the identical problem with a 2-cell stub -- see its C_CELLS.
