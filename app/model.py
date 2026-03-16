import os
from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = os.getenv("MODEL_NAME", "intfloat/multilingual-e5-base")
MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")

class EmbedModel:
    def __init__(self):
        self._model = None
        self._loaded = False
        self._load()

    def _load(self):
        try:
            model_path = os.path.join(MODEL_DIR, MODEL_NAME.replace("/", "_"))
            if os.path.exists(model_path):
                self._model = SentenceTransformer(model_path)
            else:
                self._model = SentenceTransformer(MODEL_NAME)
                os.makedirs(model_path, exist_ok=True)
                self._model.save(model_path)
            self._loaded = True
        except Exception as e:
            print(f"[embed] 모델 로드 실패: {e}")
            self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def encode(self, text: str) -> np.ndarray:
        if not self._loaded:
            raise RuntimeError("Model not loaded")
        return self._model.encode(text, normalize_embeddings=True)

    def encode_batch(self, texts: list) -> list:
        if not self._loaded:
            raise RuntimeError("Model not loaded")
        return self._model.encode(texts, batch_size=32, normalize_embeddings=True)
