# knowledge_engine/retriever.py

import os
import faiss # type: ignore
import pickle
from sentence_transformers import SentenceTransformer
from typing import List

VECTOR_STORE_PATH = "vector_db/agri_knowledge"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 3

model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def query_vector_store(query: str, top_k: int = TOP_K) -> List[str]:
    """Query the most relevant text passages from the vector knowledge base"""

    index_path = os.path.join(VECTOR_STORE_PATH, "index.faiss")
    chunk_path = os.path.join(VECTOR_STORE_PATH, "chunks.pkl")

    if not os.path.exists(index_path) or not os.path.exists(chunk_path):
        raise FileNotFoundError("❌ The knowledge base has not been built yet, please run（知识库尚未构建，请先运行） builder.build_vector_store()")

    # Load data
    index = faiss.read_index(index_path)
    with open(chunk_path, "rb") as f:
        chunks = pickle.load(f)

    # Code Search
    query_vec = model.encode([query])
    D, I = index.search(query_vec, top_k)

    results = [chunks[i] for i in I[0] if i < len(chunks)]
    return results
