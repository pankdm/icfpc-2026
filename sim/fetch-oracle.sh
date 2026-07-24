#!/usr/bin/env bash
# Fetch the reference littleman interpreter (Go->WASM) + glue from the contest site.
# These are the organizers' artifacts and are gitignored; run this once before using
# the oracle harness (harness.js) or the differential tests (difftest.js).
set -euo pipefail
cd "$(dirname "$0")"
base="https://icfpcontest2026.com"
echo "Fetching littleman.wasm ..."
curl -fsSL "$base/littleman.wasm" -o littleman.wasm
echo "Fetching wasm_exec.js ..."
curl -fsSL "$base/wasm_exec.js" -o wasm_exec.js
echo "Done: $(ls -la littleman.wasm wasm_exec.js | awk '{print $5, $9}')"
