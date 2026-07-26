//! CLI for the littleman interpreter.
//!
//! Default mode: `lm <program.man> [steps] [--input=..] [--expected=..] [--frames=..]`
//!   -> one JSON snapshot per line (step 0..=N or until end), mirroring the WASM oracle so
//!      sim/difftest.js can compare directly.
//!
//! Grade mode: `lm --grade <program.man> [--input=..] [--expected=..] [--frames=..] [--cap=N]`
//!   -> a single JSON verdict: {status, settleTick, footprint}.

use littleman::{World, EndReason, Runner, Pipe, Display};

fn runner_json(r: &Runner) -> String {
    format!(
        "{{\"id\":{},\"pos\":[{},{}],\"dir\":[{},{}],\"halted\":{},\"a\":{},\"b\":{},\"backpack\":{}}}",
        r.id, r.pos.0, r.pos.1, r.dir.0, r.dir.1, r.halted, r.a, r.b, r.bp
    )
}

fn pipe_json(p: &Pipe) -> String {
    let mut vals: Vec<String> = vec![];
    for (i, v) in p.values.iter().enumerate() {
        if let Some(v) = v { vals.push(format!("{{\"index\":{},\"value\":{}}}", i, v)); }
    }
    let values = if vals.is_empty() { "null".to_string() } else { format!("[{}]", vals.join(",")) };
    format!(
        "{{\"id\":{},\"values\":{},\"src\":[{},{}],\"dst\":[{},{}],\"srcRoom\":{},\"dstRoom\":{}}}",
        p.id, values,
        p.src_cell().0, p.src_cell().1, p.dst_cell().0, p.dst_cell().1,
        p.src_room, p.dst_room,
    )
}

fn u8arr(v: &[u8]) -> String {
    format!("[{}]", v.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(","))
}
fn display_json(d: &Display) -> String {
    format!("{{\"id\":{},\"w\":{},\"h\":{},\"front\":{},\"back\":{},\"cursor\":{},\"frames\":{}}}",
        d.id, d.w, d.h, u8arr(&d.cur), u8arr(&d.next), d.cursor, d.frames.len())
}
fn frame_judge_json(w: &World) -> String {
    if !w.is_display_judged() { return "null".to_string(); }
    let total = w.expected_frame_count();
    let mut s = format!("{{\"matched\":{},\"total\":{}", w.frame_matched, total);
    if let Some(idx) = w.frame_mismatch {
        let got = w.frame_mismatch_got.as_ref().map(|g| u8arr(g)).unwrap_or_else(|| "[]".to_string());
        s.push_str(&format!(",\"mismatch\":{{\"index\":{},\"got\":{}}}", idx, got));
    }
    s.push('}');
    s
}

fn snapshot_json(w: &World) -> String {
    let runners: Vec<String> = w.snapshot_runners().iter().map(|r| runner_json(r)).collect();
    let pipes: Vec<String> = w.pipes.iter().map(|p| pipe_json(p)).collect();
    let (end, extra) = match &w.end {
        EndReason::Running => ("running".to_string(), String::new()),
        EndReason::Done => ("done".to_string(), String::new()),
        EndReason::StepCap => ("stepcap".to_string(), String::new()),
        EndReason::LoadError { message } => (
            "loaderror".to_string(),
            format!(",\"loaderror\":{}", json_string(message)),
        ),
        EndReason::Fatal { reason, pos, cell } => (
            "fatal".to_string(),
            format!(",\"fatal\":{{\"reason\":\"{}\",\"pos\":[{},{}],\"cell\":{}}}",
                reason, pos.0, pos.1, serde_char(*cell)),
        ),
    };
    let output = if w.output.is_empty() { "null".to_string() }
        else { format!("[{}]", w.output.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(",")) };
    let pipes_field = if pipes.is_empty() { "null".to_string() } else { format!("[{}]", pipes.join(",")) };
    let displays: Vec<String> = w.displays.iter().map(|d| display_json(d)).collect();
    let displays_field = if displays.is_empty() { "null".to_string() } else { format!("[{}]", displays.join(",")) };
    format!(
        "{{\"step\":{},\"runners\":[{}],\"pipes\":{},\"displays\":{},\"frameJudge\":{},\"output\":{},\"end\":\"{}\",\"footprint\":{},\"inputReleased\":{},\"inputRead\":{}{}}}",
        w.step_count, runners.join(","), pipes_field, displays_field, frame_judge_json(w), output, end, w.footprint,
        w.input_released(), w.input_read(), extra
    )
}

fn json_string(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c { '"' => out.push_str("\\\""), '\\' => out.push_str("\\\\"), '\n' => out.push_str("\\n"), _ => out.push(c) }
    }
    out.push('"');
    out
}

fn serde_char(c: char) -> String {
    if c == '\0' { "\"\\u0000\"".to_string() }
    else if c == '"' || c == '\\' { format!("\"\\{}\"", c) }
    else { format!("\"{}\"", c) }
}

struct Args {
    grade: bool,
    profile: bool,
    inspect: Option<u64>,
    program: String,
    steps: u64,
    input: String,
    expected: String,
    frames: String,
    cap: u64,
}

