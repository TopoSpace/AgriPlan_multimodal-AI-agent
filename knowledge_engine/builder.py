# knowledge_engine/builder.py

import os
import faiss # type: ignore
import pickle
from typing import List
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter # type: ignore

VECTOR_STORE_PATH = "vector_db/agri_knowledge"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def load_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def split_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return splitter.split_text(text)


def build_vector_store(file_path: str):
    """Vectorize the uploaded text files and construct the FAISS vector database"""
    assert file_path.endswith(".txt"), "Currently only TXT format uploads are supported"
    print(f"🔍 Building the Knowledge Base（构建知识库中:） {file_path}")

    # Loading text and chunking
    raw_text = load_txt(file_path)
    chunks = split_text(raw_text)

    # vectorization
    embeddings = model.encode(chunks, convert_to_tensor=False)

    # Building the FAISS Index
    index = faiss.IndexFlatL2(len(embeddings[0]))
    index.add(embeddings)

    # Stored Data
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
    faiss.write_index(index, os.path.join(VECTOR_STORE_PATH, "index.faiss"))

    with open(os.path.join(VECTOR_STORE_PATH, "chunks.pkl"), "wb") as f:
        pickle.dump(chunks, f)

    print("✅ Knowledge base construction is complete and has been saved to（知识库构建完成，已保存至） vector_db/agri_knowledge")
