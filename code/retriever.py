"""
retriever.py — Gate 4: BM25-based Corpus Retrieval.

Uses BM25 (Best Match 25), the gold standard for keyword-based
information retrieval. No vector embeddings, no external API calls,
fully deterministic and fast.

BM25 handles:
- TF saturation: seeing "card" 10x doesn't score 10x more than 1x
- IDF weighting: rare words score higher than common words
- Length normalization: short and long documents score fairly

Architecture:
- Documents are loaded from data/ directory (all .md files)
- Split into chunks of BM25_CHUNK_SIZE words with 50% overlap
- Company is inferred from directory path (data/visa/, data/claude/, etc.)
- Index built once at startup, shared across all tickets
- Retrieval is O(1) lookup, O(N log N) for sorting by relevance
"""

import re
import logging
from pathlib import Path
from typing import List, Optional, Dict
from rank_bm25 import BM25Okapi
from config import DATA_DIR, BM25_TOP_K, BM25_CHUNK_SIZE, BM25_MIN_CHUNK_WORDS

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of a markdown document with metadata."""

    def __init__(self, text: str, source_file: str, chunk_id: int):
        """
        Initialize a document chunk.

        Args:
            text: The chunk text (plain markdown)
            source_file: Path to the source .md file (for citations)
            chunk_id: Sequential ID within the source file
        """
        self.text = text
        self.source_file = source_file
        self.chunk_id = chunk_id
        self.tokens = self._tokenize(text)

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing.

        Steps:
        1. Lowercase
        2. Remove non-alphanumeric (except spaces)
        3. Split on whitespace
        4. Filter tokens < 3 chars (removes noise)

        Args:
            text: Raw text to tokenize

        Returns:
            List of tokens ready for BM25
        """
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = [t for t in text.split() if len(t) > 2]
        return tokens


