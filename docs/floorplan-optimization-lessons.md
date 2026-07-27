# Floor-plan optimization lessons

These are reusable lessons from folding the Pathfinder MEM16 solver from a
very tall generated layout into a nearly square one.  They apply to any
Littleman program with a controller, several service rooms, and routed pipes.

## Optimize the scored side, not area

The score uses `max(width, height)^2`, so a move has no footprint value until
it reduces the longest side or stays below it while buying ticks.

Keep three numbers for every candidate:

```text
width × height, box = max(width, height)^2, ticks
```

Once a layout is nearly square, extra width is free only up to the current
height.  This turns placement into a constrained tick search: use the spare
short-side columns to widen hot controller lanes, shorten a service loop, or
move a port, but reject the move as soon as it becomes the new longest side.

Pathfinder example:

```text
175×201, box 40,401, 843,534 ticks
183×184, box 33,856, 830,074 ticks
```

The winning port spacing used almost every free width cell.  Nearby spacings
that were a little wider lost despite having similar controller height.

## A one-cell gap can accidentally connect two rooms

Pipes are discovered from grid topology, not from the builder call that
created them.  Placing a service room just beyond a controller can make a
service's input cell adjacent to both rooms.  The program may still load, but
the controller then has an extra incoming or outgoing pipe.  Lowercase `r` or
`s` silently binds to the nearest attachment and can park forever on the wrong
channel.

This happened when Pathfinder's display driver was placed at
`controller_width + 2`.  The build loaded but stopped after four setup tokens.
Moving the driver to `controller_width + 4` restored isolation.

After moving rooms, inspect topology as well as collisions:

- count each room's incoming and outgoing pipes;
- check the exact attachment cells;
- sample the main runner after a short execution;
- treat a stationary runner on `r`/`s` as a likely binding error, not merely a
  slow candidate.

A load-valid grid is not necessarily the netlist the builder intended.

## Route order matters at the controller wall

Bottom-attached nets are not independent.  A horizontal pipe one row below the
controller crosses every vertical bottom port between its source and
destination.  In Pathfinder, the display pipe crossed the input return after
the input port moved to the right.

Before drawing apron routes, order the terminals and choose a planar matching.
If a horizontal route must pass another terminal, either:

- move its logical controller port beyond that terminal;
- put the destination on the same side of the terminal;
- route at a different layer with enough room for two turns; or
- move one service to a side wall.

Do this before packing rooms.  Fixing crossings after placement tends to grow
the scored side and can create new nearest-pipe bindings.

## Optimize closed walks inside services

External pipe length is only one part of an access.  A persistent service man
also walks from its receive site through dispatch, to a worker, and back to
the receive site.  That closed walk is paid on every transaction.

Pathfinder's 106-row MEM16 hub entered near its top, descended to a decoder
root near the middle, visited a leaf, then returned to the top.  Moving the
entry loop to the decoder root and giving upper and lower leaves separate
one-way return columns changed no protocol, room, pipe, or footprint:

```text
183×184, 830,074 average ticks
183×184, 764,008 average ticks
```

The dominant case fell from 1,029,822 to 947,049 ticks.  Shortening external
pipes alone could not remove those internal walks.

For every hot service, draw its repeated man path as a cycle and count cells:

```text
receive → decode → operation → send → return → receive
```

Put the receive/return merge near the geometric median of hot operations.
Bidirectional returns need separate columns or direction-neutral crossings;
one arrow column cannot safely carry men both up and down.

## Align modules by hot endpoints, not by their top walls

Two rooms can overlap perfectly in height while their communicating endpoints
are still far apart.  Pathfinder originally placed MEM16 near the controller's
top, but both controller ports were on its bottom wall.  Every dependent access
therefore traversed two unnecessary vertical pipe legs.

Sliding MEM16 down until its command and reply endpoints nearly aligned with
the controller ports changed neither module and stayed inside the same box:

```text
183×184, 764,008 average ticks
183×184, 642,791 average ticks
```

Align the endpoints on the critical request/reply cycle, not room origins or
visual centers.  Sweep the last few cells: command and reply endpoints may sit
at different offsets inside a module, so their individual optima differ.

The validity boundary is useful information.  Moving Pathfinder's memory one
more row made its endpoint touch an apron route and changed the parsed pipe
topology.  The best valid placement was exactly one row before that boundary.

## Profile blocked cells separately from glide cells

Whole-program glyph totals are misleading because parked relay and memory men
execute `r` every tick.  Profile by room and cell.

For the Pathfinder controller, the dominant case attributed roughly:

```text
600k ticks  controller `r`
321k ticks  controller blank glide
 35k ticks  controller `s`
```

That says:

- memory/service turnaround is still the first tick target;
- controller packing has a real but smaller ceiling;
- adding more pipes without removing a dependency cannot deliver a large win.

Always identify the critical man before interpreting global `r` counts.

## Sweep geometry with functional gates

Integer port spacing is discontinuous: a one-column change can remove an
entire wrap row, change a Voronoi binding band, cross a pipe, or attach a new
room.  Arithmetic estimates are useful only as a pre-filter.

A safe sweep is:

1. generate a new file, never overwrite the champion;
2. reject collisions and load errors;
3. reject boxes above the current limit;
4. run one dominant case with the Rust interpreter;
5. run every public case for survivors;
6. regenerate byte-identically from the committed builder;
7. commit before submission.

Record failures too.  The boundary between a load error, a silent deadlock,
and a valid layout often explains the next useful routing constraint.
