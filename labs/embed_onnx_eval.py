"""ONNX(fastembed, int8量化) 版跑 20 题，与两条基线对比。

基线：torch bge-small top1 17/20 recall@3 20/20；百炼 API top1 16/20 recall@3 19/20

跑法：systemctl stop aipartner && HF_ENDPOINT=https://hf-mirror.com python labs/embed_onnx_eval.py
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import psycopg

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
ROOT = Path("/opt/ai-partner")
sys.path.insert(0, str(ROOT))

from fastembed import TextEmbedding

cases = json.loads((ROOT / "labs" / "eval_set.json").read_text(encoding="utf-8"))

with psycopg.connect("dbname=aipartner") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT file, content FROM chunks")
        rows = cur.fetchall()

files = [r[0] for r in rows]
texts = [r[1] for r in rows]

model = TextEmbedding("BAAI/bge-small-zh-v1.5")

t0 = time.time()
doc_vecs = np.array(list(model.embed(texts, batch_size=8)), dtype=np.float32)
doc_s = time.time() - t0

t1 = time.time()
q_vecs = np.array(list(model.embed([c["q"] for c in cases])), dtype=np.float32)
q_s = time.time() - t1

doc_n = doc_vecs / np.linalg.norm(doc_vecs, axis=1, keepdims=True)
q_n = q_vecs / np.linalg.norm(q_vecs, axis=1, keepdims=True)
sims = q_n @ doc_n.T
del doc_vecs, q_vecs

print(f"语料 {len(rows)} 块 | 文档嵌入 {doc_s:.1f}s | 查询 {q_s:.1f}s ({q_s/len(cases)*1000:.0f} ms/题)\n")
print(f"{'问题':<26}{'top1':<32}{'sim':>7}{'margin':>9}  命中 R3")
print("-" * 90)

top1 = r3 = 0
low_margin = 0
for i, c in enumerate(cases):
    order = np.argsort(-sims[i])[:3]
    names = [files[j] for j in order]
    s = [float(sims[i][j]) for j in order]
    margin = s[0] - s[1]
    ok1 = names[0] == c["expect"]
    ok3 = c["expect"] in names
    top1 += ok1
    r3 += ok3
    low_margin += margin < 0.01
    print(f"{c['q'][:24]:<26}{names[0][:30]:<32}{s[0]:>7.3f}{margin:>+9.4f}  {'✓' if ok1 else '✗'}  {'✓' if ok3 else '✗'}")

n = len(cases)
print("-" * 90)
print(f"ONNX(int8 量化)  top1 {top1}/{n}   recall@3 {r3}/{n}   margin<0.01 的有 {low_margin} 题")
print(f"torch bge-small   top1 17/20   recall@3 20/20   （基线，11-10）")
print(f"百炼 API(512)      top1 16/20   recall@3 19/20   （今天对照）")
