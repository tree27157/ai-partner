# 已废弃，见 app.py 的 retrieve()
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings

import time
t = time.time()
def tick(msg):
    print(f"[{time.time()-t:5.1f}s] {msg}", flush=True)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT / "chroma_db")
COLLECTION = "notes"

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5"
)

tick("开始建 client")
client = chromadb.PersistentClient(path=DB_PATH, settings=Settings(anonymized_telemetry=False))
tick("client 好了")
col = client.get_or_create_collection(
    name=COLLECTION, embedding_function=ef,
    metadata={"hnsw:space": "cosine"},
)
tick(f"集合好了，条数 {col.count()}")

print("库中条数:", col.count())          # 应该 20

q = sys.argv[1] if len(sys.argv) > 1 else "进程调度有哪些算法"
res = col.query(query_texts=[q], n_results=3)
tick("查询完成")

print(f"\n问题：{q}\n")
for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
    print(f"[{dist:.4f}]  {meta['file']}")
    print(f"    {doc[:70].replace(chr(10), ' ')}…\n")