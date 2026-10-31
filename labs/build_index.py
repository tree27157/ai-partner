import glob, os
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

COLLECTION = "notes"
ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT/"notes"          # 从 labs/ 跑，所以是上一级
DB_PATH = str(ROOT / "chroma_db")

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5"
)
client = chromadb.PersistentClient(path=DB_PATH)
col = client.get_or_create_collection(
    name=COLLECTION,
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"},
)

# 防重复灌库
if col.count() > 0:
    print(f"已有 {col.count()} 条，跳过。要重建请先删掉 chroma_db/")
    raise SystemExit

files = sorted(glob.glob(os.path.join(NOTES_DIR, "*.md")))
print(f"找到 {len(files)} 个文件")

col.add(
    documents=[open(f, encoding="utf-8").read() for f in files],
    ids=[os.path.basename(f) for f in files],
    metadatas=[{"file": os.path.basename(f)} for f in files],
)
print("入库完成，条数:", col.count())

print("CWD:", Path.cwd())
print("NOTES_DIR:", NOTES_DIR, "存在?", NOTES_DIR.exists())