fn parse_args() -> Args {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let mut a = Args { grade: false, profile: false, inspect: None, program: String::new(), steps: 200, input: String::new(),
        expected: String::new(), frames: String::new(), cap: 5_000_000 };
    let mut positional: Vec<String> = vec![];
    for arg in raw {
        if arg == "--grade" { a.grade = true; }
        else if arg == "--profile" { a.profile = true; a.grade = true; }
        else if let Some(v) = arg.strip_prefix("--inspect=") { a.inspect = v.parse().ok(); }
        else if let Some(v) = arg.strip_prefix("--input=") { a.input = v.to_string(); }
        else if let Some(v) = arg.strip_prefix("--expected=") { a.expected = v.to_string(); }
        else if let Some(v) = arg.strip_prefix("--frames=") { a.frames = v.to_string(); }
        else if let Some(v) = arg.strip_prefix("--frames-file=") { a.frames = std::fs::read_to_string(v).unwrap_or_default(); }
        else if let Some(v) = arg.strip_prefix("--cap=") { a.cap = v.parse().unwrap_or(5_000_000); }
        else { positional.push(arg); }
    }
    if !positional.is_empty() { a.program = positional[0].clone(); }
    if positional.len() > 1 { a.steps = positional[1].parse().unwrap_or(200); }
    a
}

fn main() {
    let args = parse_args();
    if args.program.is_empty() {
        eprintln!("usage: lm [--grade|--inspect=N] <program.man> [steps] [--input=..] [--expected=..] [--frames=..] [--cap=N]");
        std::process::exit(2);
    }
    let src = std::fs::read_to_string(&args.program).expect("read program");
    let rows: Vec<String> = src.lines().map(|l| l.to_string()).collect();

    if let Some(steps) = args.inspect {
        let mut w = World::load(&rows, &args.input, &args.expected, &args.frames, args.cap.max(steps));
        for _ in 0..steps {
            if w.end != EndReason::Running || w.output_settled() { break; }
            w.step();
        }
        println!("{}", snapshot_json(&w));
        return;
    }

    if args.grade {
        run_grade(&args, &rows);
        return;
    }

    let mut w = World::load(&rows, &args.input, &args.expected, &args.frames, args.cap);
    println!("{}", snapshot_json(&w)); // step 0 (or load error)
    if let EndReason::LoadError { .. } = w.end { return; }
    for _ in 0..args.steps {
        if w.end != EndReason::Running { break; }
        w.step();
        println!("{}", snapshot_json(&w));
    }
}

fn run_grade(args: &Args, rows: &[String]) {
    let cap = args.cap;
    let mut w = World::load(rows, &args.input, &args.expected, &args.frames, cap);
    if let EndReason::LoadError { message } = &w.end {
        println!("{{\"status\":\"loaderror\",\"reason\":{}}}", json_string(message));
        return;
    }
    let mut settle_tick: Option<u64> = None;
    loop {
        if w.output_settled() && settle_tick.is_none() { settle_tick = Some(w.step_count); }
        if w.end != EndReason::Running { break; }
        if w.output_settled() { break; }
        w.step();
    }
    if w.output_settled() && settle_tick.is_none() { settle_tick = Some(w.step_count); }

    let tick = settle_tick.unwrap_or(w.step_count);
    let footprint = w.footprint;

    // classification mirrors tools/lib.js gradeCase().
    let (status, reason): (&str, String) = classify(&w);
    let settle = settle_tick.unwrap_or(tick);
    match status {
        "pass" => println!("{{\"status\":\"pass\",\"settleTick\":{},\"footprint\":{}}}", settle, footprint),
        _ => println!("{{\"status\":\"{}\",\"settleTick\":{},\"footprint\":{},\"reason\":{}}}",
            status, settle, footprint, json_string(&reason)),
    }
    if args.profile {
        let mut glyphs: Vec<(char, u64)> = w.executed.iter().map(|(k, v)| (*k, *v)).collect();
        glyphs.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
        let mut rooms: Vec<(usize, u64)> = w.room_exec.iter().copied().enumerate().collect();
        rooms.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
        eprintln!("PROFILE glyphs={:?}", glyphs);
        eprintln!("PROFILE rooms={:?}", &rooms[..rooms.len().min(20)]);
        let mut room_glyphs: Vec<((usize, char), u64)> =
            w.room_glyph.iter().map(|(k, v)| (*k, *v)).collect();
        room_glyphs.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
        eprintln!(
            "PROFILE room_glyphs={:?}",
            &room_glyphs[..room_glyphs.len().min(80)]
        );
        let mut cells: Vec<((i32, i32), u64)> =
            w.executed_cells.iter().map(|(k, v)| (*k, *v)).collect();
        cells.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
        eprintln!("PROFILE cells={:?}", &cells[..cells.len().min(60)]);
        let mut stalls: Vec<((i32, i32), u64)> =
            w.stall_cells.iter().map(|(k, v)| (*k, *v)).collect();
        stalls.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
        let total: u64 = stalls.iter().map(|(_, c)| *c).sum();
        eprintln!("PROFILE stall_total={}", total);
        eprintln!("PROFILE stalls={:?}", &stalls[..stalls.len().min(5000)]);
    }
}

// Mirrors tools/lib.js gradeCase() classification order exactly. Load errors are handled
// by the caller before this. The order matters: a frame/output match is a pass even if the
// program also crashed on that same tick (frames are judged before the crash).
fn classify(w: &World) -> (&'static str, String) {
    let display = w.is_display_judged();
    // frame mismatch -> fail
    if display {
        if let Some(idx) = w.frame_mismatch {
            return ("fail", format!("frame {} wrong", idx + 1));
        }
    }
    let l = w.judge_output(); // "match" | "diverged" | "extra" | "pending"
    let frames_ok = !display || w.frame_matched >= w.expected_frame_count();
    if l == "match" && frames_ok {
        return ("pass", String::new());
    }
    if l == "diverged" || l == "extra" {
        return ("fail", l.to_string());
    }
    // pending / (display: frames incomplete)
    match &w.end {
        EndReason::Fatal { reason, .. } => ("crash", reason.clone()),
        EndReason::Done => ("fail", if display { "missing frames".into() } else { "missing output".into() }),
        _ => ("timeout", "no verdict".into()),
    }
}
