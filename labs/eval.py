"""
评测四个库（整篇 + 三种切分）在 5 个问题上的表现。
跑法：python labs/eval.py
"""
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent.parent
DB = str(ROOT / "chroma_db")

# 问题 → 你事先确认过答案在哪篇
QUESTIONS = [
    ("进程调度有哪些算法",   "03_进程调度算法.md"),
    ("TCP三次握手的过程",   "17_TCP协议、三次握手四次挥手.md"),
    ("虚拟内存和分页",      "07_虚拟内存与页面置换算法.md"),
    ("HTTP无状态是什么意思", "19_应用层：HTTP、DNS.md"),
    ("什么是计数到无穷问题", "15_路由协议、静态路由与RIP、OSPF.md"),
]

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5"
)
client = chromadb.PersistentClient(
    path=DB,
    settings=Settings(anonymized_telemetry=False),
)

for name in ["notes", "notes_fixed", "notes_head", "notes_overlap"]:
    try:
        col = client.get_collection(name, embedding_function=ef)
    except Exception:
        print(f"跳过 {name}（不存在）")
        continue

    hit = 0
    print(f"\n===== {name}（{col.count()} 块） =====")
    print(f"{'问题':<16}{'top1 文件':<26}{'dist':>8}{'margin':>9}   命中")
    print("-" * 70)

    for q, expect in QUESTIONS:
        r = col.query(query_texts=[q], n_results=3)
        files = [m["file"] for m in r["metadatas"][0]]
        d = r["distances"][0]
        margin = d[1] - d[0] if len(d) > 1 else 0.0
        ok = files[0] == expect
        hit += ok
        print(f"{q[:14]:<16}{files[0][:24]:<26}{d[0]:>8.4f}{margin:>+9.4f}   {'✓' if ok else '✗'}")

    print(f"命中: {hit}/{len(QUESTIONS)}")