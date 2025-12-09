# vector_store.py
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from ai_companion.settings import settings

# qdrant client
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import Distance, PointStruct, VectorParams

# sentence-transformers
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    text: str
    metadata: dict
    score: Optional[float] = None

    @property
    def id(self) -> Optional[str]:
        return self.metadata.get("id")

    @property
    def timestamp(self) -> Optional[datetime]:
        ts = self.metadata.get("timestamp")
        return datetime.fromisoformat(ts) if ts else None


class VectorStore:
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "long_term_memory"
    SIMILARITY_THRESHOLD = 0.9

    _instance: Optional["VectorStore"] = None
    _initialized: bool = False

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Load embedding model
        self.model = SentenceTransformer(self.EMBEDDING_MODEL)

        # Validate envs and build client
        self._validate_env_vars()

        # Decide connection mode
        if settings.USE_LOCAL_QDRANT:
            host = settings.QDRANT_HOST or "qdrant"
            port = int(settings.QDRANT_PORT or 6333)
            logger.info("Connecting to LOCAL Qdrant at %s:%s", host, port)
            # QdrantClient(host, port) is fine for local docker
            self.client = QdrantClient(host=host, port=port)
        else:
            url = settings.QDRANT_URL
            api_key = settings.QDRANT_API_KEY
            # treat "None" or empty strings as None
            if isinstance(api_key, str) and api_key.strip().lower() == "none":
                api_key = None
            logger.info("Connecting to CLOUD Qdrant at %s", url)
            # prefer_grpc default can cause issues in some networks, set prefer_grpc=False to use HTTP
            self.client = QdrantClient(url=url, api_key=api_key, prefer_grpc=False, timeout=60.0)

        self._initialized = True

    def _validate_env_vars(self) -> None:
        if settings.USE_LOCAL_QDRANT:
            if not settings.QDRANT_HOST and not settings.QDRANT_PORT and not settings.QDRANT_URL:
                raise ValueError(
                    "Local Qdrant requires QDRANT_HOST/QDRANT_PORT or QDRANT_URL when USE_LOCAL_QDRANT=true"
                )
        else:
            missing = []
            if not settings.QDRANT_URL:
                missing.append("QDRANT_URL")
            if not settings.QDRANT_API_KEY:
                # allow empty if your cloud instance is public (rare) but warn
                logger.warning("QDRANT_API_KEY not set; ensure url accepts unauthenticated requests.")
            if missing:
                raise ValueError(f"Missing required cloud Qdrant variables: {', '.join(missing)}")

    def _collection_exists(self) -> bool:
        max_retries = 3
        target = settings.QDRANT_HOST if settings.USE_LOCAL_QDRANT else settings.QDRANT_URL
        for attempt in range(1, max_retries + 1):
            try:
                collections = self.client.get_collections().collections
                return any(col.name == self.COLLECTION_NAME for col in collections)
            except ResponseHandlingException as e:
                logger.warning(
                    "Attempt %d/%d: could not reach Qdrant (%s). Retrying in %ds... (%s)",
                    attempt, max_retries, target, attempt * 2, e,
                )
                time.sleep(attempt * 2)
            except Exception as e:
                logger.exception("Unexpected error when checking qdrant collections: %s", e)
                return False
        logger.error("Failed to contact Qdrant after %d attempts; treating collection as missing.", max_retries)
        return False

    def _create_collection(self) -> None:
        try:
            sample_embedding = self.model.encode("sample text")
            dim = len(sample_embedding) if hasattr(sample_embedding, "__len__") else len(list(sample_embedding))
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info("Created qdrant collection: %s", self.COLLECTION_NAME)
        except Exception as e:
            logger.exception("Failed to create qdrant collection: %s", e)
            raise

    def find_similar_memory(self, text: str) -> Optional[Memory]:
        results = self.search_memories(text, k=1)
        if results and results[0].score is not None and results[0].score >= self.SIMILARITY_THRESHOLD:
            return results[0]
        return None

    def store_memory(self, text: str, metadata: dict) -> None:
        if not self._collection_exists():
            try:
                logger.info("Collection '%s' not found. Creating it...", self.COLLECTION_NAME)
                self._create_collection()
            except Exception:
                logger.error("Could not create collection; skipping memory storage.")
                return

        similar_memory = self.find_similar_memory(text)
        if similar_memory and similar_memory.id:
            metadata["id"] = similar_memory.id

        embedding = self.model.encode(text)
        vector = embedding.tolist() if hasattr(embedding, "tolist") else list(map(float, embedding))
        point_id = metadata.get("id", str(abs(hash(text))))

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={"text": text, **metadata},
        )

        try:
            self.client.upsert(collection_name=self.COLLECTION_NAME, points=[point])
            logger.debug("Stored/updated memory id=%s", point_id)
        except Exception as e:
            logger.exception("Failed to upsert point into qdrant: %s", e)

    def search_memories(self, query: str, k: int = 5) -> List[Memory]:
        if not self._collection_exists():
            logger.debug("Collection does not exist or Qdrant unreachable; returning empty results.")
            return []

        try:
            query_embedding = self.model.encode(query)
            qvec = query_embedding.tolist() if hasattr(query_embedding, "tolist") else list(map(float, query_embedding))
            results = self.client.search(collection_name=self.COLLECTION_NAME, query_vector=qvec, limit=k)
        except Exception as e:
            logger.exception("Error while searching qdrant: %s", e)
            return []

        return [
            Memory(
                text=hit.payload.get("text", ""),
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
                score=getattr(hit, "score", None),
            )
            for hit in results
        ]


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()
