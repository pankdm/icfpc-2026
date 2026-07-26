//! littleman — a fast reimplementation of the ICFP 2026 reference interpreter.
//!
//! Semantics are pinned against the Go reference (`littleman.wasm`) via differential
//! testing; see sim/difftest.js. Covers: rooms, men, movement, all instructions,
//! `Y` fork, collisions, walls, reaping, pipes (FIFO transport + s/S/r/R/U/q),
//! IO rooms, numeric literals, LM-75 display, round gating and judging.

pub mod value;
use value::*;
use std::collections::{HashMap, HashSet};

const MAX_LIVE_RUNNERS: usize = 65_536;

pub type Pt = (i32, i32); // (x, y) = (col, row)

#[inline]
fn rot_cw(d: Pt) -> Pt { (-d.1, d.0) }
#[inline]
fn rot_ccw(d: Pt) -> Pt { (d.1, -d.0) }

#[derive(Clone, Debug)]
pub struct Runner {
    pub id: u64,
    pub pos: Pt,
    pub dir: Pt,
    pub a: Val,
    pub b: Val,
    pub bp: Val,
    pub halted: bool,
    pub blocked: bool,          // parked on a pipe op this tick (stays active)
    pub spawned_this_tick: bool,
    pub room: usize,            // index into World.rooms
}

#[derive(Clone, Debug, PartialEq)]
pub enum EndReason {
    Running,
    Done,
    Fatal { reason: String, pos: Pt, cell: char },
    StepCap,
    LoadError { message: String },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RoomKind { Normal, Input, Output, Display }

#[derive(Clone, Debug)]
pub struct Room {
    pub id: u64,
    pub min: Pt,
    pub max: Pt,
    pub kind: RoomKind,
    pub display: Option<usize>, // index into World.displays
}

impl Room {
    #[inline]
    fn on_border(&self, x: i32, y: i32) -> bool {
        (x == self.min.0 || x == self.max.0 || y == self.min.1 || y == self.max.1)
            && x >= self.min.0 && x <= self.max.0 && y >= self.min.1 && y <= self.max.1
    }
    #[inline]
    fn interior_contains(&self, x: i32, y: i32) -> bool {
        x > self.min.0 && x < self.max.0 && y > self.min.1 && y < self.max.1
    }
}

#[derive(Clone, Debug)]
pub struct Pipe {
    pub id: u64,
    pub path: Vec<Pt>,           // path[0] = source end, path[last] = dest end
    pub values: Vec<Option<i64>>,// one slot per path cell
    occupied: Vec<usize>,        // occupied indices, strictly ascending
    pub src_room: usize,         // index into World.rooms
    pub dst_room: usize,
}

impl Pipe {
    #[inline]
    fn count(&self) -> i64 { self.occupied.len() as i64 }
    #[inline]
    pub fn src_cell(&self) -> Pt { self.path[0] }
    #[inline]
    pub fn dst_cell(&self) -> Pt { *self.path.last().unwrap() }
    #[inline]
    fn push(&mut self, value: i64) -> bool {
        if self.values[0].is_some() { return false; }
        self.values[0] = Some(value);
        self.occupied.insert(0, 0);
        true
    }
    #[inline]
    fn pop(&mut self) -> Option<i64> {
        let last = self.values.len() - 1;
        if self.occupied.last().copied() != Some(last) { return None; }
        self.occupied.pop();
        self.values[last].take()
    }
    fn transport(&mut self) {
        for occupied_index in (0..self.occupied.len()).rev() {
            let position = self.occupied[occupied_index];
            if position + 1 < self.values.len() && self.values[position + 1].is_none() {
                self.values[position + 1] = self.values[position].take();
                self.occupied[occupied_index] += 1;
            }
        }
    }
}

#[derive(Clone, Debug)]
pub enum DisplaySide { Addr, Data, Swap }

#[derive(Clone, Debug)]
pub struct Display {
    pub id: u64,
    pub room: usize,
    pub w: i32,
    pub h: i32,
    pub cursor: i64,
    pub cur: Vec<u8>,   // committed buffer (colors 0-15), row-major
    pub next: Vec<u8>,  // working buffer
    // pipe indices (into World.pipes) attached to each side, if any
    pub addr_pipe: Option<usize>,
    pub data_pipe: Option<usize>,
    pub swap_pipe: Option<usize>,
    pub frames: Vec<Vec<u8>>, // committed frames in order
}

pub struct World {
    grid: Vec<Vec<char>>,
    w: i32,
    h: i32,
    walls: Vec<Vec<bool>>,       // room perimeters (fatal to stand on)
    pipe_cells: HashMap<Pt, usize>, // pipe-glyph cell -> pipe index (informational)
    // literal lookup: for a backtick cell, value if it is the CLOSING backtick when moving in dir d.
    lit_close: HashMap<(Pt, Pt), i64>, // (backtick_cell, dir) -> value
    lit_content: HashSet<Pt>,          // digit/space cells strictly between paired backticks (nop when walked)
    pub rooms: Vec<Room>,
    pub pipes: Vec<Pipe>,
    pub displays: Vec<Display>,
    pub runners: Vec<Runner>,
    next_id: u64,
    pub step_count: u64,
    pub end: EndReason,
    pub footprint: i64,
    step_cap: u64,
    pub output: Vec<i64>,
    pub executed: HashMap<char, u64>,
    pub room_exec: Vec<u64>,
    pub room_glyph: HashMap<(usize, char), u64>,
    pub executed_cells: HashMap<Pt, u64>,

    // IO / rounds
    input_tokens: Vec<i64>,      // flattened across all rounds
    round_in_end: Vec<usize>,    // cumulative input token count at end of each round
    round_out_end: Vec<usize>,   // cumulative expected output count at end of each round
    released_round: usize,       // rounds 0..=released_round have released input
    input_read: usize,           // tokens fed into input pipe so far
    input_pipe: Option<usize>,
    output_pipe: Option<usize>,

    // judging
    expected: Vec<i64>,
    expected_frames: Vec<u8>, // flattened frame pixels (each frame = w*h bytes)
    round_frame_end: Vec<usize>, // cumulative expected frames per round (display gating)
    frame_w: i32,
    frame_h: i32,
    pub frame_mismatch: Option<usize>, // index of first mismatching committed frame
    pub frame_matched: usize,          // count of leading committed frames that matched
    pub frame_mismatch_got: Option<Vec<u8>>,
    is_display_judged: bool,
}

// ------------------------------------------------------------------------------------
// Loading / topology
// ------------------------------------------------------------------------------------

fn is_arrow(c: char) -> bool { matches!(c, '>' | '<' | '^' | 'v') }
fn arrow_dir(c: char) -> Pt {
    match c { '>' => (1, 0), '<' => (-1, 0), '^' => (0, -1), 'v' => (0, 1), _ => (0, 0) }
}

impl World {
    pub fn load_simple(rows: &[String], step_cap: u64) -> World {
        World::load(rows, "", "", "", step_cap)
    }

