"""
建三个向量库，对应三种切分策略。
跑法：python labs/build_chunks.py
"""
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# ============ 路径（从本文件位置推，跟 CWD 无关）============
ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"
DB = str(ROOT / "chroma_db")


# ============ 策略 1：固定长度 ============
def split_fixed(text, size=300):
    chunks = []
    for i in range(0, len(text), size):
        piece = text[i:i + size].strip()
        if piece:
            chunks.append(piece)
    return chunks


# ============ 策略 2：按标题 + 合并 ============
def split_by_head(text, target=350, min_size=150):
    # 第一步：按 1-2 级标题切（\n 后面紧跟 # 或 ##）
    sections = [s.strip() for s in re.split(r"\n(?=#{1,2} )", text) if s.strip()]

    # 第二步：从左往右，太小就并进来
    chunks, buf = [], ""
    for sec in sections:
        if not buf:
            buf = sec                              # 第一块
        elif len(buf) < min_size or len(buf) + len(sec) <= target:
            buf = buf + "\n\n" + sec               # 太小 / 装得下 → 合并
        else:
            chunks.append(buf)                     # 装不下了 → 收工，另起
            buf = sec
    if buf:
        chunks.append(buf)
    return chunks


# ============ 策略 3：策略 2 + 重叠 ============
def split_by_head_overlap(text, overlap=50):
    base = split_by_head(text)
    chunks = []
    for i, c in enumerate(base):
        if i == 0:
            chunks.append(c)
        else:
            chunks.append(base[i - 1][-overlap:] + "\n" + c)   # 拼上一块尾巴
    return chunks


STRATEGIES = {
    "fixed":   split_fixed,
    "head":    split_by_head,
    "overlap": split_by_head_overlap,
}


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