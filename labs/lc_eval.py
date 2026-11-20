import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from api.chunking import split_by_head

ROOT = Path(__file__).resolve().parent.parent        # 项目根
NOTES = ROOT / "notes"

chunks = []
for p in sorted(NOTES.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    for c in split_by_head(text):
        chunks.append((p.name, c))

emb = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    encode_kwargs={"normalize_embeddings": True},
)
vs = Chroma(
    collection_name="notes_head_lc",
    embedding_function=emb,
    persist_directory="chroma_db_lc",
    collection_metadata={"hnsw:space": "cosine"},
)
vs.add_texts(texts=[c for _, c in chunks],
             metadatas=[{"file": f} for f, _ in chunks])

# ③ 跑 20 题
cases = json.loads(Path(ROOT / "labs" / "eval_set.json").read_text(encoding="utf-8"))
hits = 0
hits3 = 0
rows = []
for c in cases:
    pairs = vs.similarity_search_with_score(c["q"], k=3)
    files = [d.metadata["file"] for d, s in pairs]
    dists = [s for d, s in pairs]
    margin = dists[1] - dists[0]          # 与手写版同口径
    ok = files[0] == c["expect"]
    ok3 = c["expect"] in files
    hits += ok
    hits3 += ok3
    rows.append((c["q"], files[0], dists[0], margin, ok, ok3))

print(f"{'问题':<18}{'top1':<28}{'dist':>8}{'margin':>9}  命中")
print("-" * 76)
for q, f, dist, m, ok, ok3 in rows:
    print(f"{q[:16]:<18}{f[:26]:<28}{dist:>8.4f}{m:>+9.4f}  "
          f"{'✓' if ok else '✗'}{'✓' if ok3 else '-':>4}")

low = sum(1 for r in rows if r[3] < 0.01)
print()
print(f"LangChain:  top1 {hits}/20   recall@3 {hits3}/20   margin<0.01 有 {low} 题")
print(f"手写版:     top1 17/20   recall@3 20/20   margin<0.01 有 8 题")

miss = [(r[0], r[1]) for r in rows if not r[4]]
if miss:
    print("\n未命中：")
    for q, f in miss:
        print(f"  {q}  → 实际 {f}")
