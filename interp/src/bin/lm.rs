//! CLI: `lm <program.man> [steps]` -> one JSON snapshot per line (step 0..=N or until end).
//! Field layout mirrors the WASM oracle so sim/difftest.js can compare directly.

use littleman::{World, EndReason, Runner};

fn esc(_s: &str) -> String { String::new() }

fn runner_json(r: &Runner) -> String {
    format!(
        "{{\"id\":{},\"pos\":[{},{}],\"dir\":[{},{}],\"halted\":{},\"a\":{},\"b\":{},\"bp\":{}}}",
        r.id, r.pos.0, r.pos.1, r.dir.0, r.dir.1, r.halted, r.a, r.b, r.bp
    )
}

fn snapshot_json(w: &World) -> String {
    let runners: Vec<String> = w.snapshot_runners().iter().map(|r| runner_json(r)).collect();
    let (end, extra) = match &w.end {
        EndReason::Running => ("running".to_string(), String::new()),
        EndReason::Done => ("done".to_string(), String::new()),
        EndReason::StepCap => ("stepcap".to_string(), String::new()),
        EndReason::Fatal { reason, pos, cell } => (
            "fatal".to_string(),
            format!(",\"fatal\":{{\"reason\":\"{}\",\"pos\":[{},{}],\"cell\":{}}}",
                reason, pos.0, pos.1, serde_char(*cell)),
        ),
    };
    let _ = esc("");
    format!(
        "{{\"step\":{},\"runners\":[{}],\"end\":\"{}\",\"footprint\":{}{}}}",
        w.step_count, runners.join(","), end, w.footprint, extra
    )
}

fn serde_char(c: char) -> String {
    if c == '\0' { "\"\\u0000\"".to_string() }
    else if c == '"' || c == '\\' { format!("\"\\{}\"", c) }
    else { format!("\"{}\"", c) }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: lm <program.man> [steps]");
        std::process::exit(2);
    }
    let steps: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(200);
    let src = std::fs::read_to_string(&args[1]).expect("read program");
    let rows: Vec<String> = src.lines().map(|l| l.to_string()).collect();

    let mut w = World::load(&rows, 5_000_000);
    println!("{}", snapshot_json(&w)); // step 0
    for _ in 0..steps {
        if w.end != EndReason::Running { break; }
        w.step();
        println!("{}", snapshot_json(&w));
    }
}
