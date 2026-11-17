"""A/B 对照：本地 bge-small vs 百炼 text-embedding-v3(512) 在 20 题评测集上的表现。

只读 pg 里现成的 chunks，不改任何生产代码。跑法：
    cd /opt/ai-partner && set -a && . ./.env && set +a && python3 labs/embed_ab.py
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import DB_URL  # noqa: E402

KEY = os.environ["DASHSCOPE_API_KEY"]
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"


def api_embed(texts, batch=10, dims=512):
    """百炼 embedding，按批调用，返回 list[list[float]]"""
    import urllib.request

    out = []
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        body = json.dumps(
            {"model": "text-embedding-v3", "input": chunk, "dimensions": dims}
        ).encode()
        req = urllib.request.Request(
            URL,
            data=body,
            headers={
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        out.extend([x["embedding"] for x in d["data"]])
    return out


def main():
    cases = json.loads((ROOT / "labs" / "eval_set.json").read_text(encoding="utf-8"))

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT file, content FROM chunks")
            rows = cur.fetchall()

    files = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    print(f"语料：{len(rows)} 块 / {len(set(files))} 篇；评测集：{len(cases)} 题")

    t0 = time.time()
    doc_vecs = np.array(api_embed(texts), dtype=np.float32)
    embed_s = time.time() - t0
    print(f"文档嵌入：{embed_s:.1f}s（{embed_s / len(rows) * 1000:.0f} ms/条）")

    # 归一化：余弦相似度 = 点积
    doc_norm = doc_vecs / np.linalg.norm(doc_vecs, axis=1, keepdims=True)

    t1 = time.time()
    q_vecs = np.array(api_embed([c["q"] for c in cases]), dtype=np.float32)
    q_s = time.time() - t1
    print(f"查询嵌入：{q_s:.1f}s（{q_s / len(cases) * 1000:.0f} ms/题）\n")

    q_norm = q_vecs / np.linalg.norm(q_vecs, axis=1, keepdims=True)
    sims = q_norm @ doc_norm.T          # (题数, 块数)

    top1_hit = r3_hit = 0
    print(f"{'问题':<28}{'top1 文件':<34}{'sim':>7}{'margin':>9}  命中 R3")
    print("-" * 92)
    for i, c in enumerate(cases):
        order = np.argsort(-sims[i])[:3]
        names = [files[j] for j in order]
        s = [float(sims[i][j]) for j in order]
        margin = s[0] - s[1] if len(s) > 1 else 0.0
        ok1 = names[0] == c["expect"]
        ok3 = c["expect"] in names
        top1_hit += ok1
        r3_hit += ok3
        print(
            f"{c['q'][:26]:<28}{names[0][:32]:<34}{s[0]:>7.3f}{margin:>+9.4f}"
            f"  {'✓' if ok1 else '✗'}  {'✓' if ok3 else '✗'}"
        )

    n = len(cases)
    print("-" * 92)
    print(f"API 版        top1 {top1_hit}/{n}   recall@3 {r3_hit}/{n}")
    print("本地 bge-small top1 17/20   recall@3 20/20   （历史基线，11-10 评测）")
    print(f"\n成本估算：文档 {len(rows)} 条 + 查询 {n} 条 ≈ {sum(len(t) for t in texts) // 2} token 量级")


if __name__ == "__main__":
    main()
