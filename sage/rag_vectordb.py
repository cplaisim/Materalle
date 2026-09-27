"""
RAG Vector Database Integration using Qdrant.

Handles semantic search and document embedding for Retrieval-Augmented Generation (RAG).
Stores document embeddings in Qdrant and retrieves relevant documents for LLM context.
"""

import hashlib
import logging
from typing import List, Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "materalle_documents"


def get_qdrant_client():
    """Get or create Qdrant client connection."""
    try:
        from qdrant_client import QdrantClient

        if not settings.ENABLE_RAG_VECTORDB:
            logger.debug("RAG vectordb disabled in settings")
            return None

        client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        client.get_collections()  # Test connection
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        return None


def ensure_collection_exists(client):
    """Create collection if it doesn't exist."""
    try:
        from qdrant_client.models import Distance, VectorParams

        collections = client.get_collections()
        if any(c.name == COLLECTION_NAME for c in collections.collections):
            return

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
    except Exception as e:
        logger.error(f"Error creating Qdrant collection: {e}")


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for text using sentence-transformers or Ollama."""
    try:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except ImportError:
            logger.debug("sentence-transformers not installed, skipping embedding")
            return None
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None


def index_document(document_id: int, title: str, text: str) -> bool:
    """Index a document in Qdrant vector database."""
    if not text or not text.strip():
        logger.debug(f"Skipping indexing empty document {document_id}")
        return False

    client = get_qdrant_client()
    if not client:
        logger.debug("Qdrant client unavailable, skipping indexing")
        return False

    try:
        ensure_collection_exists(client)

        embedding = get_embedding(text)
        if not embedding:
            logger.debug(f"No embedding generated for document {document_id}")
            return False

        point_id = int(hashlib.md5(f"{document_id}".encode()).hexdigest()[:8], 16)

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                {
                    "id": point_id,
                    "vector": embedding,
                    "payload": {
                        "document_id": document_id,
                        "title": title,
                        "text": text[:5000],
                    }
                }
            ],
        )
        logger.info(f"Indexed document {document_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Error indexing document {document_id}: {e}")
        return False


def search_documents(query: str, limit: int = 3) -> List[Dict]:
    """Search for relevant documents using semantic search."""
    client = get_qdrant_client()
    if not client:
        logger.debug("Qdrant client unavailable, returning empty results")
        return []

    try:
        embedding = get_embedding(query)
        if not embedding:
            logger.debug("No embedding generated for query")
            return []

        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            limit=limit,
            score_threshold=0.5,
        )

        documents = []
        for result in results:
            doc = {
                "id": result.payload.get("document_id"),
                "title": result.payload.get("title"),
                "text": result.payload.get("text"),
                "score": result.score,
            }
            documents.append(doc)

        logger.debug(f"Found {len(documents)} relevant documents for query")
        return documents
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []


def delete_document(document_id: int) -> bool:
    """Remove a document from the vector database."""
    client = get_qdrant_client()
    if not client:
        return False

    try:
        point_id = int(hashlib.md5(f"{document_id}".encode()).hexdigest()[:8], 16)
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector={"points": [point_id]},
        )
        logger.info(f"Deleted document {document_id} from vector db")
        return True
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        return False