class CorpusRetriever:
    """BM25-based corpus retriever. Loads all .md files, builds index, retrieves on query."""

    def __init__(self):
        """Initialize retriever by loading corpus and building BM25 index."""
        self.chunks: List[DocumentChunk] = []
        self.company_chunks: Dict[str, List[int]] = {
            "Visa": [],
            "HackerRank": [],
            "Claude": [],
            "None": [],
        }
        self.bm25: Optional[BM25Okapi] = None
        self._load_corpus()
        self._build_index()
        logger.info(
            f"[RETRIEVER] Corpus loaded: {len(self.chunks)} chunks "
            f"from {len(set(c.source_file for c in self.chunks))} files"
        )

    def _load_corpus(self) -> None:
        """
        Load all .md files from data/ directory recursively.

        Process:
        1. Walk data/ directory
        2. For each .md file:
           a. Read content
           b. Chunk into BM25_CHUNK_SIZE-word segments
           c. Infer company from directory path
           d. Add chunks to corpus
        """
        data_path = Path(DATA_DIR)
        if not data_path.exists():
            raise FileNotFoundError(
                f"Data directory '{DATA_DIR}' not found. "
                f"Run from the repo root."
            )

        md_files = sorted(data_path.rglob("*.md"))
        logger.info(f"[RETRIEVER] Found {len(md_files)} markdown files")

        for md_file in md_files:
            # Skip release-notes files (contain too many generic keywords)
            if "release-notes" in md_file.parts or "release_notes" in md_file.parts:
                continue

            company = self._infer_company_from_path(md_file)
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
                chunks = self._chunk_text(text, str(md_file))
                for chunk in chunks:
                    chunk_index = len(self.chunks)
                    self.chunks.append(chunk)
                    self.company_chunks.setdefault(company, []).append(chunk_index)
            except Exception as e:
                logger.warning(f"[RETRIEVER] Failed to load {md_file}: {e}")

    def _infer_company_from_path(self, path: Path) -> str:
        """
        Determine company from file path.

        Maps directory names to companies:
        - "visa*" → Visa
        - "hackerrank*" → HackerRank
        - "claude*" → Claude
        - Anything else → None

        Args:
            path: Path object to the file

        Returns:
            Company name or "None"
        """
        path_str = str(path).lower()
        if "visa" in path_str:
            return "Visa"
        elif "hackerrank" in path_str:
            return "HackerRank"
        elif "claude" in path_str:
            return "Claude"
        return "None"

    def _chunk_text(self, text: str, source_file: str) -> List[DocumentChunk]:
        """
        Split text into overlapping chunks for retrieval.

        Strategy:
        - Chunk size: BM25_CHUNK_SIZE words
        - Overlap: 50% (stride = size / 2)
        - This ensures important info near chunk boundaries isn't lost

        Args:
            text: Full text to chunk
            source_file: Path to source file (for metadata)

        Returns:
            List of DocumentChunk objects
        """
        words = text.split()
        chunks = []
        step = BM25_CHUNK_SIZE // 2  # 50% overlap

        for i in range(0, max(1, len(words) - BM25_CHUNK_SIZE + step), step):
            chunk_words = words[i : i + BM25_CHUNK_SIZE]
            chunk_text = " ".join(chunk_words)

            # Skip near-empty chunks
            if len(chunk_text.strip().split()) >= BM25_MIN_CHUNK_WORDS:
                chunk_id = i
                chunks.append(DocumentChunk(chunk_text, source_file, chunk_id))

        return chunks

    def _build_index(self) -> None:
        """
        Build BM25 index from all tokenized chunks.

        This is a one-time operation at startup. Tokenization is
        done per chunk during _load_corpus(), so we just pass all
        token lists to BM25Okapi.
        """
        if not self.chunks:
            raise ValueError(
                "Corpus is empty. Check that data/ directory exists and contains .md files."
            )
        tokenized = [chunk.tokens for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized)
        logger.info(f"[RETRIEVER] BM25 index built for {len(tokenized)} chunks")

    def retrieve(
        self, query: str, company: str, top_k: int = BM25_TOP_K
    ) -> List[DocumentChunk]:
        """
        Retrieve top-k most relevant chunks for a query.

        Strategy:
        1. Tokenize query
        2. Score ALL chunks with BM25
        3. FILTER to company-relevant chunks (company is a hard filter)
        4. Return top-k from filtered set
        5. FALLBACK: If filtered set is empty, return global top-k

        This ensures company-specific routing (Visa ticket never pulls
        HackerRank docs) but still handles the "None" company case.

        Args:
            query: The search query (typically the ticket issue text)
            company: Company to filter by (Visa, HackerRank, Claude, or None)
            top_k: Number of chunks to return

        Returns:
            List of DocumentChunk objects, ranked by relevance
        """
        # Tokenize query using same logic as DocumentChunk
        query_chunk = DocumentChunk("", "", 0)
        query_tokens = query_chunk._tokenize(query)

        if not query_tokens:
            # Empty query → return top-k random chunks from company
            logger.warning(f"[RETRIEVER] Empty query, returning random chunks")
            relevant_indices = self.company_chunks.get(company, [])
            return [self.chunks[i] for i in relevant_indices[:top_k]]

        # Score all chunks with BM25
        all_scores = self.bm25.get_scores(query_tokens)

        # Get company-specific chunk indices
        relevant_indices = self.company_chunks.get(company, [])

        if relevant_indices:
            # Filter scores to company-specific chunks only
            # Apply penalty to release-notes files (they are less actionable)
            company_scores = []
            for i in relevant_indices:
                score = all_scores[i]
                # Penalize release-notes: multiply score by 0.5
                if "release-notes" in self.chunks[i].source_file.lower():
                    score *= 0.5
                company_scores.append((i, score))

            company_scores.sort(key=lambda x: x[1], reverse=True)
            top_indices = [i for i, _ in company_scores[:top_k]]
        else:
            # Fallback: global top-k (for company=None or unknown)
            logger.warning(
                f"[RETRIEVER] No company-specific chunks for '{company}', "
                f"using global top-k"
            )
            top_indices = sorted(
                range(len(all_scores)), key=lambda i: all_scores[i], reverse=True
            )[:top_k]

        # Return chunks with non-zero scores
        result = [
            self.chunks[i] for i in top_indices if all_scores[i] > 0
        ]
        return result
