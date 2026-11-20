from sentence_transformers import SentenceTransformer
from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np

TEXT = "死锁是多个进程互相持有对方需要的资源，并且都不释放，形成无限等待的状态。"

st = SentenceTransformer("BAAI/bge-small-zh-v1.5")
v1 = st.encode([TEXT], normalize_embeddings=True)[0]

emb = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5",
                            encode_kwargs={"normalize_embeddings": True})
v2 = np.array(emb.embed_documents([TEXT])[0])

print("模长:", np.linalg.norm(v1), np.linalg.norm(v2))
print("余弦:", float(np.dot(v1, v2)))
