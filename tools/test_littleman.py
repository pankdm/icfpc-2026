import unittest

from tools.littleman import Program


class ProgramGeometryTests(unittest.TestCase):
    def test_room_records_its_rectangle(self):
        program = Program()
        rectangle = program.room(3, 4, 7, 5)
        self.assertEqual(program.rooms, [rectangle])
        self.assertEqual((rectangle.ix0, rectangle.iy0, rectangle.ix1, rectangle.iy1),
                         (4, 5, 8, 7))

    def test_pipe_can_turn_on_its_final_cell(self):
        program = Program()
        program.pipe([(1, 1), (1, 3)], end_direction="E")
        self.assertEqual(program.get(1, 1), "v")
        self.assertEqual(program.get(1, 2), "|")
        self.assertEqual(program.get(1, 3), ">")

    def test_pipe_rejects_unknown_end_direction(self):
        program = Program()
        with self.assertRaises(ValueError):
            program.pipe([(1, 1), (1, 2)], end_direction="sideways")


if __name__ == "__main__":
    unittest.main()
