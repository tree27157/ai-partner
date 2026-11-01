"""
query 改写对照实验。
1) 无缓存时调用模型为每题生成 3 条改写，增量落盘到 labs/rewrites.json
2) 在 notes_head 上对比「原句 vs 3 条改写」的 top1 / margin / recall@3
用法：python labs/query_rewrite.py           # 有缓存则直接用
      python labs/query_rewrite.py --regen  # 强制重新生成
"""
import json
import os
import re
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = ROOT / "labs" / "eval_set.json"
REWRITES = ROOT / "labs" / "rewrites.json"

MODEL = "deepseek-chat"
PROMPT_VERSION = 1

db = chromadb.PersistentClient(
    path=str(ROOT / "chroma_db"),
    settings=Settings(anonymized_telemetry=False))
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-zh-v1.5")
col = db.get_collection("notes_head", embedding_function=ef)

llm = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
             base_url="https://api.deepseek.com")

SYS = """你是检索查询改写器。针对用户问题生成 3 条检索查询，每条一行：
1. 术语补全：补上教材里可能出现的同义术语
2. 主题扩展：补上该知识点所属的更大主题
3. 关键词化：去掉疑问句式，只保留名词短语
只输出 3 行，不要编号、不要解释。"""


def gen(q: str) -> list[str]:
    r = llm.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYS},
                  {"role": "user", "content": q}],
        temperature=0)
    lines = [re.sub(r"^\d+[.、)]\s*", "", ln).strip()
             for ln in r.choices[0].message.content.splitlines()]
    return [ln for ln in lines if ln][:3]


def load_rewrites(cases, regen=False):
    data = {"meta": {}, "rewrites": {}}
    if REWRITES.exists() and not regen:
        data = json.loads(REWRITES.read_text(encoding="utf-8"))
        if data.get("meta", {}).get("prompt_version") != PROMPT_VERSION:
            print("⚠️ 提示词版本变了，清空缓存")
            data = {"meta": {}, "rewrites": {}}

    data["meta"] = {"model": MODEL, "prompt_version": PROMPT_VERSION}

    for c in cases:
        if c["q"] in data["rewrites"]:
            continue
        data["rewrites"][c["q"]] = gen(c["q"])
        REWRITES.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")     # 每题落一次盘
        print(f"[生成] {c['q']}")
    return data["rewrites"]


def probe(q):
    r = col.query(query_texts=[q], n_results=3)
    files = [m["file"] for m in r["metadatas"][0]]
    return files, r["distances"][0]


def main():
    cases = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    rw = load_rewrites(cases, regen="--regen" in sys.argv)

    for c in cases:
        q, expect = c["q"], c["expect"]
        print(f"\n【{q}】  期望: {expect[:14]}")
        rows = [("原句", q)] + [(f"改写{i}", r) for i, r in enumerate(rw[q], 1)]
        for label, qq in rows:
            files, d = probe(qq)
            m = d[1] - d[0] if len(d) > 1 else 0.0
            print(f"  {label:<6}{files[0][:22]:<24} dist={d[0]:.4f} "
                  f"margin={m:+.4f} {'✓' if files[0] == expect else '✗'}  "
                  f"{'R3✓' if expect in files else 'R3-'}")
        print("  改写内容：")
        for i, r in enumerate(rw[q], 1):
            print(f"    {i}. {r}")


if __name__ == "__main__":
    main()