    /// Parse a program. `input`/`expected` are '/'-separated rounds of whitespace-separated
    /// ints; `frames` is a JSON-ish array of frames (each an array of hex-digit row strings).
    pub fn load(rows: &[String], input: &str, expected: &str, frames: &str, step_cap: u64) -> World {
        let w = rows.iter().map(|r| r.chars().count()).max().unwrap_or(0) as i32;
        let h = rows.len() as i32;
        let mut grid = vec![vec![' '; w as usize]; h as usize];
        for (y, r) in rows.iter().enumerate() {
            for (x, c) in r.chars().enumerate() {
                grid[y][x] = c;
            }
        }

        // footprint = max(w,h)^2 of bounding box of non-space cells.
        let (mut minx, mut miny, mut maxx, mut maxy) = (i32::MAX, i32::MAX, i32::MIN, i32::MIN);
        for y in 0..h {
            for x in 0..w {
                if grid[y as usize][x as usize] != ' ' {
                    minx = minx.min(x); maxx = maxx.max(x);
                    miny = miny.min(y); maxy = maxy.max(y);
                }
            }
        }
        let footprint = if maxx < minx { 0 } else {
            let bw = (maxx - minx + 1) as i64;
            let bh = (maxy - miny + 1) as i64;
            let m = bw.max(bh);
            m * m
        };

        let mut world = World {
            grid, w, h,
            walls: vec![vec![false; w as usize]; h as usize],
            pipe_cells: HashMap::new(),
            lit_close: HashMap::new(),
            lit_content: HashSet::new(),
            rooms: vec![], pipes: vec![], displays: vec![], runners: vec![],
            next_id: 0, step_count: 0, end: EndReason::Running, footprint, step_cap,
            output: vec![],
            executed: HashMap::new(), room_exec: vec![], room_glyph: HashMap::new(),
            executed_cells: HashMap::new(),
            input_tokens: vec![], round_in_end: vec![], round_out_end: vec![],
            released_round: 0, input_read: 0, input_pipe: None, output_pipe: None,
            expected: vec![], expected_frames: vec![], round_frame_end: vec![], frame_w: 0, frame_h: 0,
            frame_mismatch: None, frame_matched: 0, frame_mismatch_got: None, is_display_judged: false,
        };

        // Parse rounds
        world.parse_rounds(input, expected, frames);

        if let Err(msg) = world.build_topology() {
            world.end = EndReason::LoadError { message: msg };
        }
        world.room_exec.resize(world.rooms.len(), 0);
        world
    }

    fn parse_rounds(&mut self, input: &str, expected: &str, frames: &str) {
        // input rounds
        let in_rounds: Vec<&str> = if input.is_empty() { vec![] } else { input.split('/').collect() };
        let mut cum = 0usize;
        for r in &in_rounds {
            for tok in r.split_whitespace() {
                if let Ok(v) = tok.parse::<i64>() { self.input_tokens.push(v); cum += 1; }
            }
            self.round_in_end.push(cum);
        }
        // expected rounds
        let ex_rounds: Vec<&str> = if expected.is_empty() { vec![] } else { expected.split('/').collect() };
        let mut cumo = 0usize;
        for r in &ex_rounds {
            for tok in r.split_whitespace() {
                if let Ok(v) = tok.parse::<i64>() { self.expected.push(v); cumo += 1; }
            }
            self.round_out_end.push(cumo);
        }
        // ensure round_out_end has as many entries as input rounds for gating; pad
        while self.round_out_end.len() < self.round_in_end.len() {
            self.round_out_end.push(cumo);
        }
        // frames (JSON): array of frames, each an array of strings of hex digits
        if !frames.trim().is_empty() {
            if let Some((fw, fh, flat, per_round)) = parse_frames_rounds(frames) {
                self.frame_w = fw; self.frame_h = fh;
                self.expected_frames = flat;
                self.round_frame_end = per_round;
                self.is_display_judged = true;
            }
        }
    }

    fn build_topology(&mut self) -> Result<(), String> {
        // 1. Find rooms (rectangles). Two kinds: normal (+ - |) and display (+ = :).
        self.find_rooms()?;
        if self.rooms.is_empty() {
            return Err("program has no rooms — draw a room around your little men".into());
        }

        // 2. Mark walls (all room perimeters).
        for r in &self.rooms {
            for x in r.min.0..=r.max.0 {
                self.walls[r.min.1 as usize][x as usize] = true;
                self.walls[r.max.1 as usize][x as usize] = true;
            }
            for y in r.min.1..=r.max.1 {
                self.walls[y as usize][r.min.0 as usize] = true;
                self.walls[y as usize][r.max.0 as usize] = true;
            }
        }

        // 3. Assign IDs: runners (reading order of '@') first.
        //    But we need room membership for runners. Validate one '@' per room.
        self.place_runners()?;

        // 4. Assign IDs to non-display rooms (reading order; rooms already in reading order).
        for r in self.rooms.iter_mut() {
            if r.kind != RoomKind::Display { r.id = self.next_id; self.next_id += 1; }
        }

        // 5. Displays: counted after normal rooms, before pipes. The display room's id
        //    IS the display id (a single entity).
        self.build_displays()?;

        // 6. Parse pipes.
        self.find_pipes()?;

        // 7. Validate IO rooms & wire input/output pipes.
        self.wire_io()?;

        // 8. Numeric literals.
        self.parse_literals()?;

        Ok(())
    }

    fn at(&self, x: i32, y: i32) -> char {
        if x < 0 || y < 0 || x >= self.w || y >= self.h { '\0' }
        else { self.grid[y as usize][x as usize] }
    }

    fn find_rooms(&mut self) -> Result<(), String> {
        let w = self.w; let h = self.h;
        let mut claimed = vec![vec![false; w as usize]; h as usize];
        let mut rooms: Vec<Room> = vec![];
        for y0 in 0..h {
            for x0 in 0..w {
                if self.at(x0, y0) != '+' { continue; }
                // Try both wall styles.
                for &(hchar, vchar, kind) in &[('-', '|', RoomKind::Normal), ('=', ':', RoomKind::Display)] {
                    // top edge: run of hchar then '+'
                    let mut x1 = x0 + 1;
                    while self.at(x1, y0) == hchar { x1 += 1; }
                    if x1 <= x0 + 1 || self.at(x1, y0) != '+' { continue; }
                    // left edge: run of vchar then '+'
                    let mut y1 = y0 + 1;
                    while self.at(x0, y1) == vchar { y1 += 1; }
                    if y1 <= y0 + 1 || self.at(x0, y1) != '+' { continue; }
                    // verify bottom & right edges + corner
                    if self.at(x1, y1) != '+' { continue; }
                    let mut ok = true;
                    for x in (x0 + 1)..x1 { if self.at(x, y1) != hchar { ok = false; break; } }
                    if ok { for y in (y0 + 1)..y1 { if self.at(x1, y) != vchar { ok = false; break; } } }
                    if !ok { continue; }
                    // shared-wall quirk: if any border cell already claimed by another room, skip.
                    let mut overlaps = false;
                    'ck: for x in x0..=x1 {
                        for &yy in &[y0, y1] {
                            if claimed[yy as usize][x as usize] { overlaps = true; break 'ck; }
                        }
                    }
                    if !overlaps {
                        'ck2: for y in y0..=y1 {
                            for &xx in &[x0, x1] {
                                if claimed[y as usize][xx as usize] { overlaps = true; break 'ck2; }
                            }
                        }
                    }
                    if overlaps { break; }
                    // claim perimeter
                    for x in x0..=x1 { claimed[y0 as usize][x as usize] = true; claimed[y1 as usize][x as usize] = true; }
                    for y in y0..=y1 { claimed[y as usize][x0 as usize] = true; claimed[y as usize][x1 as usize] = true; }
                    rooms.push(Room { id: 0, min: (x0, y0), max: (x1, y1), kind, display: None });
                    break;
                }
            }
        }
        self.rooms = rooms;
        // classify IO rooms by interior content
        let mut io_class: Vec<Option<RoomKind>> = vec![None; self.rooms.len()];
        for (i, r) in self.rooms.iter().enumerate() {
            if r.kind == RoomKind::Display { continue; }
            let mut has_i = 0; let mut has_o = 0;
            for y in (r.min.1 + 1)..r.max.1 {
                for x in (r.min.0 + 1)..r.max.0 {
                    match self.at(x, y) { 'I' => has_i += 1, 'O' => has_o += 1, _ => {} }
                }
            }
            if has_i > 0 && has_o == 0 {
                if has_i > 1 { return Err("multiple I".into()); }
                io_class[i] = Some(RoomKind::Input);
            } else if has_o > 0 && has_i == 0 {
                if has_o > 1 { return Err("multiple O".into()); }
                io_class[i] = Some(RoomKind::Output);
            } else if has_i > 0 && has_o > 0 {
                return Err("mixed IO room".into());
            }
        }
        // at most one input, one output room
        let inputs = io_class.iter().filter(|c| **c == Some(RoomKind::Input)).count();
        let outputs = io_class.iter().filter(|c| **c == Some(RoomKind::Output)).count();
        if inputs > 1 { return Err("multiple input rooms".into()); }
        if outputs > 1 { return Err("multiple output rooms".into()); }
        for (i, c) in io_class.into_iter().enumerate() {
            if let Some(k) = c { self.rooms[i].kind = k; }
        }
        // IO room size must be 3x3 (interior 1x1)
        for r in &self.rooms {
            if matches!(r.kind, RoomKind::Input | RoomKind::Output) {
                if r.max.0 - r.min.0 != 2 || r.max.1 - r.min.1 != 2 {
                    return Err("IO room not 3x3".into());
                }
            }
        }
        Ok(())
    }

