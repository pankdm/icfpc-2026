"""Addressable circulating RAM component for generated littleman programs.

This packages the offset-addressed belt proven in ``solutions/memory/belt5``.
Commands are ``[0, address]`` for reads and ``[1, address, value]`` for writes.
Read values leave through the reply port.  The returned coordinates are outside
the component and are suitable as endpoints for ``Program.pipe``.
"""


def build(program, ox, oy, size):
    """Stamp a RAM server and its recirculation relay.

    Returns ``{"command": point, "reply": point}``.  The server owns the area
    from roughly ``(ox, oy)`` through ``(ox + 78, oy + 39)``.
    """
    put, text = program.put, program.text
    # OFF encoding makes the belt's seed sentinel distinguishable by sign.
    # Keep the seed literal at least three columns wide. Besides stabilizing
    # component geometry, this prevents a short literal's closing backtick
    # from accidentally pairing vertically with a later horizontal literal.
    size_text = str(size).zfill(3)
    put(ox + 1, oy + 1, "@")
    text(ox + 2, oy + 1, "`" + size_text + "`")
    put(ox + 2 + len(size_text) + 2, oy + 1, "b")
    x = ox + 2 + len(size_text) + 3
    text(x, oy + 1, "`2000000`")
    put(x + 9, oy + 1, "v")

    # Seed loop.
    put(x + 9, oy + 2, "<")
    put(ox + 6, oy + 2, "a")
    put(ox + 7, oy + 2, "m")
    put(ox + 8, oy + 2, "s")
    put(ox + 9, oy + 2, "<")
    put(ox + 6, oy + 3, ">")
    put(ox + 9, oy + 3, "^")
    put(ox + 1, oy + 2, "v")
    put(ox + 1, oy + 3, "v")
    put(ox + 1, oy + 4, ">")
    put(ox + 2, oy + 4, "1")
    put(ox + 3, oy + 4, "N")
    put(ox + 4, oy + 4, "s")
    put(ox + 5, oy + 4, "v")
    put(ox + 5, oy + 5, "<")
    put(ox + 2, oy + 5, "v")
    put(ox + 16, oy + 5, "<")

    # Read command and seek requested address.
    put(ox + 2, oy + 6, "r")
    put(ox + 2, oy + 7, "M")
    put(ox + 2, oy + 8, "r")
    put(ox + 2, oy + 9, "b")
    put(ox + 2, oy + 10, ">")
    put(ox + 6, oy + 10, "v")
    put(ox + 6, oy + 11, "r")
    put(ox + 6, oy + 12, "d")
    put(ox + 5, oy + 12, "s")
    put(ox + 4, oy + 12, "m")
    put(ox + 3, oy + 12, "^")
    put(ox + 3, oy + 10, ">")
    put(ox + 6, oy + 13, "W")
    put(ox + 6, oy + 14, "X")

    # Read branch.
    put(ox + 6, oy + 15, "W")
    put(ox + 6, oy + 16, ">")
    put(ox + 7, oy + 16, "s")
    put(ox + 8, oy + 16, "M")
    text(ox + 9, oy + 16, "`2000000`")
    put(ox + 18, oy + 16, "-")
    put(ox + 19, oy + 16, "N")
    put(ox + 20, oy + 16, "s")
    put(ox + 21, oy + 16, "v")
    put(ox + 21, oy + 17, "v")
    put(ox + 21, oy + 18, "v")
    put(ox + 21, oy + 19, "<")

    # Write branch.
    put(ox + 4, oy + 14, "v")
    put(ox + 4, oy + 15, "r")
    put(ox + 4, oy + 16, "M")
    put(ox + 4, oy + 17, ">")
    text(ox + 5, oy + 17, "`2000000`")
    put(ox + 14, oy + 17, "+")
    put(ox + 15, oy + 17, "v")
    put(ox + 15, oy + 18, "<")
    put(ox + 10, oy + 18, "s")
    put(ox + 9, oy + 18, "v")
    put(ox + 9, oy + 19, ">")
    put(ox + 10, oy + 19, "v")

    # Drain the selected slot and restore it to the belt.
    put(ox + 10, oy + 20, "v")
    put(ox + 10, oy + 21, "r")
    put(ox + 10, oy + 22, "s")
    put(ox + 10, oy + 23, "X")
    put(ox + 9, oy + 23, "^")
    put(ox + 9, oy + 20, ">")
    put(ox + 16, oy + 23, "^")
    program.room(ox, oy, 24, 25)

    command = (ox + 2, oy + 25)
    belt_in = (ox + 6, oy + 25)
    belt_out = (ox + 10, oy + 25)
    reply = (ox + 24, oy + 16)

    # Recirculation belt and relay room.
    base = oy + 32
    points = [(belt_out[0], belt_out[1]), (belt_out[0], base), (ox + 48, base)]
    yy = base
    for index in range(7):
        nx = ox + (70 if index % 2 == 0 else 48)
        points += [(nx, yy), (nx, yy + 1)]
        yy += 1
    points += [(ox + 71, yy)]
    program.pipe(points)

    relay_x = ox + 72
    program.room(relay_x, yy - 2, 6, 6)
    program.text(relay_x + 1, yy, ">@rv")
    program.text(relay_x + 4, yy + 1, "<s.^", "W")
    program.pipe([
        (relay_x - 1, yy + 1),
        (belt_in[0], yy + 1),
        (belt_in[0], belt_in[1] + 2),
        belt_in,
    ])
    return {"command": command, "reply": reply}
