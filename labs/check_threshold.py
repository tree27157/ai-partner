import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from api.rag import retrieve, SCORE_THRESHOLD

cases = json.loads(open("labs/eval_set.json", encoding="utf-8").read())

low = []
for c in cases:
    r = retrieve(c["q"])
    top = r[0][1] if r else 0.0
    if top < SCORE_THRESHOLD:
        low.append((c["q"], top, c["expect"]))

print(f"阈值 {SCORE_THRESHOLD}：{len(cases) - len(low)}/{len(cases)} 题能过线")
for q, s, e in low:
    print(f"  ⚠️ {s:.3f}  {q[:28]}  → 期望 {e[:14]}")