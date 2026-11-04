"""
建三个向量库，对应三种切分策略。
跑法：python labs/build_chunks.py
"""
import re
from pathlib import Path
import sys

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api.chunking import STRATEGIES


# ============ 路径（从本文件位置推，跟 CWD 无关）============
ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"
DB = str(ROOT / "chroma_db")



# ============ 主流程 ============
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5"
)
client = chromadb.PersistentClient(
    path=DB,
    settings=Settings(anonymized_telemetry=False),
)

files = sorted(NOTES.glob("*.md"))
if not files:
    raise SystemExit(f"没找到 md 文件！NOTES = {NOTES}")
print(f"文档数: {len(files)}\n")

for name, fn in STRATEGIES.items():
    col_name = f"notes_{name}"

    # 重建前先删旧库，否则数据会叠加
    try:
        client.delete_collection(col_name)
        print(f"[{name}] 已删除旧 collection")
    except Exception:
        pass

    docs, ids, metas = [], [], []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for i, ch in enumerate(fn(text)):
            docs.append(ch)
            ids.append(f"{f.name}::{i}")
            metas.append({"file": f.name})

    if not docs:
        print(f"[{name}] 空，跳过")
        continue

    col = client.get_or_create_collection(
        col_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    col.add(documents=docs, ids=ids, metadatas=metas)

    avg = sum(len(d) for d in docs) // len(docs)
    mn = min(len(d) for d in docs)
    mx = max(len(d) for d in docs)
    print(f"[{name}] {len(docs)} 块 | 平均 {avg} 字 | 最短 {mn} | 最长 {mx}")