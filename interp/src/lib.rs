//! littleman — a fast reimplementation of the ICFP 2026 reference interpreter.
//!
//! MILESTONE 1: rooms, men, movement, all non-pipe instructions, `Y` fork, man↔man
//! collision, walls, halting/reaping. Pipes / IO rooms / LM-75 display are TODO (pipe
//! ops currently produce a clear `unimpl-pipe` fatal so those programs are skipped by
//! the differential harness rather than silently mis-run).
//!
//! Semantics are pinned against the Go reference (`littleman.wasm`) via differential
//! testing; see sim/difftest.js.

pub mod value;
use value::*;

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
    pub spawned_this_tick: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub enum EndReason {
    Running,
    Done,
    Fatal { reason: String, pos: Pt, cell: char },
    StepCap,
}

pub struct World {
    grid: Vec<Vec<char>>,
    walls: Vec<Vec<bool>>, // structural wall mask (room borders; later: pipe bodies, display borders)
    w: i32,
    h: i32,
    pub runners: Vec<Runner>,
    next_id: u64,
    pub step_count: u64,
    pub end: EndReason,
    pub footprint: i64,
    step_cap: u64,
}

/// Detect room rectangles (+ corners, - top/bottom, | sides) and return their
/// perimeter cells as a wall mask. Interior `+ - |` are NOT walls — they are the
/// add / subtract / or instructions.
fn detect_walls(grid: &[Vec<char>], w: i32, h: i32) -> Vec<Vec<bool>> {
    let mut walls = vec![vec![false; w as usize]; h as usize];
    let at = |x: i32, y: i32| -> char {
        if x < 0 || y < 0 || x >= w || y >= h { '\0' } else { grid[y as usize][x as usize] }
    };
    for y0 in 0..h {
        for x0 in 0..w {
            if at(x0, y0) != '+' { continue; }
            // find top-right corner: '-' run then '+'
            let mut x1 = x0 + 1;
            while at(x1, y0) == '-' { x1 += 1; }
            if x1 <= x0 + 1 || at(x1, y0) != '+' { continue; }
            // find bottom-left corner: '|' run then '+'
            let mut y1 = y0 + 1;
            while at(x0, y1) == '|' { y1 += 1; }
            if y1 <= y0 + 1 || at(x0, y1) != '+' { continue; }
            // verify bottom edge and right edge
            let mut ok = at(x1, y1) == '+';
            for x in (x0 + 1)..x1 { if at(x, y1) != '-' { ok = false; } }
            for y in (y0 + 1)..y1 { if at(x1, y) != '|' { ok = false; } }
            if !ok { continue; }
            // mark perimeter
            for x in x0..=x1 { walls[y0 as usize][x as usize] = true; walls[y1 as usize][x as usize] = true; }
            for y in y0..=y1 { walls[y as usize][x0 as usize] = true; walls[y as usize][x1 as usize] = true; }
        }
    }
    walls
}

impl World {
    /// Parse a program (array of row strings) into a World. Short rows are space-padded
    /// to the widest line, matching the reference loader.
    pub fn load(rows: &[String], step_cap: u64) -> World {
        let w = rows.iter().map(|r| r.chars().count()).max().unwrap_or(0) as i32;
        let h = rows.len() as i32;
        let mut grid = vec![vec![' '; w as usize]; h as usize];
        for (y, r) in rows.iter().enumerate() {
            for (x, c) in r.chars().enumerate() {
                grid[y][x] = c;
            }
        }
        // Men: every '@' becomes a runner facing east; ids assigned in reading order.
        let mut runners = vec![];
        let mut next_id = 0u64;
        for y in 0..h {
            for x in 0..w {
                if grid[y as usize][x as usize] == '@' {
                    runners.push(Runner {
                        id: next_id, pos: (x, y), dir: (1, 0),
                        a: 0, b: 0, bp: 0, halted: false, spawned_this_tick: false,
                    });
                    next_id += 1;
                }
            }
        }
        // Footprint = max(width,height)^2 of the bounding box of all non-space cells.
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
        let walls = detect_walls(&grid, w, h);
        World { grid, walls, w, h, runners, next_id, step_count: 0, end: EndReason::Running, footprint, step_cap }
    }

    #[inline]
    fn cell(&self, x: i32, y: i32) -> char {
        if x < 0 || y < 0 || x >= self.w || y >= self.h { '\0' }
        else { self.grid[y as usize][x as usize] }
    }
    #[inline]
    fn is_wall(&self, x: i32, y: i32) -> bool {
        if x < 0 || y < 0 || x >= self.w || y >= self.h { true }
        else { self.walls[y as usize][x as usize] }
    }

    fn fatal(&mut self, reason: &str, pos: Pt) {
        let cell = self.cell(pos.0, pos.1);
        self.end = EndReason::Fatal { reason: reason.into(), pos, cell };
    }

    /// If any runner is standing on a wall cell, raise a fatal `wall` at the first such
    /// runner (id order), halt every runner in place, and return true.
    fn wall_scan(&mut self) -> bool {
        let hit = self.runners.iter().find(|r| self.is_wall(r.pos.0, r.pos.1)).map(|r| r.pos);
        if let Some(pos) = hit {
            self.fatal("wall", pos);
            for r in &mut self.runners { r.halted = true; }
            true
        } else {
            false
        }
    }