    fn place_runners(&mut self) -> Result<(), String> {
        // map each cell to room index (interior)
        let mut runners = vec![];
        let mut per_room: HashMap<usize, u32> = HashMap::new();
        for y in 0..self.h {
            for x in 0..self.w {
                if self.at(x, y) == '@' {
                    let room = self.room_at(x, y);
                    match room {
                        Some(ri) => {
                            *per_room.entry(ri).or_insert(0) += 1;
                            if per_room[&ri] > 1 {
                                let r = &self.rooms[ri];
                                return Err(format!(
                                    "room {} {:?}..{:?} has multiple '@'s (latest at {},{})",
                                    ri, r.min, r.max, x, y
                                ));
                            }
                            runners.push(Runner {
                                id: self.next_id, pos: (x, y), dir: (1, 0),
                                a: 0, b: 0, bp: 0, halted: false, blocked: false,
                                spawned_this_tick: false, room: ri,
                            });
                            self.next_id += 1;
                        }
                        // A '@' not inside any recognized room is silently dropped
                        // (e.g. the man of a room lost to the shared-wall quirk).
                        None => {}
                    }
                }
            }
        }
        self.runners = runners;
        Ok(())
    }

    fn room_at(&self, x: i32, y: i32) -> Option<usize> {
        for (i, r) in self.rooms.iter().enumerate() {
            if r.interior_contains(x, y) { return Some(i); }
        }
        None
    }
    fn border_room(&self, x: i32, y: i32) -> Option<usize> {
        for (i, r) in self.rooms.iter().enumerate() {
            if r.on_border(x, y) { return Some(i); }
        }
        None
    }

    fn find_pipes(&mut self) -> Result<(), String> {
        // Gather pipe-glyph cells outside rooms.
        let mut is_pipe_glyph = |x: i32, y: i32| -> bool {
            let c = self.at(x, y);
            if !(is_arrow(c) || c == '-' || c == '|') { return false; }
            // Not part of a room perimeter (walls) — those are room borders / instructions.
            if x < 0 || y < 0 || x >= self.w || y >= self.h { return false; }
            !self.walls[y as usize][x as usize] && self.room_at(x, y).is_none()
        };
        // collect arrowheads that are pipe starts (backward cell is a room border)
        let mut pipes: Vec<Pipe> = vec![];
        let mut used: HashSet<Pt> = HashSet::new();
        // reading order over start arrowheads
        for y in 0..self.h {
            for x in 0..self.w {
                let c = self.at(x, y);
                if !is_arrow(c) { continue; }
                if !is_pipe_glyph(x, y) { continue; }
                let d = arrow_dir(c);
                let back = (x - d.0, y - d.1);
                // start if backward cell is a room border and forward is a pipe cell (or another arrow)
                let src_room = self.border_room(back.0, back.1);
                if src_room.is_none() { continue; }
                if used.contains(&(x, y)) { continue; }
                // trace
                let (path, dst_room) = self.trace_pipe(x, y, d, &mut is_pipe_glyph)?;
                if path.len() < 2 { return Err("pipe too short".into()); }
                let dst_room = dst_room.ok_or_else(|| "pipe does not end at a room".to_string())?;
                let sr = src_room.unwrap();
                if sr == dst_room { return Err("pipe self-loop".into()); }
                for &p in &path { used.insert(p); }
                let n = path.len();
                pipes.push(Pipe {
                    id: 0,
                    path,
                    values: vec![None; n],
                    occupied: vec![],
                    src_room: sr,
                    dst_room,
                });
            }
        }
        // record pipe cells + assign ids (reading order = order discovered above is reading order of starts)
        for (i, p) in pipes.iter_mut().enumerate() {
            p.id = self.next_id; self.next_id += 1;
            for &c in &p.path { self.pipe_cells.insert(c, i); }
        }
        self.pipes = pipes;
        Ok(())
    }

    fn trace_pipe(
        &self,
        sx: i32, sy: i32, sdir: Pt,
        is_pipe_glyph: &mut impl FnMut(i32, i32) -> bool,
    ) -> Result<(Vec<Pt>, Option<usize>), String> {
        let mut path = vec![(sx, sy)];
        let mut pos = (sx, sy);
        let mut dir = sdir;
        loop {
            let nxt = (pos.0 + dir.0, pos.1 + dir.1);
            // forward cell a room border? -> current arrowhead is the end
            if let Some(_) = self.border_room(nxt.0, nxt.1) {
                // current cell must be an arrowhead pointing into the room
                let cc = self.at(pos.0, pos.1);
                if !is_arrow(cc) { return Err("pipe runs into wall".into()); }
                return Ok((path, self.border_room(nxt.0, nxt.1)));
            }
            if !is_pipe_glyph(nxt.0, nxt.1) {
                return Err(format!(
                    "pipe dangling after {:?} heading {:?}; next {:?} is {:?}",
                    pos, dir, nxt, self.at(nxt.0, nxt.1)
                ));
            }
            let cn = self.at(nxt.0, nxt.1);
            path.push(nxt);
            if is_arrow(cn) {
                dir = arrow_dir(cn);
            } else if cn == '-' {
                if dir.1 != 0 {
                    return Err(format!(
                        "wrong pipe body glyph at ({},{}): '-' while moving ({},{})",
                        nxt.0, nxt.1, dir.0, dir.1
                    ));
                }
            } else if cn == '|' {
                if dir.0 != 0 {
                    return Err(format!(
                        "wrong pipe body glyph at ({},{}): '|' while moving ({},{})",
                        nxt.0, nxt.1, dir.0, dir.1
                    ));
                }
            }
            pos = nxt;
            if path.len() > (self.w * self.h) as usize + 4 { return Err("pipe loop".into()); }
        }
    }

    fn build_displays(&mut self) -> Result<(), String> {
        let mut displays = vec![];
        let display_room_idxs: Vec<usize> = self.rooms.iter().enumerate()
            .filter(|(_, r)| r.kind == RoomKind::Display).map(|(i, _)| i).collect();
        for ri in display_room_idxs {
            let (min, max) = (self.rooms[ri].min, self.rooms[ri].max);
            let dw = max.0 - min.0 - 1;
            let dh = max.1 - min.1 - 1;
            if dw < 1 || dh < 1 || dw > 64 || dh > 64 { return Err("display size invalid".into()); }
            let di = displays.len();
            let id = self.next_id; self.next_id += 1;
            self.rooms[ri].id = id; // display room's entity id == its display id
            displays.push(Display {
                id, room: ri, w: dw, h: dh, cursor: 0,
                cur: vec![0; (dw * dh) as usize], next: vec![0; (dw * dh) as usize],
                addr_pipe: None, data_pipe: None, swap_pipe: None, frames: vec![],
            });
            self.rooms[ri].display = Some(di);
        }
        self.displays = displays;
        Ok(())
    }

