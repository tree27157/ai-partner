"""
评测：读 eval_set.json，对多个 collection 打分。
用法：
    python labs/eval.py                 # 评全部
    python labs/eval.py notes_head      # 只评一个
"""
import json
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = ROOT / "labs" / "eval_set.json"
DB = str(ROOT / "chroma_db")
ALL_COLLECTIONS = ["notes", "notes_fixed", "notes_head", "notes_overlap"]
def main():
    targets = sys.argv[1:] or ALL_COLLECTIONS

    cases = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    print(f"评测集: {len(cases)} 题\n")

    # 期望文件必须真实存在，否则就是抄错了
    existing = {p.name for p in (ROOT / "notes").glob("*.md")}
    for c in cases:
        if c["expect"] not in existing:
            raise SystemExit(f"❌ 期望文件不存在：{c['expect']!r}\n"
                             f"   磁盘上以 {c['expect'][:4]!r} 开头的有："
                             f"{[n for n in existing if n.startswith(c['expect'][:4])]}")

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-small-zh-v1.5")
    client = chromadb.PersistentClient(
        path=DB, settings=Settings(anonymized_telemetry=False))

    for name in targets:
        try:
            col = client.get_collection(name, embedding_function=ef)
        except Exception:
            print(f"跳过 {name}（不存在）")
            continue

        hits = 0
        hits3 = 0
        rows = []
        for c in cases:
            r = col.query(query_texts=[c["q"]], n_results=3)
            files = [m["file"] for m in r["metadatas"][0]]
            d = r["distances"][0]
            margin = d[1] - d[0] if len(d) > 1 else 0.0
            ok = files[0] == c["expect"]
            ok3 = c["expect"] in files
            hits += ok
            hits3 += ok3
            rows.append((c["q"], files[0], d[0], margin, ok, ok3))



        print(f"===== {name}（{col.count()} 块）: {hits}/{len(cases)} =====")
        print(f"{'问题':<18}{'top1':<28}{'dist':>8}{'margin':>9}  命中")
        print("-" * 76)
        for q, f, dist, m, ok, ok3 in rows:
            print(f"{q[:16]:<18}{f[:26]:<28}{dist:>8.4f}{m:>+9.4f}  {'✓' if ok else '✗'}{'✓' if ok3 else '-':>4}")
        print()


if __name__ == "__main__":
    main()