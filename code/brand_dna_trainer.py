"""
brand_dna_trainer.py — Auto-learn Brand DNA from corpus at startup.

This script scans the data/ folder and automatically builds Brand DNA maps
by analyzing the most frequent and discriminative terms in each company's
documentation.

Why? If a new company is added to data/, the agent learns its DNA without
code changes. This is self-healing and scales infinitely.

Algorithm:
1. For each company folder, scan all .md files
2. Extract all words, remove stopwords, calculate TF-IDF
3. Keep top-N words with highest IDF (most "unique" to this company)
4. Assign weights based on TF-IDF rank
5. Export as Python dict for config.py

Run once at startup or manually with: python brand_dna_trainer.py
"""

import os
import re
import math
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple

# Common English stopwords
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "must", "shall", "i", "you", "he",
    "she", "it", "we", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "its", "our", "their", "this", "that", "these", "those",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "as", "from", "up", "about", "into", "through", "during", "before",
    "after", "above", "below", "between", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "please", "also", "click", "go",
    "select", "help", "support", "issue", "request", "need", "contact", "via",
    "using", "example", "see", "etc", "like", "use", "used", "available", "make",
}


def tokenize(text: str) -> List[str]:
    """Extract and clean tokens from text."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = [t for t in text.split() if len(t) > 2 and t not in STOPWORDS]
    return tokens


def calculate_tfidf(documents: List[List[str]]) -> Dict[str, float]:
    """
    Calculate TF-IDF scores for all tokens across documents.

    Returns dict: {token: tfidf_score}
    """
    # Calculate IDF
    token_doc_count = defaultdict(int)
    for doc in documents:
        unique_tokens = set(doc)
        for token in unique_tokens:
            token_doc_count[token] += 1

    num_docs = len(documents)
    tfidf_scores = {}

    for token, doc_count in token_doc_count.items():
        # Only keep tokens that appear in multiple documents (more general signal)
        if doc_count > 1:
            idf = math.log(num_docs / doc_count)

            # Calculate average TF across documents
            tf_sum = 0
            for doc in documents:
                tf_sum += doc.count(token)
            tf_avg = tf_sum / num_docs

            tfidf_scores[token] = idf * tf_avg

    return tfidf_scores


def learn_brand_dna(company_folder: str, company_name: str, top_n: int = 50) -> Dict[str, float]:
    """
    Learn Brand DNA for a company by scanning all .md files in its folder.

    Returns: {keyword: weight} dict
    """
    print(f"\n[*] Learning DNA for {company_name}...")

    documents = []
    file_count = 0

    # Load all markdown files
    for md_file in Path(company_folder).rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            tokens = tokenize(text)
            if tokens:
                documents.append(tokens)
                file_count += 1
        except Exception as e:
            print(f"    [!] Error reading {md_file}: {e}")

    if not documents:
        print(f"    [!] No documents found for {company_name}")
        return {}

    print(f"    [+] Loaded {file_count} documents")

    # Calculate TF-IDF
    tfidf_scores = calculate_tfidf(documents)

    if not tfidf_scores:
        print(f"    [!] No TF-IDF scores calculated")
        return {}

    # Sort by score and keep top-N
    sorted_tokens = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Normalize scores to 0-1 range (max score becomes 0.95)
    max_score = sorted_tokens[0][1] if sorted_tokens else 1
    dna_map = {}
    for token, score in sorted_tokens:
        weight = 0.3 + (score / max_score * 0.65)  # Range: 0.3-0.95
        dna_map[token] = round(weight, 2)

    print(f"    [+] Learned {len(dna_map)} keywords")
    print(f"    [+] Top 5: {', '.join([f'{k}({v})' for k,v in list(sorted_tokens)[:5]])}")

    return dna_map


def main():
    """Main entry point."""
    print("""
    ====================================================================
    Brand DNA Trainer -- Auto-learn from corpus
    ====================================================================
    """)

    data_dir = Path("../data")

    if not data_dir.exists():
        print(f"[!] data/ directory not found at {data_dir}")
        print(f"[!] Run from the code/ directory")
        return

    # Scan for company folders
    companies = {}
    for item in sorted(data_dir.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            companies[item.name] = item

    if not companies:
        print("[!] No company folders found in data/")
        return

    print(f"\n[*] Found {len(companies)} companies: {', '.join(companies.keys())}")

    # Learn DNA for each company
    all_dna = {}
    for company_name, company_path in companies.items():
        dna = learn_brand_dna(str(company_path), company_name.title())
        if dna:
            all_dna[company_name.title()] = dna

    # Generate Python code
    print(f"\n\n{'='*68}")
    print("AUTO-GENERATED Brand DNA Maps (copy to config.py)")
    print(f"{'='*68}\n")

    for company_name, dna in all_dna.items():
        # Format as Python dict
        dna_str = "{\n"
        for i, (keyword, weight) in enumerate(sorted(dna.items(), key=lambda x: x[1], reverse=True)):
            if i % 3 == 0:
                dna_str += "    "
            dna_str += f'"{keyword}": {weight}'
            if i < len(dna) - 1:
                dna_str += ", "
            if (i + 1) % 3 == 0 or i == len(dna) - 1:
                dna_str += "\n"
        dna_str += "}"

        print(f"{company_name.upper()}_DNA = {dna_str}\n")

    print(f"{'='*68}")
    print("Replace the DNA maps in config.py with the above")
    print(f"{'='*68}\n")


if __name__ == "__main__":
    main()
