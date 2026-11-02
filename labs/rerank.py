import json
from pathlib import Path
import sys
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import numpy as np
from sentence_transformers import CrossEncoder


ROOT = Path(__file__).resolve().parent.parent

CASES = json.loads((ROOT / "labs" / "eval_set.json").read_text(encoding="utf-8"))

DB = str(ROOT / "chroma_db")
client = chromadb.PersistentClient(
        path=DB, settings=Settings(anonymized_telemetry=False))

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-small-zh-v1.5")


RERANKER = CrossEncoder("BAAI/bge-reranker-base")


def recall(col,query, k=10):

    res = col.query(query_texts=[query], n_results=k)
    cands = [
        (doc, meta["file"], dist)
        for doc, meta, dist in zip(res["documents"][0],
                                   res["metadatas"][0],
                                   res["distances"][0])
    ]
    cands.sort(key=lambda c: c[2])
    return cands


def rerank(query, cands):
    scores = RERANKER.predict([(query, text) for text, name, dist in cands])
    order = np.argsort(scores)[::-1]
    reranked = [(*cands[i], float(scores[i])) for i in order]
    return reranked


def main():

    targets = sys.argv[1:] or ["notes", "notes_overlap", "notes_head"]

    for name in targets:
        n = len(CASES)
        top1_before = top1_after = 0
        r3_before = r3_after = 0

        col = client.get_collection(name, embedding_function=ef)
        print(f"\n########## {name}（{col.count()} 块）##########")

        for case in CASES:
            q, expect = case["q"], case["expect"]
            cand = recall(col, q) # 10 条，dist 升序
            rer = rerank(q, cand)  # 每条为 (正文, 文件名, dist, score)

            before3 = [c[1] for c in cand[:3]]
            after3 = [r[1] for r in rer[:3]]
            hit_top1_before = before3[0] == expect
            hit_top1_after = after3[0] == expect
            gap = rer[0][3] - rer[1][3] if len(rer) > 1 else 0.0  # 只有 1 条时无第2名
            hit_at3_before = expect in before3
            hit_at3_after = expect in after3

            top1_before += hit_top1_before
            top1_after += hit_top1_after
            r3_before += hit_at3_before
            r3_after += hit_at3_after

            print("=" * 60)
            print(f"问题：{q}")
            print(f"期望：{expect}")
            print("召回前3（文件名 + dist）：")
            for fname, c in zip(before3, cand[:3]):
                mark = "✓" if fname == expect else " "
                print(f"  {mark} {fname}  dist={c[2]:.4f}")
            print("重排后3（文件名 + score）：")
            for r in rer[:3]:
                mark = "✓" if r[1] == expect else " "
                print(f"  {mark} {r[1]}  score={r[3]:.4f}")
            print(f"top1 命中： 召回 {'✓' if hit_top1_before else '✗'}  "
                  f"→ 重排 {'✓' if hit_top1_after else '✗'}")
            print(f"gap(前两名分差)：{gap:.4f}   "
                  f"recall@3：召回 {'✓' if hit_at3_before else '✗'}  "
                  f"→ 重排 {'✓' if hit_at3_after else '✗'}")


    print("=" * 60)
    print("【汇总】")
    print(f"top1   ：召回 {top1_before}/{n}  →  重排 {top1_after}/{n}")
    print(f"recall@3：召回 {r3_before}/{n}  →  重排 {r3_after}/{n}")




if __name__ == "__main__":
    main()
