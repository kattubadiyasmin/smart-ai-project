import re
import math
from collections import Counter

# Common English stop words to ignore during keyword scoring
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", 
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", 
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", 
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", 
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", 
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", 
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", 
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", 
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", 
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", 
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", 
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", 
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", 
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", 
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", 
    "yourself", "yourselves", "tell", "explain", "please", "can", "give"
}

def split_into_chunks(text, max_chunk_words=350, overlap_words=50):
    """
    Splits long extracted text into overlapping chunks based on paragraphs / sentences.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks = []
    current_words = []

    for para in paragraphs:
        para_words = para.split()
        if not para_words:
            continue

        if len(current_words) + len(para_words) <= max_chunk_words:
            current_words.extend(para_words)
        else:
            if current_words:
                chunks.append(" ".join(current_words))
                # Retain overlap words
                current_words = current_words[-overlap_words:] if len(current_words) > overlap_words else []
            
            # If paragraph itself is longer than max_chunk_words, break it into pieces
            while len(para_words) > max_chunk_words:
                sub_slice = para_words[:max_chunk_words]
                chunks.append(" ".join(sub_slice))
                para_words = para_words[max_chunk_words - overlap_words:]
            
            current_words.extend(para_words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks

def tokenize(text):
    """Tokenize and filter stop words and punctuation."""
    words = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
    return [w for w in words if w not in STOP_WORDS]

def retrieve_relevant_chunks(query, document_text, top_k=4):
    """
    Searches document chunks and ranks them based on query term frequency and phrase match.
    Returns:
        list of chunk strings, and boolean indicating whether high-confidence match exists.
    """
    if not document_text or not query:
        return [], False

    chunks = split_into_chunks(document_text)
    if not chunks:
        return [], False

    # If document is small enough (< 1200 words), return all chunks
    total_words = len(document_text.split())
    if total_words < 1200:
        return chunks, True

    query_tokens = tokenize(query)
    clean_query = query.lower().strip()

    if not query_tokens:
        # Fallback to the first few chunks if query had only stop words
        return chunks[:top_k], True

    scored_chunks = []
    for idx, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        chunk_tokens = tokenize(chunk)
        chunk_counter = Counter(chunk_tokens)
        
        score = 0.0
        # 1. Exact phrase bonus
        if len(clean_query) > 5 and clean_query in chunk_lower:
            score += 25.0
        
        # 2. Term frequency & matched unique query terms
        matched_terms = 0
        for token in query_tokens:
            if token in chunk_counter:
                matched_terms += 1
                tf = chunk_counter[token]
                # Log-dampened term frequency
                score += (1.0 + math.log(tf)) * 3.0
        
        # Coverage fraction bonus (how many of the query's keywords appear in this chunk)
        coverage = matched_terms / len(query_tokens)
        score += coverage * 10.0

        # Position slight bias (earlier introductory chunks get slight boost if equal)
        score += max(0, (len(chunks) - idx) / len(chunks)) * 0.5

        scored_chunks.append((score, chunk))

    # Sort descending by score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    top_scores = [item[0] for item in scored_chunks[:top_k]]
    has_relevant_match = any(s >= 3.0 for s in top_scores)
    
    selected_chunks = [item[1] for item in scored_chunks[:top_k]]
    return selected_chunks, has_relevant_match
