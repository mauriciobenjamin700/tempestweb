#!/usr/bin/env bash
# run.sh — one issue #160 reproduction run: fresh port, fresh Chrome profile,
# fresh service worker. Usage:
#   ./run.sh <label> <port> <arm:clean|drain> <ticks> [harness flags...]
set -euo pipefail

LABEL="$1"; PORT="$2"; ARM="$3"; TICKS="$4"; shift 4
LATENCY="${TW160_LATENCY_MS:-0}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${TW160_OUT:-$HERE/results}"
mkdir -p "$OUT"

rm -rf "$OUT/prof-$LABEL"
(cd "$REPO" && exec "$REPO/.venv/bin/python" "$HERE/backend.py" \
  --port "$PORT" --dist "$HERE/app/dist/wasm" --arm "$ARM" \
  --latency-ms "$LATENCY" \
  --log "$OUT/req-$LABEL.log" > "$OUT/be-$LABEL.out" 2>&1) &
BE=$!
trap 'kill $BE 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then break; fi
  sleep 0.5
done
curl -fsS "http://127.0.0.1:$PORT/api/health"; echo

xvfb-run -a node "$HERE/harness.mjs" \
  --port "$PORT" --profile "$OUT/prof-$LABEL" --out "$OUT/$LABEL.json" \
  --ticks "$TICKS" --label "$LABEL" "$@"

kill $BE 2>/dev/null || true
wait $BE 2>/dev/null || true
echo "requests logged: $(wc -l < "$OUT/req-$LABEL.log")"