    fn wire_io(&mut self) -> Result<(), String> {
        // For each pipe, if its src/dst room is Input/Output/Display, wire accordingly.
        // Also validate IO room pipe constraints.
        // Collect per-room attached pipes.
        let mut input_room: Option<usize> = None;
        let mut output_room: Option<usize> = None;
        for (i, r) in self.rooms.iter().enumerate() {
            match r.kind {
                RoomKind::Input => input_room = Some(i),
                RoomKind::Output => output_room = Some(i),
                _ => {}
            }
        }
        // input room: exactly one outgoing pipe, no incoming
        if let Some(ir) = input_room {
            let out: Vec<usize> = self.pipes.iter().enumerate().filter(|(_, p)| p.src_room == ir).map(|(i, _)| i).collect();
            let inc: Vec<usize> = self.pipes.iter().enumerate().filter(|(_, p)| p.dst_room == ir).map(|(i, _)| i).collect();
            if !inc.is_empty() { return Err("input room has incoming pipe".into()); }
            if out.len() > 1 { return Err("input room has multiple pipes".into()); }
            if out.len() == 1 { self.input_pipe = Some(out[0]); }
        }
        if let Some(or) = output_room {
            let out: Vec<usize> = self.pipes.iter().enumerate().filter(|(_, p)| p.src_room == or).map(|(i, _)| i).collect();
            let inc: Vec<usize> = self.pipes.iter().enumerate().filter(|(_, p)| p.dst_room == or).map(|(i, _)| i).collect();
            if !out.is_empty() { return Err("output room has outgoing pipe".into()); }
            if inc.len() > 1 { return Err("output room has multiple pipes".into()); }
            if inc.len() == 1 { self.output_pipe = Some(inc[0]); }
        }
        // Displays: wire pipes by side, validate constraints.
        // Need to precompute pipe attach info first (immutable borrow) then mutate displays.
        let mut wiring: Vec<(usize, DisplaySide, usize)> = vec![]; // (display_idx, side, pipe_idx)
        for di in 0..self.displays.len() {
            let ri = self.displays[di].room;
            let (min, max) = (self.rooms[ri].min, self.rooms[ri].max);
            let mut sides_seen: HashMap<u8, usize> = HashMap::new(); // side -> count
            for (pi, p) in self.pipes.iter().enumerate() {
                // display consumes: incoming pipes only (dst_room == ri)
                if p.dst_room != ri && p.src_room != ri { continue; }
                if p.src_room == ri { return Err("display has outgoing pipe".into()); }
                // determine side by the dst attach cell (path.last forward is the border cell)
                let end = *p.path.last().unwrap();
                let d = {
                    // direction into room = from end toward its forward border cell
                    let fwd = self.border_cell_of_pipe_end(p);
                    (fwd.0 - end.0, fwd.1 - end.1)
                };
                let border = self.border_cell_of_pipe_end(p);
                // corner?
                let is_corner = (border.0 == min.0 || border.0 == max.0) && (border.1 == min.1 || border.1 == max.1);
                if is_corner { return Err("display corner pipe".into()); }
                let side = if border.1 == min.1 && d == (0, 1) { 0u8 /*top ADDR*/ }
                    else if border.0 == min.0 && d == (1, 0) { 1u8 /*left DATA*/ }
                    else if border.1 == max.1 && d == (0, -1) { 2u8 /*bottom SWAP*/ }
                    else if border.0 == max.0 { return Err("display right-side pipe".into()); }
                    else { return Err("display pipe bad side".into()); };
                *sides_seen.entry(side).or_insert(0) += 1;
                if sides_seen[&side] > 1 { return Err("display multiple pipes on a side".into()); }
                let ds = match side { 0 => DisplaySide::Addr, 1 => DisplaySide::Data, _ => DisplaySide::Swap };
                wiring.push((di, ds, pi));
            }
        }
        for (di, side, pi) in wiring {
            match side {
                DisplaySide::Addr => self.displays[di].addr_pipe = Some(pi),
                DisplaySide::Data => self.displays[di].data_pipe = Some(pi),
                DisplaySide::Swap => self.displays[di].swap_pipe = Some(pi),
            }
        }
        Ok(())
    }

    // The room-border cell just beyond a pipe's dst end (the forward cell of the end arrowhead).
    fn border_cell_of_pipe_end(&self, p: &Pipe) -> Pt {
        let end = *p.path.last().unwrap();
        let prev = if p.path.len() >= 2 { p.path[p.path.len() - 2] } else { end };
        let d = (end.0 - prev.0, end.1 - prev.1);
        (end.0 + d.0, end.1 + d.1)
    }

