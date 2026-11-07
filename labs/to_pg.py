import chromadb
from chromadb.config import Settings
import psycopg

client = chromadb.PersistentClient(
    path="chroma_db", settings=Settings(anonymized_telemetry=False))
col = client.get_collection("notes_head")

data = col.get(include=["documents", "metadatas", "embeddings"])
print("从 chroma 读到:", len(data["ids"]))

with psycopg.connect("dbname=aipartner") as conn:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE chunks RESTART IDENTITY")
        for doc, meta, emb in zip(data["documents"], data["metadatas"], data["embeddings"]):
            vec = "[" + ",".join(str(float(x)) for x in emb) + "]"
            cur.execute(
                "INSERT INTO chunks (file, content, embedding) VALUES (%s, %s, %s::vector)",
                (meta["file"], doc, vec),
            )
    conn.commit()

print("插入完成")