    /// Advance one tick. Returns after updating `self`.
    pub fn step(&mut self) {
        if self.end != EndReason::Running { return; }

        // Reap men that halted on a previous tick.
        self.runners.retain(|r| !r.halted);
        for r in &mut self.runners { r.spawned_this_tick = false; }
        if self.runners.is_empty() {
            self.end = EndReason::Done;
            return;
        }

        // Top-of-tick wall fault: a man that MOVED onto a wall last tick faults now,
        // in place. (Movement itself does not forbid stepping onto a border cell.)
        if self.wall_scan() { return; }

        // ---- EXECUTE ---- (reading-order / ascending-id; see OPEN question in docs)
        let mut spawns: Vec<Runner> = vec![];
        let n = self.runners.len();
        for i in 0..n {
            if self.runners[i].halted { continue; }
            let (x, y) = self.runners[i].pos;
            let ch = self.cell(x, y);
            let dir = self.runners[i].dir;
            let r = &mut self.runners[i];
            match ch {
                '@' | '.' | ' ' => {}
                '>' => r.dir = (1, 0),
                '<' => r.dir = (-1, 0),
                '^' => r.dir = (0, -1),
                'v' | 'V' => r.dir = (0, 1),
                'H' => r.halted = true,
                'M' => r.b = r.a,
                'W' => std::mem::swap(&mut r.a, &mut r.b),
                '+' => r.a = add(r.a, r.b),
                '-' => r.a = sub(r.a, r.b),
                '*' => r.a = mul(r.a, r.b),
                'N' => r.a = neg(r.a),
                '/' => { let (q, rem) = divmod(r.a, r.b); r.a = q; r.b = rem; }
                '%' => r.a = fmod(r.a, r.b),
                '&' => r.a = and(r.a, r.b),
                '|' => r.a = or(r.a, r.b),
                '~' => r.a = xor(r.a, r.b),
                '{' => r.a = shl(r.a, r.b),
                '}' => r.a = ashr(r.a, r.b),
                'X' => { if r.a > 0 { r.dir = rot_cw(dir); } else if r.a < 0 { r.dir = rot_ccw(dir); } }
                'b' => r.bp = r.a,
                'm' => r.bp = r.bp.wrapping_sub(1),
                'd' => { if r.bp > 0 { r.dir = rot_cw(dir); } }
                'a' => { if r.bp > 0 { r.dir = rot_ccw(dir); } }
                'x' => { r.dir = if r.bp & 1 == 1 { rot_cw(dir) } else { rot_ccw(dir) }; }
                ']' => r.bp = ashr1(r.bp),
                '0'..='9' => r.a = (ch as i64) - ('0' as i64),
                'Y' => {
                    let ccw = rot_ccw(dir);
                    let spawn_pos = (x + ccw.0, y + ccw.1);
                    let clone = Runner {
                        id: 0, // assigned below
                        pos: spawn_pos, dir: ccw,
                        a: r.a, b: r.b, bp: r.bp, halted: false, spawned_this_tick: true,
                    };
                    r.dir = rot_cw(dir);
                    spawns.push(clone);
                }
                's' | 'S' | 'r' | 'R' | 'U' | 'q' | '`' => {
                    self.fatal("unimpl", (x, y)); // pipes/literals not in milestone 1
                    return;
                }
                _ => { self.fatal("bad-op", (x, y)); return; }
            }
            if self.end != EndReason::Running { return; }
        }
        for mut c in spawns {
            c.id = self.next_id; self.next_id += 1;
            self.runners.push(c);
        }

        // Post-execute wall fault: a fork that placed a copy onto a wall faults THIS
        // tick, before anyone advances (so the parent stays where it forked).
        if self.wall_scan() { return; }

        // ---- MOVE + COLLISION (movement does NOT wall-check) ----
        // Movers: active men that were not spawned this tick.
        let movers: Vec<usize> = (0..self.runners.len())
            .filter(|&i| !self.runners[i].halted && !self.runners[i].spawned_this_tick)
            .collect();

        // Intended targets.
        let mut targets: std::collections::HashMap<Pt, u32> = std::collections::HashMap::new();
        for &i in &movers {
            let r = &self.runners[i];
            let t = (r.pos.0 + r.dir.0, r.pos.1 + r.dir.1);
            *targets.entry(t).or_insert(0) += 1;
        }
        // Current occupancy by runners that will stay put (halted or spawned-this-tick).
        let stationary: std::collections::HashSet<Pt> = self.runners.iter()
            .filter(|r| r.halted || r.spawned_this_tick)
            .map(|r| r.pos)
            .collect();
        // Positions of movers (to detect swaps: a target occupied by a mover heading into me).
        let mover_target: std::collections::HashMap<Pt, Pt> = movers.iter()
            .map(|&i| {
                let r = &self.runners[i];
                (r.pos, (r.pos.0 + r.dir.0, r.pos.1 + r.dir.1))
            })
            .collect();

        // Decide, per mover, move vs collision-halt; then wall-check the ones that move.
        let mut to_halt: Vec<usize> = vec![];
        let mut to_move: Vec<(usize, Pt)> = vec![];
        for &i in &movers {
            let r = &self.runners[i];
            let t = (r.pos.0 + r.dir.0, r.pos.1 + r.dir.1);
            let conflict = targets.get(&t).copied().unwrap_or(0) > 1
                || stationary.contains(&t)
                || matches!(mover_target.get(&t), Some(&tt) if tt == r.pos); // swap (conservative: both halt)
            if conflict { to_halt.push(i); } else { to_move.push((i, t)); }
        }
        for i in to_halt { self.runners[i].halted = true; }
        for (i, t) in to_move { self.runners[i].pos = t; }

        self.step_count += 1;
        if self.runners.iter().all(|r| r.halted) {
            self.end = EndReason::Done;
        } else if self.step_count >= self.step_cap {
            self.end = EndReason::StepCap;
        }
    }

    /// Runners sorted by id (matches oracle snapshot ordering).
    pub fn snapshot_runners(&self) -> Vec<&Runner> {
        let mut v: Vec<&Runner> = self.runners.iter().collect();
        v.sort_by_key(|r| r.id);
        v
    }
}
