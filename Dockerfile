FROM docker.1ms.run/library/python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*


ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        -r requirements.txt

ENV HF_ENDPOINT=https://hf-mirror.com
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

COPY . .

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]