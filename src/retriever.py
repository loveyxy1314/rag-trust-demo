"""Module E (part): lightweight retrieval.

Primary retriever = BAAI/bge-small-zh-v1.5 sentence embeddings (HF, CPU/GPU).
Fallback = TF-IDF character n-grams, used when the embedding model cannot be
downloaded/loaded. The chosen backend is recorded in the run metadata.
"""
from __future__ import annotations

import math

import numpy as np


class EmbeddingRetriever:
    backend = "bge-small-zh-v1.5"

    def __init__(self, model_id: str, device: str = "cuda", dtype: str = "float32", batch_size: int = 32):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = device if torch.cuda.is_available() else "cpu"
        self.batch_size = batch_size
        torch_dtype = getattr(torch, dtype, torch.float32)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)
        try:
            self.model = AutoModel.from_pretrained(model_id, dtype=torch_dtype, trust_remote_code=False)
        except TypeError:
            self.model = AutoModel.from_pretrained(model_id, torch_dtype=torch_dtype, trust_remote_code=False)
        self.model = self.model.to(self.device).eval()
        self.docs: list[dict] = []
        self.matrix = None

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            encoded = self.tokenizer(batch, padding=True, truncation=True, max_length=256, return_tensors="pt").to(self.device)
            with self.torch.inference_mode():
                hidden = self.model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).float()
            summed = (hidden.float() * mask).sum(1)
            counts = mask.sum(1).clamp(min=1e-6)
            emb = summed / counts
            emb = self.torch.nn.functional.normalize(emb, p=2, dim=1)
            vectors.append(emb.cpu().numpy())
        return np.vstack(vectors)

    def index(self, documents: list[dict]) -> None:
        self.docs = list(documents)
        self.matrix = self._encode([d["text"] for d in self.docs])

    def search(self, question: str, top_k: int = 5) -> list[tuple[dict, float]]:
        q = self._encode([question])[0]
        scores = self.matrix @ q
        order = np.argsort(-scores)[:top_k]
        return [(self.docs[i], float(scores[i])) for i in order]


class TfidfRetriever:
    backend = "tfidf-char-ngram"

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=1)
        self.docs: list[dict] = []
        self.matrix = None

    def index(self, documents: list[dict]) -> None:
        self.docs = list(documents)
        self.matrix = self.vectorizer.fit_transform([d["text"] for d in self.docs])

    def search(self, question: str, top_k: int = 5) -> list[tuple[dict, float]]:
        from sklearn.metrics.pairwise import cosine_similarity

        q = self.vectorizer.transform([question])
        sims = cosine_similarity(q, self.matrix)[0]
        order = np.argsort(-sims)[:top_k]
        return [(self.docs[i], float(sims[i])) for i in order]


def build_retriever(cfg: dict, documents: list[dict]) -> object:
    model_cfg = cfg.get("models", {})
    if model_cfg.get("embedding_model"):
        try:
            retriever = EmbeddingRetriever(
                model_cfg["embedding_model"],
                device=model_cfg.get("device", "cuda"),
                dtype=model_cfg.get("embedding_dtype", "float32"),
            )
            retriever.index(documents)
            return retriever
        except Exception as exc:  # recorded by the caller via retriever.backend
            print(f"[retriever] embedding backend unavailable, falling back to TF-IDF: {exc}")
    retriever = TfidfRetriever()
    retriever.index(documents)
    return retriever
