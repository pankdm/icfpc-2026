from __future__ import annotations

from pathlib import Path


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.cells = [[" "] * width for _ in range(height)]

    def put(self, x: int, y: int, character: str) -> None:
        current = self.cells[y][x]
        if current != " " and current != character:
            raise ValueError(f"cell {(x, y)} already contains {current!r}, cannot place {character!r}")
        self.cells[y][x] = character

    def room(self, left: int, top: int, right: int, bottom: int) -> None:
        self.put(left, top, "+")
        self.put(right, top, "+")
        self.put(left, bottom, "+")
        self.put(right, bottom, "+")
        for x in range(left + 1, right):
            self.put(x, top, "-")
            self.put(x, bottom, "-")
        for y in range(top + 1, bottom):
            self.put(left, y, "|")
            self.put(right, y, "|")

    def io_room(self, center_x: int, top: int, kind: str) -> None:
        self.room(center_x - 1, top, center_x + 1, top + 2)
        self.put(center_x, top + 1, kind)

    def pipe(self, points: list[tuple[int, int]]) -> None:
        if len(points) < 2:
            raise ValueError("pipe must have at least two cells")
        directions = [
            (points[index + 1][0] - points[index][0], points[index + 1][1] - points[index][1])
            for index in range(len(points) - 1)
        ]
        if any(direction not in {(1, 0), (-1, 0), (0, 1), (0, -1)} for direction in directions):
            raise ValueError("pipe points must be adjacent")
        for index, point in enumerate(points):
            if index == 0:
                character = arrow(directions[0])
            elif index == len(points) - 1:
                character = arrow(directions[-1])
            elif directions[index - 1] != directions[index]:
                character = arrow(directions[index])
            else:
                character = "-" if directions[index][0] else "|"
            self.put(point[0], point[1], character)

    def render(self) -> str:
        lines = ["".join(row).rstrip() for row in self.cells]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + "\n"


def arrow(direction: tuple[int, int]) -> str:
    return {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}[direction]


def vertical_points(x: int, start_y: int, end_y: int) -> list[tuple[int, int]]:
    step = 1 if end_y > start_y else -1
    return [(x, y) for y in range(start_y, end_y + step, step)]


def horizontal_points(y: int, start_x: int, end_x: int) -> list[tuple[int, int]]:
    step = 1 if end_x > start_x else -1
    return [(x, y) for x in range(start_x, end_x + step, step)]


def draw_controller(canvas: Canvas, top: int) -> None:
    canvas.room(0, top, 44, top + 44)
    instructions = {
        (2, 10): ">",
        (6, 10): "r",
        (7, 10): "M",
        (8, 10): "r",
        (9, 10): "W",
        (10, 10): "b",
        (12, 10): "v",
        (12, 30): ">",
        (30, 30): "s",
        (32, 30): "W",
        (34, 30): "s",
        (36, 30): "d",
        (38, 30): "r",
        (40, 30): "^",
        (40, 5): "<",
        (16, 5): "s",
        (2, 5): "v",
        (36, 40): "<",
        (4, 40): "^",
        (4, 8): ">",
        (6, 8): "r",
        (10, 8): "v",
        (10, 32): ">",
        (30, 32): "s",
        (38, 32): "r",
        (40, 32): "v",
        (40, 42): "<",
        (2, 42): "^",
    }
    canvas.put(3, top + 10, "@")
    for (x, y), character in instructions.items():
        canvas.put(x, top + y, character)


def draw_stage(canvas: Canvas, top: int) -> None:
    canvas.room(0, top, 44, top + 44)
    instructions = {
        (2, 20): ">",
        (6, 20): "R",
        (7, 20): "b",
        (8, 20): "R",
        (10, 20): "X",
        (14, 20): "d",
        (16, 20): "W",
        (18, 20): "^",
        (18, 6): ">",
        (36, 6): "s",
        (38, 6): "W",
        (40, 6): "^",
        (40, 2): "<",
        (2, 2): "v",
        (14, 24): "R",
        (14, 25): "M",
        (14, 26): "0",
        (14, 38): "<",
        (12, 38): "^",
        (12, 4): ">",
        (36, 4): "s",
        (42, 4): "v",
        (42, 18): "<",
        (2, 18): "v",
        (10, 24): "W",
        (10, 28): ">",
        (32, 28): "s",
        (33, 28): "1",
        (34, 28): "W",
        (35, 28): "-",
        (36, 28): "M",
        (38, 28): "d",
        (40, 28): "0",
        (41, 28): "v",
        (41, 34): "<",
        (38, 30): "1",
        (38, 34): "<",
        (30, 34): "s",
        (28, 34): "W",
        (26, 34): "s",
        (24, 34): "d",
        (18, 34): "v",
        (18, 40): "r",
        (18, 42): ">",
        (42, 42): "<",
        (40, 42): "<",
        (22, 42): "^",
        (22, 10): ">",
        (36, 10): "s",
        (40, 10): "r",
        (41, 10): "M",
        (42, 10): "v",
        (24, 12): ">",
        (30, 12): "r",
        (39, 12): "v",
        (39, 32): "<",
        (30, 32): "s",
        (28, 32): "v",
        (28, 40): "r",
        (28, 42): "<",
        (40, 30): "v",
        (40, 38): "r",
    }
    canvas.put(3, top + 20, "@")
    for (x, y), character in instructions.items():
        canvas.put(x, top + y, character)
    draw_helper(canvas, top + 7)
    outbound = horizontal_points(top + 28, 45, 56)
    outbound.extend((56, y) for y in range(top + 27, top + 7, -1))
    outbound.append((55, top + 8))
    canvas.pipe(outbound)
    canvas.pipe(horizontal_points(top + 10, 47, 45))


def draw_helper(canvas: Canvas, top: int) -> None:
    canvas.room(48, top, 54, top + 6)
    rows = [">@r v", "^   v", "s   v", "^   v", "^<<<<"]
    for row_index, row in enumerate(rows, start=1):
        for column_index, character in enumerate(row, start=49):
            if character != " ":
                canvas.put(column_index, top + row_index, character)


def connect_layers(canvas: Canvas, upper_bottom: int, lower_top: int) -> None:
    canvas.pipe(vertical_points(30, upper_bottom + 1, lower_top - 1))

    acknowledgement = [
        (36, lower_top - 1),
        (36, lower_top - 2),
        (37, lower_top - 2),
        (38, lower_top - 2),
        (38, upper_bottom + 2),
        (38, upper_bottom + 1),
    ]
    canvas.pipe(acknowledgement)


def generate() -> str:
    controller_top = 6
    controller_bottom = controller_top + 44
    first_stage_top = controller_bottom + 5
    stage_stride = 49
    final_stage_bottom = first_stage_top + 99 * stage_stride + 44
    canvas = Canvas(57, final_stage_bottom + 1)

    canvas.io_room(6, 0, "I")
    canvas.io_room(16, 0, "O")
    canvas.pipe(vertical_points(6, 3, controller_top - 1))
    canvas.pipe(vertical_points(16, controller_top - 1, 3))
    draw_controller(canvas, controller_top)

    previous_bottom = controller_bottom
    for index in range(100):
        stage_top = first_stage_top + index * stage_stride
        connect_layers(canvas, previous_bottom, stage_top)
        draw_stage(canvas, stage_top)
        previous_bottom = stage_top + 44

    return canvas.render()


def main() -> None:
    output = Path(__file__).with_name("p1.man")
    output.write_text(generate(), encoding="ascii")
    print(output)


if __name__ == "__main__":
    main()
