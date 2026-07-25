"""Generate a deterministic maximum-token stress case for the memory problem."""

from __future__ import annotations

import json
import random
from pathlib import Path


SEED = 20260724
WRITE_COUNT = 150
READ_COUNT = 275


def build_case() -> dict[str, object]:
    randomizer = random.Random(SEED)
    operations = [1] * WRITE_COUNT + [0] * READ_COUNT
    randomizer.shuffle(operations)

    memory = [0] * 100
    input_tokens = []
    output_tokens = []
    for operation in operations:
        address = randomizer.randrange(100)
        input_tokens.extend((str(operation), str(address)))
        if operation == 0:
            output_tokens.append(str(memory[address]))
        else:
            value = randomizer.randint(-1_000_000, 1_000_000)
            input_tokens.append(str(value))
            memory[address] = value

    assert len(input_tokens) == 1_000
    return {
        "name": "deterministic maximum-token mixed operations",
        "seed": SEED,
        "writeCount": WRITE_COUNT,
        "readCount": READ_COUNT,
        "in": input_tokens,
        "out": output_tokens,
    }


def main() -> None:
    output = Path(__file__).resolve().parents[2] / "tests" / "memory-max.json"
    output.write_text(json.dumps(build_case(), indent=2) + "\n", encoding="ascii")
    print(output)


if __name__ == "__main__":
    main()
