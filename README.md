# ICFPC 2026 — littleman

Team "Snakes, Monkeys, and Two Smoking Lambdas"

Programming language of choice:
* Claude Code
* mad skillz

A lot of problem were solved with AI using "human-in-the-loop" approach. AI generates baseline solution, 
then humans looks and either prompts with fresh ideas or hand optimizes into oblivion.

## Best submissions

All 16 graded problems were solved. Scores use the dashboard's compact notation; ranks
are projected against the frozen boards using the archived exact scores.

| Semester | Problem | Size | Score | Rank | Screenshot |
|---|---|---:|---:|---:|---|
| 1 | [Triangle](best-submissions/triangle.man) | 8×8 | 832 | 1/267 | <a href="best-submissions/screenshots/triangle.png"><img src="best-submissions/screenshots/triangle.png" width="120" alt="Triangle submission"></a> |
| 1 | [Memory](best-submissions/memory.man) | 79×79 | 5.75M | 2/190 | <a href="best-submissions/screenshots/memory.png"><img src="best-submissions/screenshots/memory.png" width="120" alt="Memory submission"></a> |
| 1 | [Reverse a List](best-submissions/reverse-a-list.man) | 11×11 | 13.8K | 2/181 | <a href="best-submissions/screenshots/reverse-a-list.png"><img src="best-submissions/screenshots/reverse-a-list.png" width="120" alt="Reverse a List submission"></a> |
| 1 | [Sort](best-submissions/sort-numbers.man) | 12×12 | 263K | 3/145 | <a href="best-submissions/screenshots/sort-numbers.png"><img src="best-submissions/screenshots/sort-numbers.png" width="120" alt="Sort submission"></a> |
| 2 | [History Lesson](best-submissions/history-lesson.man) | 80×80 | 6.40K | 12/155 | <a href="best-submissions/screenshots/history-lesson.png"><img src="best-submissions/screenshots/history-lesson.png" width="120" alt="History Lesson submission"></a> |
| 2 | [Brackets](best-submissions/brackets.man) | 16×16 | 81.8K | 12/125 | <a href="best-submissions/screenshots/brackets.png"><img src="best-submissions/screenshots/brackets.png" width="120" alt="Brackets submission"></a> |
| 2 | [Packet Reassembly](best-submissions/tcp.man) | 22×22 | 315K | 7/107 | <a href="best-submissions/screenshots/tcp.png"><img src="best-submissions/screenshots/tcp.png" width="120" alt="Packet Reassembly submission"></a> |
| 2 | [Plotter](best-submissions/plotter.man) | 48×50 | 4.52M | 7/95 | <a href="best-submissions/screenshots/plotter.png"><img src="best-submissions/screenshots/plotter.png" width="120" alt="Plotter submission"></a> |
| 3 | [Grade Book](best-submissions/gradebook.man) | 47×64 | 105M | 12/85 | <a href="best-submissions/screenshots/gradebook.png"><img src="best-submissions/screenshots/gradebook.png" width="120" alt="Grade Book submission"></a> |
| 3 | [Matrix Multiply](best-submissions/matmul.man) | 38×38 | 20.6M | 12/83 | <a href="best-submissions/screenshots/matmul.png"><img src="best-submissions/screenshots/matmul.png" width="120" alt="Matrix Multiply submission"></a> |
| 3 | [Sudoku Auditor](best-submissions/sudoku-validity.man) | 28×28 | 1.67M | 7/90 | <a href="best-submissions/screenshots/sudoku-validity.png"><img src="best-submissions/screenshots/sudoku-validity.png" width="120" alt="Sudoku Auditor submission"></a> |
| 3 | [Subset Sum](best-submissions/subset-sum.man) | 118×119 | 456M | 6/80 | <a href="best-submissions/screenshots/subset-sum.png"><img src="best-submissions/screenshots/subset-sum.png" width="120" alt="Subset Sum submission"></a> |
| 4 | [Snake](best-submissions/snake.man) | 62×61 | 39.2M | 6/70 | <a href="best-submissions/screenshots/snake.png"><img src="best-submissions/screenshots/snake.png" width="120" alt="Snake submission"></a> |
| 4 | [Pathfinder](best-submissions/pathfinder.man) | 141×171 | 16.2B | 12/60 | <a href="best-submissions/screenshots/pathfinder.png"><img src="best-submissions/screenshots/pathfinder.png" width="120" alt="Pathfinder submission"></a> |
| 4 | [LLLM](best-submissions/little-little-little-man.man) | 140×125 | 5.59B | 10/62 | <a href="best-submissions/screenshots/little-little-little-man.png"><img src="best-submissions/screenshots/little-little-little-man.png" width="120" alt="LLLM submission"></a> |
| 4 | [LLM](best-submissions/little-little-man.man) | 356×793 | 2.80T | 10/55 | <a href="best-submissions/screenshots/little-little-man.png"><img src="best-submissions/screenshots/little-little-man.png" width="120" alt="LLM submission"></a> |

## Contents

| Folder | Contents |
|---|---|
| [`best-submissions/`](best-submissions/) | Exact best submissions and screenshots |
| [`solutions/`](solutions/) | Candidate programs and builders |
| [`tools/`](tools/) | Grading, submission, layout, and optimization tools |
| [`sim/`](sim/) | Official-oracle harness and profiling |
| [`interp/`](interp/) | Fast Rust interpreter |
| [`interpreter/`](interpreter/) | Reference Python interpreter |
| [`tests/`](tests/) | Cached problem specifications and test data |
| [`docs/`](docs/) | Language notes and workflow guides |
| [`submitted/`](submitted/) | Archived submissions and grader results |
| [`scratchpad/`](scratchpad/) | Experiments and probes |

## Appendix

Solutions and tooling for the 2026 ICFP Programming Contest.

- [Problem and language reference](PROBLEM.md)
- [Python interpreter](interpreter/README.md)
- [`Y` split semantics](https://icfpcontest2026.com/split)
