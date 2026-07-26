# `submitted/` — the exact program behind each problem's best server score

Pulled with `python3 tools/submissions.py --download submitted/`, which reads
`/api/v1/dashboard/submissions/<id>/download` using the browser session cookie
(`~/.icfpc-cookie`). Neither the Bearer API key nor any documented route returns program
text, which is why these were believed unrecoverable — **they are not**.

That mattered: five of these existed nowhere in git, so the best build for those problems
could be neither reproduced nor improved. Two were the ones we had written off:

| problem | live build | note |
|---|---|---|
| tcp | 32x31, 1,842,739 | ~30% better than anything in the repo |
| little-little-little-man | 149x1469 | the only copy |
| reverse-a-list | 12x12, 17,093 | beats the repo's 11x11 (see below) |
| sort-numbers | 16x16, 720,712 | beats the repo's 21x21 |
| sudoku-validity | 42x40 | beats the repo's copy of the same dimensions |

Re-run the download after any submission; it is the only source of truth for what is live.
`tools/submissions.py` (no flags) prints the box/avgTicks split per problem, which is what
tells you whether a problem is box-bound or tick-bound on the real case set.

The reverse-a-list pair is worth studying: the live 12x12 scores 13,788 locally while the
repo's 11x11 scores 16,638. It is BIGGER and still wins, because squeezing to 11x11 forces
the man to zigzag — 64.9% of its ticks go to turn glyphs and it walks 335 cells, versus
35.8% and 174 cells at 12x12. Over-folding costs more than the box saves.
