import chromadb
from chromadb.config import Settings
import psycopg


def to_list(v):
    """psycopg 取 pgvector 列默认返回字符串 '[0.1,0.2,...]'，转成 float 列表"""
    if isinstance(v, str):
        return [float(x) for x in v.strip("[]").split(",")]
    return list(v)


conn = psycopg.connect("dbname=aipartner")
cur = conn.cursor()

# ① 当查询向量的那条记录
cur.execute("SELECT id, file, embedding FROM chunks WHERE id = 1")
ref_id, ref_file, ref_vec = cur.fetchone()
vec_list = to_list(ref_vec)
print(f"参照: id={ref_id}  {ref_file}\n")

# ② postgres 排序
cur.execute("""
    SELECT id, file, embedding <=> %s::vector AS dist
    FROM chunks ORDER BY dist LIMIT 3
""", (ref_vec,))
pg_rows = cur.fetchall()

# ③ chroma 排序
client = chromadb.PersistentClient(
    path="chroma_db", settings=Settings(anonymized_telemetry=False))
col = client.get_collection("notes_head")
r = col.query(query_embeddings=[vec_list], n_results=3)

print("== postgres ==")
for i, f, d in pg_rows:
    print(f"  id={i:<3} dist={d:.6f}  {f}")

print("\n== chroma ==")
for m, d in zip(r["metadatas"][0], r["distances"][0]):
    print(f"           dist={d:.6f}  {m['file']}")