    fn parse_literals(&mut self) -> Result<(), String> {
        // Horizontal literals: per row, backticks; between consecutive backticks the cells must
        // be digits or spaces. Vertical similarly per column.
        // For each closing backtick in a given travel direction, precompute the value.
        // Pre-pass: which backticks participate in a valid vertical pair? A backtick that is
        // the endpoint of a vertical literal routinely shares a row with unrelated horizontal
        // literals (subset-sum's parallel workers); the reference does NOT reject the row when
        // consecutive-row-pairing would span code across such a backtick. So when a horizontal
        // pair has a non-digit between its ends, drop a vertically-paired endpoint and re-pair
        // instead of erroring; only a dirty pair with no vertical excuse is a load error
        // (the reference does reject a standalone `1x2`).
        let mut v_paired: std::collections::HashSet<Pt> = std::collections::HashSet::new();
        for x in 0..self.w {
            let mut vt: Vec<i32> = vec![];
            for y in 0..self.h { if self.at(x, y) == '`' { vt.push(y); } }
            let mut i = 0;
            while i + 1 < vt.len() {
                let (a, b) = (vt[i], vt[i + 1]);
                let mut clean = true;
                for y in (a + 1)..b {
                    let c = self.at(x, y);
                    if c != ' ' && !c.is_ascii_digit() { clean = false; break; }
                }
                if clean { v_paired.insert((x, a)); v_paired.insert((x, b)); i += 2; }
                else { i += 1; }
            }
        }
        // Horizontal.
        for y in 0..self.h {
            let mut ticks: Vec<i32> = vec![];
            for x in 0..self.w { if self.at(x, y) == '`' { ticks.push(x); } }
            // pair consecutively (0,1),(2,3)...
            let mut i = 0;
            while i + 1 < ticks.len() {
                let (a, b) = (ticks[i], ticks[i + 1]);
                let mut dirty = false;
                for x in (a + 1)..b {
                    let c = self.at(x, y);
                    if c != ' ' && !c.is_ascii_digit() { dirty = true; break; }
                }
                if dirty {
                    if v_paired.contains(&(a, y)) { ticks.remove(i); continue; }
                    if v_paired.contains(&(b, y)) { ticks.remove(i + 1); continue; }
                    return Err("non-digit in literal".into());
                }
                let mut digits = String::new();
                for x in (a + 1)..b {
                    let c = self.at(x, y);
                    self.lit_content.insert((x, y));
                    if c == ' ' { continue; }
                    if c.is_ascii_digit() { digits.push(c); }
                    else { return Err("non-digit in literal".into()); }
                }
                // eastward: closing tick = b, value = digits as-is; westward: closing = a, value = reversed
                let east = parse_lit(&digits, false)?;
                let rev: String = digits.chars().rev().collect();
                let west = parse_lit(&rev, false)?;
                let overflow = lit_overflow(&digits) || lit_overflow(&rev);
                if overflow { return Err(format!("numeric literal exceeds i64: {}", digits)); }
                if !digits.is_empty() {
                    self.lit_close.insert(((b, y), (1, 0)), east);
                    self.lit_close.insert(((a, y), (-1, 0)), west);
                }
                i += 2;
            }
            // odd leftover backtick -> unmatched (only error if it has digits adjacent? reference: unmatched backtick = load error)
            // A lone backtick with no partner in either axis is an error; handled after vertical pass.
        }
        // Vertical.
        for x in 0..self.w {
            let mut ticks: Vec<i32> = vec![];
            for y in 0..self.h { if self.at(x, y) == '`' { ticks.push(y); } }
            let mut i = 0;
            while i + 1 < ticks.len() {
                let (a, b) = (ticks[i], ticks[i + 1]);
                // Vertical is NOT symmetric with horizontal. Backticks belonging to two
                // unrelated horizontal literals on different rows routinely share a column,
                // and pairing them vertically spans arbitrary code. Such a pair is simply
                // not a vertical literal; treating it as an error rejects real programs the
                // reference loads (it rejected our own sudoku champion).
                let mut digits = String::new();
                let mut is_literal = true;
                for y in (a + 1)..b {
                    let c = self.at(x, y);
                    if c == ' ' { continue; }
                    if c.is_ascii_digit() { digits.push(c); }
                    else { is_literal = false; break; }
                }
                if !is_literal { i += 1; continue; }
                for y in (a + 1)..b { self.lit_content.insert((x, y)); }
                let south = parse_lit(&digits, false)?;
                let rev: String = digits.chars().rev().collect();
                let north = parse_lit(&rev, false)?;
                if lit_overflow(&digits) || lit_overflow(&rev) {
                    return Err(format!("numeric literal exceeds i64: {}", digits));
                }
                if !digits.is_empty() {
                    self.lit_close.insert(((x, b), (0, 1)), south);
                    self.lit_close.insert(((x, a), (0, -1)), north);
                }
                i += 2;
            }
        }
        // Unmatched backtick detection: a backtick that is neither in a horizontal pair
        // nor a vertical pair is an error.
        for y in 0..self.h {
            for x in 0..self.w {
                if self.at(x, y) != '`' { continue; }
                let in_h = self.lit_close.contains_key(&((x, y), (1, 0)))
                    || self.lit_close.contains_key(&((x, y), (-1, 0)));
                let in_v = self.lit_close.contains_key(&((x, y), (0, 1)))
                    || self.lit_close.contains_key(&((x, y), (0, -1)));
                // Also count membership even for empty literals: recompute pairing membership.
                if !in_h && !in_v && !self.backtick_paired(x, y) {
                    return Err("unmatched backtick".into());
                }
            }
        }
        Ok(())
    }

    fn backtick_paired(&self, x: i32, y: i32) -> bool {
        // horizontal: is there another backtick in the same row that pairs with this one?
        let mut hticks = vec![];
        for xx in 0..self.w { if self.at(xx, y) == '`' { hticks.push(xx); } }
        let hpos = hticks.iter().position(|&c| c == x).unwrap();
        if hticks.len() >= 2 && (hpos / 2) * 2 + 1 < hticks.len() && (hpos % 2 == 0 || hpos % 2 == 1) {
            // paired if it belongs to a full pair
            let pair_index = hpos - (hpos % 2);
            if pair_index + 1 < hticks.len() { return true; }
        }
        let mut vticks = vec![];
        for yy in 0..self.h { if self.at(x, yy) == '`' { vticks.push(yy); } }
        let vpos = vticks.iter().position(|&c| c == y).unwrap();
        if vticks.len() >= 2 {
            let pair_index = vpos - (vpos % 2);
            if pair_index + 1 < vticks.len() { return true; }
        }
        false
    }

    // ------------------------------------------------------------------------------------
    // Simulation
    // ------------------------------------------------------------------------------------

    #[inline]
    fn cell(&self, x: i32, y: i32) -> char { self.at(x, y) }
    #[inline]
    fn is_wall(&self, x: i32, y: i32) -> bool {
        if x < 0 || y < 0 || x >= self.w || y >= self.h { true }
        else { self.walls[y as usize][x as usize] }
    }

    fn fatal(&mut self, reason: &str, pos: Pt) {
        // First fault of a tick wins the reason (systems run in a fixed order; a later
        // system, e.g. the DisplaySystem, must not override an earlier wall fault).
        if self.end != EndReason::Running { return; }
        let cell = self.cell(pos.0, pos.1);
        self.end = EndReason::Fatal { reason: reason.into(), pos, cell };
        // A fatal error ends the whole program: every runner halts in place.
        for r in &mut self.runners { r.halted = true; }
    }

    fn wall_scan(&mut self) -> bool {
        let hit = self.runners.iter().find(|r| self.is_wall(r.pos.0, r.pos.1)).map(|r| r.pos);
        if let Some(pos) = hit {
            self.fatal("wall", pos);
            true
        } else { false }
    }

    pub fn step(&mut self) {
        if self.end != EndReason::Running { return; }

        // Cleanup: reap men that halted on a previous tick.
        self.runners.retain(|r| !r.halted);
        for r in &mut self.runners { r.spawned_this_tick = false; r.blocked = false; }

        // This tick's number (the oracle increments even on the tick a fault is reported).
        self.step_count += 1;

        // Phase 1: pipe transport. (Runs even on the tick a wall fault is reported.)
        self.pipe_transport();
        // Phase 2: IO (emit output, release input).
        self.io_phase();

        // Wall consequence of last tick's move (reported at this tick, after transport/IO).
        // A wall fault does not return early: displays still consume this tick.
        self.wall_scan();

        // Displays consume what arrived at their pipes this tick. This runs after the wall
        // check (a wall fault wins the reason) but BEFORE OpDispatch (a display fault freezes
        // the men before they execute). A display fault never overrides an earlier fatal.
        self.display_consume();

        if self.end == EndReason::Running {
            if self.runners.is_empty() {
                // Draining: no active men, keep ticking pipes/IO until output drains.
                if self.drained() { self.end = EndReason::Done; }
                else if self.step_count >= self.step_cap { self.end = EndReason::StepCap; }
            } else {
                // Phase 3: execute (OpDispatch). Fork-onto-wall / no-pipe / bad-op fatal inline.
                self.execute();
                if self.end == EndReason::Running {
                    // Phase 4: advance + collision.
                    self.advance();
                    let all_halted = self.runners.iter().all(|r| r.halted);
                    if all_halted && self.drained() {
                        self.end = EndReason::Done;
                    } else if self.step_count >= self.step_cap {
                        self.end = EndReason::StepCap;
                    }
                }
            }
        }
    }

    // whether no pending values remain in any consumer pipe (output pipe or a display's
    // addr/data/swap pipe). Values stranded in man-to-man / input pipes do not block Done.
    fn drained(&self) -> bool {
        let mut consumers: Vec<usize> = vec![];
        if let Some(pi) = self.output_pipe { consumers.push(pi); }
        for d in &self.displays {
            for p in [d.addr_pipe, d.data_pipe, d.swap_pipe].into_iter().flatten() { consumers.push(p); }
        }
        consumers.into_iter().all(|pi| self.pipes[pi].occupied.is_empty())
    }

    fn pipe_transport(&mut self) {
        for pipe in &mut self.pipes { pipe.transport(); }
    }

