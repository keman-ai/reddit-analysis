#!/usr/bin/env bash
# A2H Agent Runtime entrypoint for reddit-analysis.
# Reads /workspace/input.json, runs the research, writes /workspace/output.json.
set -euo pipefail

WORKSPACE="${A2H_WORKSPACE:-/workspace}"
PROJECT_ROOT="/opt/agent"

cd "$PROJECT_ROOT"

# 1. Parse input
RESEARCH_BRIEF=$(jq -r '.inputs.research_brief // ""' "$WORKSPACE/input.json")
if [ -z "$RESEARCH_BRIEF" ]; then
    printf '{"ts":"%s","msg":"ERROR: research_brief is empty"}\n' "$(date -Iseconds)" \
        >> "$WORKSPACE/progress.ndjson"
    jq -n '{status:"failed", error:"research_brief input is required"}' \
        > "$WORKSPACE/output.json"
    exit 1
fi

# 2. Generate task_id
TASK_ID="run-$(date +%Y%m%d-%H%M%S)-$$"
printf '{"ts":"%s","msg":"Starting research task: %s"}\n' \
    "$(date -Iseconds)" "${RESEARCH_BRIEF:0:100}" >> "$WORKSPACE/progress.ndjson"

# 3. Run research (redirecting stdout to progress.ndjson for live feedback)
# The run.py script writes status files to data/raw/{task_id}_status.json.
# We'll tail that file and convert it to progress events.
python run.py --task-id "$TASK_ID" "$RESEARCH_BRIEF" &
RUN_PID=$!

# Tail status file in the background
STATUS_FILE="$PROJECT_ROOT/data/raw/${TASK_ID}_status.json"
(
  while kill -0 $RUN_PID 2>/dev/null; do
    if [ -f "$STATUS_FILE" ]; then
      PHASE=$(jq -r '.phase_name // "unknown"' "$STATUS_FILE" 2>/dev/null || echo "unknown")
      STATUS=$(jq -r '.status // "running"' "$STATUS_FILE" 2>/dev/null || echo "running")
      DETAIL=$(jq -r '.detail // ""' "$STATUS_FILE" 2>/dev/null || echo "")
      printf '{"ts":"%s","msg":"Phase: %s | Status: %s | %s"}\n' \
          "$(date -Iseconds)" "$PHASE" "$STATUS" "${DETAIL:0:80}" >> "$WORKSPACE/progress.ndjson"
    fi
    sleep 5
  done
) &
TAIL_PID=$!

# Wait for run.py to complete
wait $RUN_PID || {
    printf '{"ts":"%s","msg":"ERROR: run.py exited with code %s"}\n' \
        "$(date -Iseconds)" "$?" >> "$WORKSPACE/progress.ndjson"
    kill $TAIL_PID 2>/dev/null || true
    jq -n '{status:"failed", error:"Research script crashed"}' > "$WORKSPACE/output.json"
    exit 1
}
kill $TAIL_PID 2>/dev/null || true

# 4. Extract results
REPORT_PATH="$PROJECT_ROOT/data/reports/${TASK_ID}_report.md"
if [ ! -f "$REPORT_PATH" ]; then
    printf '{"ts":"%s","msg":"ERROR: Report not found at %s"}\n' \
        "$(date -Iseconds)" "$REPORT_PATH" >> "$WORKSPACE/progress.ndjson"
    jq -n '{status:"failed", error:"Report generation failed"}' > "$WORKSPACE/output.json"
    exit 1
fi

# Copy report to workspace outputs/
mkdir -p "$WORKSPACE/outputs"
cp "$REPORT_PATH" "$WORKSPACE/outputs/report.md"

# Extract summary (first 300 chars of ## 核心结论 section, or fallback to first paragraph)
SUMMARY=$(awk '/^## 核心结论/,/^##/' "$REPORT_PATH" | grep -v '^##' | head -c 300 || head -c 300 "$REPORT_PATH")

# 5. Write output.json
jq -n --arg summary "$SUMMARY" \
    '{status:"success", 
      outputs:{
        report:{type:"file", path:"outputs/report.md", mime:"text/markdown"},
        summary:{type:"text", content:$summary}
      }}' \
    > "$WORKSPACE/output.json"

printf '{"ts":"%s","msg":"Research complete. Report: outputs/report.md"}\n' \
    "$(date -Iseconds)" >> "$WORKSPACE/progress.ndjson"
