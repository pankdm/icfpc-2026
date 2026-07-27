# M's drain loop: what I found, and the exact blocker for 9x9 -> 8x9.
# NOT LANDED. Read this before re-attempting; two of the three sub-problems are solved.
#
# 1) THREE cells in M are provably dead, not one. All confirmed by reading the
#    three chains that reach them (offence-verdict, unclosed-end, balanced-end):
#      (3,9) 'M'  -- B is already 0 on all three chains
#      (2,9) '0'  and  (5,9) '0'  -- duplicates, one per chain
#    Replace all three with a SINGLE '0' at (4,3), on the shared column-4 reset
#    climb, between (4,4)'+' and (4,2)'^'.  A is untouched by '+' there (B=0).
#    Row 9 then becomes  >  .  .  ^  s  N  2  <   -- and the offence chain can
#    shift one column west, so row 9's extent is cols 1..8.  COLUMN 9 IS THEN
#    FREE IN ROW 9.  This part is easy and safe.
#
# 2) The drain ring can be 8 cells instead of 10 (also -2 ticks per drained
#    token, which matters on early-offence + long-input private cases):
#      corners (8,5)'v' (8,8)'X' (7,8)'^' (7,5)'>'
#      straights in walk order after X:  (7,7)'r'  (7,6)'M'  (8,6)'*'  (8,7) .
#    'X' sits on the corner: A=token*token > 0 -> CW (south->west) keeps the
#    ring; A==0 -> STRAIGHT south -> (8,9) -> verdict chain. Corners are free
#    work, so the whole zero-test costs no cell.
#
# 3) BLOCKER (this is what stopped me): the drain's return column must become 7,
#    and col 7 rows 1-4 are owned by the S==t pop tail:
#      (7,4)'^'  (7,3)'1'  (7,2)'s'  (7,1)'<'
#    (7,4) and (7,3) are compatible -- the drain walks them northbound and '1'
#    is harmless there because the drain's 'r' overwrites A two cells later.
#    (7,2) is NOT: the pop needs 's' (send the trigger) and the drain needs '>'
#    (turn east). One cell, two incompatible ops.
#
#    Ways out, in order of how much I believe them:
#    a) Give the S==t pop its own trigger cell on row 1 -- (8,1) and (9,1) are
#       free today and (9,x) is being vacated anyway.
#    b) Fold the S==t pop into the general pop: it already computes correctly
#       through 3/W// (0/3 = 0 rem 0, B := 0), the ONLY thing that breaks is the
#       trigger, because A ends 0 and P needs a positive value.  If P's protocol
#       is re-signed so 0 means "increment", this case disappears entirely and
#       col 7 rows 1-3 free up wholesale.  That also deletes (6,1)'0'.
