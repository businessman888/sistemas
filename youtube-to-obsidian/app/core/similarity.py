import re
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def _get_stopwords() -> List[str]:
    # Portuguese stopwords + common english
    return [
        "a", "o", "e", "é", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
        "um", "uma", "uns", "umas", "para", "por", "com", "como", "que", "seu", "sua", "seus", "suas",
        "ele", "ela", "eles", "elas", "eu", "nós", "você", "vocês", "me", "te", "se", "lhe", "lhes",
        "mais", "mas", "ou", "não", "sim", "já", "só", "também", "muito", "pouco", "tudo", "nada",
        "ser", "estar", "ter", "fazer", "ir", "poder", "dizer", "ver", "dar", "saber",
        "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas", "aquele", "aquela", "aqueles", "aquelas",
        "meu", "minha", "meus", "minhas", "teu", "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas",
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
        "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
        "so", "up", "out", "if", "about", "who", "get", "which", "go", "me"
    ]

def extract_keywords(text: str, top_k: int = 5) -> List[str]:
    """Extrai as top keywords de um texto usando TF-IDF."""
    if not text or not text.strip():
        return []
        
    stopwords = _get_stopwords()
    vectorizer = TfidfVectorizer(
        stop_words=stopwords,
        ngram_range=(1, 2),
        lowercase=True,
        max_df=0.8,
        min_df=1
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        
        # Obter os índices das palavras com maior TF-IDF
        dense = tfidf_matrix.todense()
        episode = dense[0].tolist()[0]
        phrase_scores = [pair for pair in zip(range(0, len(episode)), episode) if pair[1] > 0]
        sorted_phrase_scores = sorted(phrase_scores, key=lambda t: t[1] * -1)
        
        keywords = []
        for phrase, score in sorted_phrase_scores[:top_k]:
            kw = feature_names[phrase]
            # Normalizar
            kw = re.sub(r'[^a-z0-9]', '-', kw.lower())
            kw = re.sub(r'-+', '-', kw).strip('-')
            if kw:
                keywords.append(kw)
        return keywords
    except Exception:
        return []

def calculate_similarities(
    documents: Dict[str, str], 
    min_similarity: float = 0.1
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Calcula os vizinhos mais próximos para cada documento.
    documents: dicionário com chaves como IDs (ex: caminho do arquivo ou titulo) e valor o texto.
    Retorna um dicionário: ID -> lista de tuplas (ID_relacionado, score_similaridade)
    """
    if not documents or len(documents) < 2:
        return {doc_id: [] for doc_id in documents}
        
    doc_ids = list(documents.keys())
    texts = list(documents.values())
    
    stopwords = _get_stopwords()
    vectorizer = TfidfVectorizer(
        stop_words=stopwords,
        ngram_range=(1, 2),
        lowercase=True
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
        
        results = {}
        for i, doc_id in enumerate(doc_ids):
            # Obter pontuações para o doc i
            sim_scores = list(enumerate(cosine_sim[i]))
            # Filtrar o próprio doc e abaixo do min_similarity
            valid_scores = [(doc_ids[idx], score) for idx, score in sim_scores if idx != i and score >= min_similarity]
            # Ordenar do mais similar para o menos
            valid_scores = sorted(valid_scores, key=lambda x: x[1], reverse=True)
            results[doc_id] = valid_scores
            
        return results
    except Exception:
        return {doc_id: [] for doc_id in doc_ids}
