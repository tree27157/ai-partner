import numpy as np
from sentence_transformers import CrossEncoder
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
from api.config import CHROMA_DIR

ROOT = Path(__file__).resolve().parent.parent

_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5")
_client = chromadb.PersistentClient(
    path=CHROMA_DIR,
    settings=Settings(anonymized_telemetry=False))
COL = _client.get_or_create_collection(
    "notes_head", embedding_function=_ef,
    metadata={"hnsw:space": "cosine"})
SCORE_THRESHOLD = 0.3
RERANKER = CrossEncoder("BAAI/bge-reranker-base")
STANDARD = {"role", "content", "tool_calls", "tool_call_id"}

def embed(texts: list[str]) -> list[list[float]]:
    return _ef(texts)

def format_reference(retrieved, threshold= SCORE_THRESHOLD):
    """把检索结果格式化为第二条 system 的内容；全部低于阈值则提示笔记无相关内容"""
    hits = [(name, score, text) for name, score, text in (retrieved or []) if score >= threshold]
    if not hits:
        return ("")
    lines = [f"[{i}] 《{name}》(相关度 {score:.2f})\n{text}"
             for i, (name, score, text) in enumerate(hits, 1)]
    lines.append("只依据以上片段回答；片段里没有的信息就直接说笔记里没有，不要编造。")
    return "【参考资料】\n\n" + "\n\n".join(lines)



def build_messages(messages, system_prompt, retrieved=None, threshold= SCORE_THRESHOLD):
    msgs = [
        {"role": "system", "content": system_prompt},
    ]
    ref = format_reference(retrieved, threshold)
    if ref:  # 只有真的有命中才插
        msgs.append({"role": "system", "content": ref})
    for m in messages:
        msgs.append({k: v for k, v in m.items() if k in STANDARD})
    return msgs

def retrieve(query, candidates=10, top_k=3):
    """返回 [(文件名, 分数, 正文), ...]，按分数降序，最多 top_k 条"""
    res = COL.query(query_texts=[query], n_results=candidates)
    cands = [
        (doc, meta["file"], dist)
        for doc, meta, dist in zip(res["documents"][0],
                                   res["metadatas"][0],
                                   res["distances"][0])
    ]
    cands.sort(key=lambda c: c[2])
    scores = RERANKER.predict([(query, text) for text, name, dist in cands])
    order = np.argsort(scores)[::-1]
    retrieved = [(cands[i][1], float(scores[i]), cands[i][0]) for i in order]
    return retrieved[:top_k]