    fn io_phase(&mut self) {
        // emit output first
        if let Some(pi) = self.output_pipe {
            if let Some(v) = self.pipes[pi].pop() {
                self.output.push(v);
            }
        }
        // advance round gating: release next round when current round's expected output emitted
        // A DISPLAY round completes when its frames are committed and matched; it emits no
        // integers, so gating on output.len() releases every round immediately and the
        // program finishes early (measured: 84 ticks per round transition too soon).
        if self.is_display_judged && !self.round_frame_end.is_empty() {
            while self.released_round + 1 < self.round_in_end.len().max(self.round_frame_end.len())
                && self.released_round < self.round_frame_end.len()
                && self.frame_matched >= self.round_frame_end[self.released_round]
            {
                self.released_round += 1;
            }
        } else {
            while self.released_round + 1 < self.round_in_end.len().max(self.round_out_end.len())
                && self.released_round < self.round_out_end.len()
                && self.output.len() >= self.round_out_end[self.released_round]
            {
                self.released_round += 1;
            }
        }
        // feed input into input pipe source cell if free & a released token remains
        if let Some(pi) = self.input_pipe {
            let released = self.released_input_count();
            if self.input_read < released {
                if self.pipes[pi].values[0].is_none() {
                    let v = self.input_tokens[self.input_read];
                    self.pipes[pi].push(v);
                    self.input_read += 1;
                }
            }
        }
    }

    fn released_input_count(&self) -> usize {
        if self.round_in_end.is_empty() { return self.input_tokens.len(); }
        let r = self.released_round.min(self.round_in_end.len() - 1);
        self.round_in_end[r]
    }

    pub fn input_released(&self) -> usize { self.released_input_count() }
    pub fn input_read(&self) -> usize { self.input_read }
    pub fn is_display_judged(&self) -> bool { self.is_display_judged }
    pub fn expected_frame_count(&self) -> usize {
        let fsize = (self.frame_w * self.frame_h) as usize;
        if fsize == 0 { 0 } else { self.expected_frames.len() / fsize }
    }

    fn display_consume(&mut self) {
        // For each display, consume one value from ADDR, DATA, SWAP (in that order) if present
        // at the pipe's dst end.
        for di in 0..self.displays.len() {
            // ADDR
            if let Some(pi) = self.displays[di].addr_pipe {
                if let Some(v) = self.pipes[pi].pop() {
                    let (wd, ht) = (self.displays[di].w as i64, self.displays[di].h as i64);
                    if v < 0 || v >= wd * ht {
                        self.fatal("display-addr", self.pipes[pi].dst_cell());
                        return;
                    }
                    self.displays[di].cursor = v;
                }
            }
            // DATA
            if let Some(pi) = self.displays[di].data_pipe {
                if let Some(v) = self.pipes[pi].pop() {
                    if v < 0 || v > 15 {
                        self.fatal("display-data", self.pipes[pi].dst_cell());
                        return;
                    }
                    let d = &mut self.displays[di];
                    let idx = d.cursor as usize;
                    if idx < d.next.len() { d.next[idx] = v as u8; }
                    let cap = (d.w * d.h) as i64;
                    d.cursor = (d.cursor + 1) % cap;
                }
            }
            // SWAP
            if let Some(pi) = self.displays[di].swap_pipe {
                if let Some(v) = self.pipes[pi].pop() {
                    if v != 0 && v != 1 {
                        self.fatal("display-swap", self.pipes[pi].dst_cell());
                        return;
                    }
                    let d = &mut self.displays[di];
                    d.cur = d.next.clone();
                    let frame = d.cur.clone();
                    d.frames.push(frame);
                    if v == 0 {
                        for c in d.next.iter_mut() { *c = 0; }
                        d.cursor = 0;
                    }
                    // judge frame
                    self.judge_frame(di);
                    if self.end != EndReason::Running { return; }
                }
            }
        }
    }

    fn judge_frame(&mut self, di: usize) {
        if !self.is_display_judged { return; }
        let fw = self.frame_w as usize; let fh = self.frame_h as usize;
        let fsize = fw * fh;
        if fsize == 0 { return; }
        if self.frame_mismatch.is_some() { return; }
        // global committed-frame index (display-judged problems have exactly one display)
        let fi = self.displays.iter().map(|d| d.frames.len()).sum::<usize>() - 1;
        let expected_count = self.expected_frames.len() / fsize;
        let got = self.displays[di].cur.clone();
        let matches = fi < expected_count
            && got.as_slice() == &self.expected_frames[fi * fsize..(fi + 1) * fsize];
        if fi == self.frame_matched && matches {
            self.frame_matched += 1;
        } else {
            self.frame_mismatch = Some(fi);
            self.frame_mismatch_got = Some(got);
        }
    }

