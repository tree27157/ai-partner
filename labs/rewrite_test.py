"""
对比同一题三种 query 版本的 margin（只跑 notes_head）。
用法：python labs/rewrite_test.py
"""
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent.parent
client = chromadb.PersistentClient(
    path=str(ROOT / "chroma_db"),
    settings=Settings(anonymized_telemetry=False),
)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5")
col = client.get_collection("notes_head", embedding_function=ef)

CASES = [
    ("虚拟内存", "07_虚拟内存与页面置换算法.md", [
        ("A 原句",   "虚拟内存和分页"),
        ("B 关键词", "虚拟内存 分页 地址映射"),
        ("C 补术语", "虚拟内存 页表 缺页中断"),
    ]),
    ("计数到无穷", "15_路由协议、静态路由与RIP、OSPF.md", [
        ("A 原句",   "什么是计数到无穷问题"),
        ("B 关键词", "计数到无穷 路由环路"),
        ("C 补术语", "路由 距离向量 环路"),
    ]),
]

for title, expect, variants in CASES:
    print(f"\n===== {title}  期望: {expect[:14]} =====")
    print(f"{'版本':<10}{'top1':<28}{'dist':>8}{'margin':>9}  命中")
    print("-" * 70)
    for label, q in variants:
        r = col.query(query_texts=[q], n_results=3)
        files = [m["file"] for m in r["metadatas"][0]]
        d = r["distances"][0]
        margin = d[1] - d[0] if len(d) > 1 else 0.0
        ok = "✓" if files[0] == expect else "✗"
        print(f"{label:<10}{files[0][:26]:<28}{d[0]:>8.4f}{margin:>+9.4f}  {ok}")