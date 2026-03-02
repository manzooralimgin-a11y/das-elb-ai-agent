"""
Lightweight in-memory RAG Store for Das ELB.
Calculates embeddings for historical sent emails and performs vector search
to find the most similar human replies based on the current guest's inquiry.
"""
import logging
from typing import List, Dict, Any
import numpy as np

import openai
from app.config import settings

logger = logging.getLogger(__name__)

class RagStore:
    def __init__(self):
        self.emails: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = None
        self.client = None

    def _load_client(self):
        if self.client is None:
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def update_index(self, sent_emails: List[Dict[str, Any]]) -> None:
        """
        Embed all provided emails and replace the current in-memory index.
        """
        if not sent_emails:
            logger.warning("No emails provided to RAG store. Index cleared.")
            self.emails = []
            self.embeddings = None
            return

        self._load_client()
        logger.info(f"Building RAG index for {len(sent_emails)} emails using OpenAI API...")
        
        # We embed the "to" address, subject, and body to capture context
        texts_to_embed = []
        for e in sent_emails:
            text = f"Subject: {e.get('subject', '')}\nTo: {e.get('to_email', '')}\nBody:\n{e.get('body', '')}"
            texts_to_embed.append(text[:8000]) # Cap to avoid 8192 token limit

        try:
            response = self.client.embeddings.create(
                input=texts_to_embed,
                model="text-embedding-3-small"
            )
            embeddings = [data.embedding for data in response.data]
            self.embeddings = np.array(embeddings)
            self.emails = sent_emails
            logger.info("RAG index update complete via OpenAI.")
        except Exception as e:
            logger.error(f"Failed to fetch embeddings from OpenAI: {e}")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Find the top_k most similar historical emails to the query.
        """
        if not self.emails or self.embeddings is None:
            logger.warning("RAG store is empty. No similarities found.")
            return []

        self._load_client()
        from sklearn.metrics.pairwise import cosine_similarity
        
        try:
            # Embed the incoming guest email (query)
            response = self.client.embeddings.create(
                input=[query[:8000]],
                model="text-embedding-3-small"
            )
            query_embedding = np.array([response.data[0].embedding])

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
        except Exception as e:
            logger.error(f"Failed RAG search query via OpenAI: {e}")
            return []

# Global singleton instance
rag_store = RagStore()