    fn execute(&mut self) {
        let n = self.runners.len();
        for i in 0..n {
            if self.runners[i].halted { continue; }
            let (x, y) = self.runners[i].pos;
            let ch = self.cell(x, y);
            let dir = self.runners[i].dir;
            *self.executed.entry(ch).or_insert(0) += 1;
            *self.executed_cells.entry((x, y)).or_insert(0) += 1;
            let room = self.runners[i].room;
            if room < self.room_exec.len() {
                self.room_exec[room] += 1;
            }
            *self.room_glyph.entry((room, ch)).or_insert(0) += 1;
            // literal content cell (digit/space between backticks) -> nop
            if self.lit_content.contains(&(x, y)) { continue; }
            // literal closing?
            if ch == '`' {
                if let Some(&v) = self.lit_close.get(&((x, y), dir)) {
                    self.runners[i].a = v;
                }
                continue;
            }
            match ch {
                '@' | '.' | ' ' | '`' => {}
                '>' => self.runners[i].dir = (1, 0),
                '<' => self.runners[i].dir = (-1, 0),
                '^' => self.runners[i].dir = (0, -1),
                'v' | 'V' => self.runners[i].dir = (0, 1),
                'H' => self.runners[i].halted = true,
                'M' => self.runners[i].b = self.runners[i].a,
                'W' => { let r = &mut self.runners[i]; std::mem::swap(&mut r.a, &mut r.b); }
                '+' => { let r = &mut self.runners[i]; r.a = add(r.a, r.b); }
                '-' => { let r = &mut self.runners[i]; r.a = sub(r.a, r.b); }
                '*' => { let r = &mut self.runners[i]; r.a = mul(r.a, r.b); }
                'N' => self.runners[i].a = neg(self.runners[i].a),
                '/' => { let r = &mut self.runners[i]; let (q, rem) = divmod(r.a, r.b); r.a = q; r.b = rem; }
                '%' => { let r = &mut self.runners[i]; r.a = fmod(r.a, r.b); }
                '&' => { let r = &mut self.runners[i]; r.a = and(r.a, r.b); }
                '|' => { let r = &mut self.runners[i]; r.a = or(r.a, r.b); }
                '~' => { let r = &mut self.runners[i]; r.a = xor(r.a, r.b); }
                '{' => { let r = &mut self.runners[i]; r.a = shl(r.a, r.b); }
                '}' => { let r = &mut self.runners[i]; r.a = ashr(r.a, r.b); }
                'X' => { let a = self.runners[i].a; if a > 0 { self.runners[i].dir = rot_cw(dir); } else if a < 0 { self.runners[i].dir = rot_ccw(dir); } }
                'b' => self.runners[i].bp = self.runners[i].a,
                'm' => self.runners[i].bp = self.runners[i].bp.wrapping_sub(1),
                'd' => { if self.runners[i].bp > 0 { self.runners[i].dir = rot_cw(dir); } }
                'a' => { if self.runners[i].bp > 0 { self.runners[i].dir = rot_ccw(dir); } }
                'x' => { self.runners[i].dir = if self.runners[i].bp & 1 == 1 { rot_cw(dir) } else { rot_ccw(dir) }; }
                ']' => self.runners[i].bp = ashr1(self.runners[i].bp),
                '0'..='9' => self.runners[i].a = (ch as i64) - ('0' as i64),
                'Y' => {
                    let live_count = self.runners.iter().filter(|runner| !runner.halted).count();
                    if live_count >= MAX_LIVE_RUNNERS {
                        self.fatal("man-limit", (x, y));
                        return;
                    }

                    let right_dir = rot_cw(dir);
                    let left_dir = rot_ccw(dir);
                    let right_pos = (x + right_dir.0, y + right_dir.1);
                    let left_pos = (x + left_dir.0, y + left_dir.1);
                    let (id, a, b, bp, room) = {
                        let splitter = &self.runners[i];
                        (splitter.id, splitter.a, splitter.b, splitter.bp, splitter.room)
                    };

                    // Birth order and wall handling are ASYMMETRIC in the reference, and
                    // both traces below were taken from it (sim/otrace.js):
                    //   left(CCW) birth onto a wall  -> fatal on the SPLIT tick, and the
                    //     splitter is still on its own cell (it never reaches right_pos);
                    //   right(CW) birth onto a wall  -> NOT fatal on the split tick; both
                    //     copies are placed, one standing on the wall, and it dies one tick
                    //     later when the wall system runs.
                    // So the left copy is created and wall-checked BEFORE the splitter is
                    // moved, and the right birth is never wall-checked here.
                    // The splitter is turned to the right copy's heading BEFORE the left
                    // birth is resolved, but only MOVED after: on a fatal left birth the
                    // reference leaves it on its own cell already facing the new heading.
                    self.runners[i].dir = right_dir;
                    self.runners[i].spawned_this_tick = true;

                    let left_index = self.runners.len();
                    self.runners.push(Runner {
                        id: self.next_id, pos: left_pos, dir: left_dir,
                        a, b, bp, halted: false, blocked: false, spawned_this_tick: true, room,
                    });
                    self.next_id += 1;

                    if self.is_wall(left_pos.0, left_pos.1) {
                        self.fatal("wall", left_pos);
                        return;
                    }

                    self.runners[i] = Runner {
                        id, pos: right_pos, dir: right_dir,
                        a, b, bp, halted: false, blocked: false, spawned_this_tick: true, room,
                    };

                    for birth_index in [i, left_index] {
                        let birth_pos = self.runners[birth_index].pos;
                        let occupants: Vec<usize> = self.runners.iter().enumerate()
                            .filter(|(_, runner)| !runner.halted && runner.pos == birth_pos)
                            .map(|(index, _)| index)
                            .collect();
                        if occupants.len() > 1 {
                            for occupant in occupants {
                                self.runners[occupant].halted = true;
                            }
                        }
                    }

                    if self.end != EndReason::Running {
                        return;
                    }
                }
                's' => { self.op_send_nearest(i); }
                'S' => { self.op_send_all(i); }
                'r' => { self.op_recv_nearest(i); }
                'R' => { self.op_recv_any(i, false); }
                'U' => { self.op_recv_any(i, true); }
                'q' => { self.op_count(i); }
                _ => { self.fatal("bad-op", (x, y)); return; }
            }
            if self.end != EndReason::Running { return; }
        }
    }

    // Pipes attached to a runner's room.
    fn outgoing_pipes(&self, room: usize) -> Vec<usize> {
        self.pipes.iter().enumerate().filter(|(_, p)| p.src_room == room).map(|(i, _)| i).collect()
    }
    fn incoming_pipes(&self, room: usize) -> Vec<usize> {
        self.pipes.iter().enumerate().filter(|(_, p)| p.dst_room == room).map(|(i, _)| i).collect()
    }

    // nearest outgoing pipe: Manhattan from man cell to pipe source attach (path[0]); tie -> reading order of attach cell.
    fn nearest_outgoing(&self, pos: Pt, room: usize) -> Option<usize> {
        let cands = self.outgoing_pipes(room);
        cands.into_iter().min_by_key(|&pi| {
            let a = self.pipes[pi].src_cell();
            let dist = (a.0 - pos.0).abs() + (a.1 - pos.1).abs();
            (dist, a.1, a.0)
        })
    }
    fn nearest_incoming(&self, pos: Pt, room: usize) -> Option<usize> {
        let cands = self.incoming_pipes(room);
        cands.into_iter().min_by_key(|&pi| {
            let a = self.pipes[pi].dst_cell();
            let dist = (a.0 - pos.0).abs() + (a.1 - pos.1).abs();
            (dist, a.1, a.0)
        })
    }

    fn op_send_nearest(&mut self, i: usize) {
        let (pos, room) = (self.runners[i].pos, self.runners[i].room);
        match self.nearest_outgoing(pos, room) {
            None => { self.fatal("no-pipe", pos); }
            Some(pi) => {
                if self.pipes[pi].values[0].is_none() {
                    self.pipes[pi].push(self.runners[i].a);
                } else {
                    self.runners[i].blocked = true;
                }
            }
        }
    }

    fn op_send_all(&mut self, i: usize) {
        let (pos, room) = (self.runners[i].pos, self.runners[i].room);
        let outs = self.outgoing_pipes(room);
        if outs.is_empty() { self.fatal("no-pipe", pos); return; }
        let all_free = outs.iter().all(|&pi| self.pipes[pi].values[0].is_none());
        if all_free {
            let a = self.runners[i].a;
            for &pi in &outs { self.pipes[pi].push(a); }
        } else {
            self.runners[i].blocked = true;
        }
    }

    fn op_recv_nearest(&mut self, i: usize) {
        let (pos, room) = (self.runners[i].pos, self.runners[i].room);
        match self.nearest_incoming(pos, room) {
            None => { self.fatal("no-pipe", pos); }
            Some(pi) => {
                if let Some(v) = self.pipes[pi].pop() {
                    self.runners[i].a = v;
                } else {
                    self.runners[i].blocked = true;
                }
            }
        }
    }

    fn op_recv_any(&mut self, i: usize, turn_away: bool) {
        let (pos, room) = (self.runners[i].pos, self.runners[i].room);
        let incs = self.incoming_pipes(room);
        if incs.is_empty() { self.fatal("no-pipe", pos); return; }
        // reading order among ready pipes: by dst attach cell reading order
        let mut ready: Vec<usize> = incs.into_iter().filter(|&pi| {
            let last = self.pipes[pi].values.len() - 1;
            self.pipes[pi].values[last].is_some()
        }).collect();
        ready.sort_by_key(|&pi| { let a = self.pipes[pi].dst_cell(); (a.1, a.0) });
        if let Some(&pi) = ready.first() {
            let v = self.pipes[pi].pop().unwrap();
            self.runners[i].a = v;
            if turn_away {
                // "turn away from the pipe that supplied the value" = face the pipe's
                // flow-into-room direction (its end arrowhead direction).
                self.runners[i].dir = self.pipe_flow_dir(pi);
            }
        } else {
            self.runners[i].blocked = true;
        }
    }

    fn pipe_flow_dir(&self, pi: usize) -> Pt {
        let p = &self.pipes[pi];
        let n = p.path.len();
        let end = p.path[n - 1];
        let prev = p.path[n - 2];
        (end.0 - prev.0, end.1 - prev.1)
    }

    fn op_count(&mut self, i: usize) {
        let (pos, room) = (self.runners[i].pos, self.runners[i].room);
        match self.nearest_incoming(pos, room) {
            None => { self.fatal("no-pipe", pos); }
            Some(pi) => { self.runners[i].bp = self.pipes[pi].count(); }
        }
    }

