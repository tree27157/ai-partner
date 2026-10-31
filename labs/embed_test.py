from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

sentences = [
    "今天天气真好，适合出门散步",
    "阳光明媚，是个出游的好日子",
    "股票市场今天大幅下跌",
    "我想学怎么做红烧肉",
]

vecs = model.encode(sentences, normalize_embeddings=False)   # 先不归一化
print("维度:", vecs.shape)                                    # 看它多少维

def cos(a, b):
    return float(np.dot(a, b)/ (np.linalg.norm(a) * np.linalg.norm(b)))

print("近义对:", cos(vecs[0], vecs[1]))     # 应该高
print("无关对:", cos(vecs[0], vecs[2]))     # 应该低

vecs_n = model.encode(sentences, normalize_embeddings=True)
print("归一化后直接点积:", float(np.dot(vecs_n[0], vecs_n[1])))