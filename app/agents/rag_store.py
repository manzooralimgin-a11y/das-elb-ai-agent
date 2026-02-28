"""
Lightweight in-memory RAG Store for Das ELB.
Calculates embeddings for historical sent emails and performs vector search
to find the most similar human replies based on the current guest's inquiry.
"""
import logging
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class RagStore:
    def __init__(self):
        self.emails: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = None
        self.model = None

    def _load_model(self):
        if self.model is None:
            logger.info("Loading sentence-transformers model...")
            from sentence_transformers import SentenceTransformer
            # Small, fast model suitable for CPU 
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded successfully.")

    def update_index(self, sent_emails: List[Dict[str, Any]]) -> None:
        """
        Embed all provided emails and replace the current in-memory index.
        """
        if not sent_emails:
            logger.warning("No emails provided to RAG store. Index cleared.")
            self.emails = []
            self.embeddings = None
            return

        self._load_model()
        logger.info(f"Building RAG index for {len(sent_emails)} emails...")
        
        # We embed the "to" address, subject, and body to capture context
        texts_to_embed = []
        for e in sent_emails:
            text = f"Subject: {e.get('subject', '')}\nTo: {e.get('to_email', '')}\nBody:\n{e.get('body', '')}"
            texts_to_embed.append(text)

        # Generate embeddings as a numpy array
        self.embeddings = self.model.encode(texts_to_embed, convert_to_numpy=True)
        self.emails = sent_emails
        logger.info("RAG index update complete.")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Find the top_k most similar historical emails to the query.
        """
        if not self.emails or self.embeddings is None:
            logger.warning("RAG store is empty. No similarities found.")
            return []

        self._load_model()
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Embed the incoming guest email (query)
        query_embedding = self.model.encode([query], convert_to_numpy=True)

        # Calculate cosine similarity between query and all stored emails
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Get indices of top_k most similar
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            # Only return results with a decent similarity score (e.g., > 0.4)
            if similarities[idx] > 0.4:
                result = self.emails[idx].copy()
                result["similarity_score"] = float(similarities[idx])
                results.append(result)

        logger.info(f"Found {len(results)} similar past replies via RAG.")
        return results

# Global singleton instance
rag_store = RagStore()