    fn advance(&mut self) {
        let movers: Vec<usize> = (0..self.runners.len())
            .filter(|&i| !self.runners[i].halted && !self.runners[i].spawned_this_tick && !self.runners[i].blocked)
            .collect();
        let mover_set: HashSet<usize> = movers.iter().copied().collect();

        let mut targets: HashMap<Pt, Vec<usize>> = HashMap::new();
        for &i in &movers {
            let r = &self.runners[i];
            let t = (r.pos.0 + r.dir.0, r.pos.1 + r.dir.1);
            targets.entry(t).or_default().push(i);
        }

        let mut colliding: HashSet<usize> = HashSet::new();
        for indices in targets.values() {
            if indices.len() > 1 {
                colliding.extend(indices.iter().copied());
            }
        }

        let mut stationary: HashMap<Pt, Vec<usize>> = HashMap::new();
        for (index, runner) in self.runners.iter().enumerate() {
            if !runner.halted && !mover_set.contains(&index) {
                stationary.entry(runner.pos).or_default().push(index);
            }
        }
        for &i in &movers {
            let r = &self.runners[i];
            let t = (r.pos.0 + r.dir.0, r.pos.1 + r.dir.1);
            if let Some(occupants) = stationary.get(&t) {
                colliding.insert(i);
                colliding.extend(occupants.iter().copied());
            }
        }

        let origins: HashMap<Pt, usize> = movers.iter()
            .map(|&i| (self.runners[i].pos, i))
            .collect();
        for &i in &movers {
            let runner = &self.runners[i];
            let target = (runner.pos.0 + runner.dir.0, runner.pos.1 + runner.dir.1);
            if let Some(&other) = origins.get(&target) {
                let other_runner = &self.runners[other];
                let other_target = (
                    other_runner.pos.0 + other_runner.dir.0,
                    other_runner.pos.1 + other_runner.dir.1,
                );
                if other_target == runner.pos {
                    colliding.insert(i);
                    colliding.insert(other);
                }
            }
        }

        for &i in &movers {
            if colliding.contains(&i) { continue; }
            let runner = &mut self.runners[i];
            runner.pos = (runner.pos.0 + runner.dir.0, runner.pos.1 + runner.dir.1);
        }
        for index in colliding {
            self.runners[index].halted = true;
        }
    }

    pub fn snapshot_runners(&self) -> Vec<&Runner> {
        let mut v: Vec<&Runner> = self.runners.iter().collect();
        v.sort_by_key(|r| r.id);
        v
    }

    // ---- judging ----
    /// Streaming prefix compare: "match" | "diverged" | "extra" | "pending".
    pub fn judge_output(&self) -> &'static str {
        let o = &self.output;
        let e = &self.expected;
        for (i, v) in o.iter().enumerate() {
            if i >= e.len() { return "extra"; }
            if *v != e[i] { return "diverged"; }
        }
        if o.len() == e.len() { "match" } else { "pending" }
    }

    pub fn output_settled(&self) -> bool {
        if self.is_display_judged {
            let fsize = (self.frame_w * self.frame_h) as usize;
            if fsize == 0 { return false; }
            let total = self.expected_frames.len() / fsize;
            self.frame_mismatch.is_none() && self.frame_matched >= total && total > 0
        } else {
            // Empty expected never "settles" early: the run continues to halt, then a
            // program that emitted anything is judged `extra` (fail).
            !self.expected.is_empty() && self.judge_output() == "match"
        }
    }
}

fn parse_lit(digits: &str, _rev: bool) -> Result<i64, String> {
    if digits.is_empty() { return Ok(0); }
    match digits.parse::<i64>() {
        Ok(v) => Ok(v),
        Err(_) => Ok(0), // overflow handled separately
    }
}
fn lit_overflow(digits: &str) -> bool {
    if digits.is_empty() { return false; }
    digits.parse::<i64>().is_err()
}

// Parse frames JSON. The oracle wants rounds x frames x rows ([][][]string); we also accept
// frames x rows ([][]string). We collect every innermost array-of-strings as a frame, in order.
// Also returns the CUMULATIVE frame count per round. The judged frames are flattened for
// comparison, but round gating needs to know where each round's frames end (see the gate in
// io_phase): a display round is finished when its frames are committed, not when integers
// are emitted -- display programs emit no integers at all.
fn parse_frames_rounds(s: &str) -> Option<(i32, i32, Vec<u8>, Vec<usize>)> {
    let val = serde_frames::parse(s)?;
    let mut per_round: Vec<usize> = vec![];
    if let serde_frames::Val::Arr(rounds) = &val {
        for r in rounds {
            let mut fr: Vec<Vec<String>> = vec![];
            serde_frames::collect_frames(r, &mut fr);
            per_round.push(fr.len());
        }
    }
    let mut cum = 0usize;
    let round_frame_end: Vec<usize> = per_round.iter().map(|n| { cum += n; cum }).collect();
    let (w, h, flat) = parse_frames(s)?;
    Some((w, h, flat, round_frame_end))
}

fn parse_frames(s: &str) -> Option<(i32, i32, Vec<u8>)> {
    let val = serde_frames::parse(s)?;
    let mut frames: Vec<Vec<String>> = vec![];
    serde_frames::collect_frames(&val, &mut frames);
    if frames.is_empty() { return None; }
    let fh = frames[0].len() as i32;
    if fh == 0 { return None; }
    let fw = frames[0][0].chars().count() as i32;
    let mut flat = vec![];
    for frame in &frames {
        for row in frame {
            for c in row.chars() {
                let d = c.to_digit(16).unwrap_or(0) as u8;
                flat.push(d);
            }
        }
    }
    Some((fw, fh, flat))
}

mod serde_frames {
    // A tiny JSON value: only arrays and strings are needed.
    pub enum Val { Arr(Vec<Val>), Str(String) }

    pub fn parse(s: &str) -> Option<Val> {
        let b = s.as_bytes();
        let mut i = 0usize;
        let v = parse_val(b, &mut i)?;
        Some(v)
    }
    fn parse_val(b: &[u8], i: &mut usize) -> Option<Val> {
        skip_ws(b, i);
        if *i >= b.len() { return None; }
        match b[*i] {
            b'[' => {
                *i += 1;
                let mut arr = vec![];
                loop {
                    skip_ws(b, i);
                    if *i < b.len() && b[*i] == b']' { *i += 1; break; }
                    let v = parse_val(b, i)?;
                    arr.push(v);
                    skip_ws(b, i);
                    if *i < b.len() && b[*i] == b',' { *i += 1; }
                }
                Some(Val::Arr(arr))
            }
            b'"' => {
                *i += 1;
                let start = *i;
                while *i < b.len() && b[*i] != b'"' { *i += 1; }
                let s = String::from_utf8_lossy(&b[start..*i]).to_string();
                *i += 1;
                Some(Val::Str(s))
            }
            _ => None,
        }
    }
    // Collect every array whose elements are all strings, as a frame (list of row strings).
    pub fn collect_frames(v: &Val, out: &mut Vec<Vec<String>>) {
        if let Val::Arr(items) = v {
            if !items.is_empty() && items.iter().all(|x| matches!(x, Val::Str(_))) {
                let frame: Vec<String> = items.iter().map(|x| match x { Val::Str(s) => s.clone(), _ => String::new() }).collect();
                out.push(frame);
            } else {
                for x in items { collect_frames(x, out); }
            }
        }
    }
    fn skip_ws(b: &[u8], i: &mut usize) {
        while *i < b.len() && (b[*i] == b' ' || b[*i] == b'\n' || b[*i] == b'\t' || b[*i] == b'\r') { *i += 1; }
    }
}
