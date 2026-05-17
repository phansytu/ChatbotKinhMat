"""
=============================================================
KNOWLEDGE BASE - WITH SEMANTIC SEARCH v3.0
=============================================================
Cải tiến: 
  1. Sử dụng sentence-transformers cho semantic search
  2. Cosine similarity giữa vector câu hỏi
  3. Hybrid search: semantic + keyword + TF-IDF
=============================================================
"""

import re
import os
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity

# Thử import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    logging.warning("sentence-transformers not installed. Run: pip install sentence-transformers")

logger = logging.getLogger(__name__)


class KnowledgeBase:

    def __init__(self):
        self.topics: Dict[str, str] = {}
        self.qa_pairs: List[Dict]   = []
        self.raw_sentences: List[Dict] = []
        self._is_loaded = False
        self._tfidf_matrix = None
        self._vectorizer   = None
        
        # Semantic search attributes
        self.semantic_model = None
        self.question_vectors = None
        self.semantic_enabled = False

    # =========================================================
    #  SEMANTIC SEARCH (THÊM MỚI)
    # =========================================================
    
    def init_semantic_model(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """Khởi tạo model embedding cho semantic search"""
        if not SEMANTIC_AVAILABLE:
            logger.warning("⚠️ Cannot init semantic model: sentence-transformers not installed")
            return False
        
        try:
            logger.info(f"Loading semantic model: {model_name}")
            self.semantic_model = SentenceTransformer(model_name)
            self.semantic_enabled = True
            logger.info("✅ Semantic model loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to load semantic model: {e}")
            self.semantic_enabled = False
            return False
    
    def build_semantic_embeddings(self):
        """Tạo vector embeddings cho tất cả câu hỏi"""
        if not self.semantic_enabled or not self.semantic_model:
            return
        
        if not self.qa_pairs:
            return
        
        questions = [qa['question'] for qa in self.qa_pairs]
        logger.info(f"Building embeddings for {len(questions)} questions...")
        
        try:
            self.question_vectors = self.semantic_model.encode(
                questions,
                convert_to_numpy=True,
                show_progress_bar=True,
                normalize_embeddings=True
            )
            logger.info(f"✅ Embeddings shape: {self.question_vectors.shape}")
        except Exception as e:
            logger.error(f"Failed to build embeddings: {e}")
            self.question_vectors = None
    
    def semantic_search(self, query: str, top_k: int = 3, threshold: float = 0.35) -> List[Dict]:
        """Tìm kiếm bằng cosine similarity"""
        if not self.semantic_enabled or self.question_vectors is None:
            return []
        
        try:
            query_vector = self.semantic_model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            
            similarities = np.dot(self.question_vectors, query_vector.T).flatten()
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                if score >= threshold:
                    qa = self.qa_pairs[idx]
                    results.append({
                        'answer': qa['answer'],
                        'question': qa['question'],
                        'confidence': score,
                        'source': 'semantic',
                        'topic': qa.get('topic', 'Chung')
                    })
            return results
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
    
    def hybrid_search(self, query: str, top_k: int = 3, 
                      semantic_weight: float = 0.6,
                      keyword_weight: float = 0.4) -> List[Dict]:
        """Hybrid search: kết hợp semantic + keyword"""
        semantic_results = self.semantic_search(query, top_k=top_k*2, threshold=0.2)
        keyword_results = self._search_exact_keyword(query, top_k=top_k*2)
        
        hybrid_map = {}
        
        for r in semantic_results:
            key = r['answer'][:100].lower()
            hybrid_map[key] = {
                'answer': r['answer'],
                'question': r.get('question', ''),
                'semantic_score': r['confidence'],
                'keyword_score': 0,
            }
        
        for r in keyword_results:
            key = r['answer'][:100].lower()
            if key in hybrid_map:
                hybrid_map[key]['keyword_score'] = r['confidence']
            else:
                hybrid_map[key] = {
                    'answer': r['answer'],
                    'question': r.get('matched_question', ''),
                    'semantic_score': 0,
                    'keyword_score': r['confidence'],
                }
        
        results = []
        for item in hybrid_map.values():
            hybrid_score = (semantic_weight * item['semantic_score'] + 
                          keyword_weight * item['keyword_score'])
            
            if len(item['answer']) > 500:
                hybrid_score += 0.05
            
            results.append({
                'answer': item['answer'],
                'question': item['question'],
                'confidence': min(hybrid_score, 1.0),
                'source': 'hybrid'
            })
        
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:top_k]

    # =========================================================
    #  LOAD FILE (GIỮ NGUYÊN NHƯNG THÊM BUILD EMBEDDINGS)
    # =========================================================

    def load_file(self, file_path: str) -> Dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy: {file_path}")

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Reset
        self.topics        = {}
        self.qa_pairs      = []
        self.raw_sentences = []
        self._tfidf_matrix = None
        self._vectorizer   = None
        self.question_vectors = None

        self._parse_all_formats(content)
        self._extract_sentences_from_topics()
        self._build_tfidf()

        # Build semantic embeddings nếu enabled
        if self.semantic_enabled and self.qa_pairs:
            self.build_semantic_embeddings()

        self._is_loaded = True
        stats = {
            'topics_count':    len(self.topics),
            'qa_count':        len(self.qa_pairs),
            'sentences_count': len(self.raw_sentences),
            'file_kb':         round(os.path.getsize(file_path) / 1024, 1),
            'semantic_enabled': self.semantic_enabled
        }
        logger.info(f"✅ Knowledge loaded: {stats}")
        return stats

    # =========================================================
    #  SEARCH - CẬP NHẬT ĐỂ DÙNG HYBRID
    # =========================================================

    def search(self, query: str, top_k: int = 3,
               threshold: float = 0.15, use_hybrid: bool = True) -> List[Dict]:
        """Tìm kiếm chính với hybrid search"""
        if not self._is_loaded:
            return []
        
        # Hybrid search
        if use_hybrid and self.semantic_enabled:
            hybrid_results = self.hybrid_search(query, top_k=top_k)
            if hybrid_results and hybrid_results[0]['confidence'] >= threshold:
                return hybrid_results
        
        # Fallback: keyword + TF-IDF
        return self._legacy_search(query, top_k, threshold)
    
    def _legacy_search(self, query: str, top_k: int, threshold: float) -> List[Dict]:
        """Phương thức tìm kiếm cũ (keyword + TF-IDF)"""
        all_results = []
        all_results.extend(self._search_exact_keyword(query, top_k * 2))
        
        if self._vectorizer is not None:
            all_results.extend(self._search_tfidf(query, top_k * 2))
        
        if not all_results:
            all_results.extend(self._search_partial(query, top_k))
        
        seen = set()
        uniq = []
        for r in sorted(all_results, key=lambda x: x['confidence'], reverse=True):
            key = r['answer'][:60].lower().strip()
            if key not in seen:
                seen.add(key)
                uniq.append(r)
        
        return [r for r in uniq if r['confidence'] >= threshold][:top_k]

    # =========================================================
    #  CÁC HÀM PHÍA DƯỚI GIỮ NGUYÊN (KHÔNG CẦN SỬA)
    # =========================================================

    def _parse_all_formats(self, content: str):
        """Parse file với nhiều format (giữ nguyên code cũ)"""
        lines = content.split('\n')
        current_topic   = 'Chung'
        current_q       = None
        current_a_lines = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            i += 1

            if not line or line.startswith('#!') or line.startswith('//'):
                continue

            if line.startswith('##') or line.startswith('# '):
                if current_q and current_a_lines:
                    self._add_qa(current_q, ' '.join(current_a_lines), current_topic)
                    current_q, current_a_lines = None, []
                current_topic = re.sub(r'^#+\s*', '', line).strip()
                current_topic = re.sub(r'\s*\(.+\)\s*$', '', current_topic).strip()
                if not current_topic:
                    current_topic = 'Chung'
                self.topics.setdefault(current_topic, '')
                continue

            if re.match(r'^[-─=]{3,}$', line):
                if current_q and current_a_lines:
                    self._add_qa(current_q, ' '.join(current_a_lines), current_topic)
                    current_q, current_a_lines = None, []
                continue

            q_m = re.match(r'^(?:Q\s*:|Hỏi\s*:|Khách\s*:|Question\s*:)\s*(.+)', line, re.IGNORECASE)
            if q_m:
                if current_q and current_a_lines:
                    self._add_qa(current_q, ' '.join(current_a_lines), current_topic)
                current_q = q_m.group(1).strip()
                current_a_lines = []
                continue

            a_m = re.match(r'^(?:A\s*:|Đáp\s*:|Shop\s*:|Answer\s*:|Trả lời\s*:)\s*(.+)', line, re.IGNORECASE)
            if a_m:
                current_a_lines.append(a_m.group(1).strip())
                while i < len(lines):
                    nxt = lines[i].strip()
                    if not nxt:
                        break
                    if re.match(r'^(?:Q\s*:|A\s*:|Hỏi:|Khách:|Shop:|Đáp:|##|-----)', nxt, re.IGNORECASE):
                        break
                    current_a_lines.append(nxt)
                    i += 1
                continue

            if current_topic and current_topic in self.topics:
                self.topics[current_topic] += (' ' + line)
            else:
                self.topics.setdefault('Chung', '')
                self.topics['Chung'] += (' ' + line)

        if current_q and current_a_lines:
            self._add_qa(current_q, ' '.join(current_a_lines), current_topic)

    def _add_qa(self, question: str, answer: str, topic: str = 'Chung'):
        q = question.strip()
        a = answer.strip()
        if not q or not a or len(a) < 3:
            return
        for existing in self.qa_pairs:
            if existing['question'].lower() == q.lower():
                existing['answer'] = a
                return
        self.qa_pairs.append({
            'question': q,
            'answer':   a,
            'topic':    topic or 'Chung',
            'keywords': self._keywords(q + ' ' + a),
        })

    def _extract_sentences_from_topics(self):
        for topic, content in self.topics.items():
            content = content.strip()
            if not content:
                continue
            for sent in re.split(r'[.!?\n]+', content):
                sent = sent.strip()
                if len(sent) > 15:
                    self.raw_sentences.append({
                        'text':     sent,
                        'topic':    topic,
                        'keywords': self._keywords(sent),
                    })

    def _build_tfidf(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            all_texts = [qa['question'] for qa in self.qa_pairs] + \
                        [s['text'] for s in self.raw_sentences]
            if len(all_texts) < 2:
                return
            self._vectorizer = TfidfVectorizer(
                analyzer='char_wb',
                ngram_range=(2, 4),
                min_df=1,
                max_features=8000,
                sublinear_tf=True
            )
            self._tfidf_matrix = self._vectorizer.fit_transform(all_texts)
            logger.info(f"  → TF-IDF {self._tfidf_matrix.shape}")
        except ImportError:
            logger.warning("  ⚠️ sklearn không có — dùng keyword matching")
        except Exception as e:
            logger.error(f"  TF-IDF build error: {e}")

    def _search_exact_keyword(self, query: str, top_k: int) -> List[Dict]:
        q_low = query.lower().strip()
        q_kws = set(self._keywords(query))
        results = []

        for qa in self.qa_pairs:
            qa_low = qa['question'].lower().strip()
            score = 0.0

            if q_low == qa_low:
                score = 1.0
            elif q_low in qa_low:
                score = 0.85
            elif qa_low in q_low:
                score = 0.80
            else:
                qa_kws = set(qa['keywords'])
                if q_kws and qa_kws:
                    overlap = len(q_kws & qa_kws)
                    if overlap > 0:
                        score = overlap / max(len(q_kws), len(qa_kws))
                        score = min(score * 1.3, 0.75)

            if score > 0.05:
                results.append({
                    'answer': qa['answer'],
                    'source': 'qa_exact',
                    'confidence': score,
                    'topic': qa.get('topic', 'Chung'),
                    'matched_question': qa['question'],
                })

        for sent in self.raw_sentences:
            s_low = sent['text'].lower()
            score = 0.0
            if q_low in s_low:
                score = 0.60
            elif s_low in q_low:
                score = 0.55
            else:
                s_kws = set(sent['keywords'])
                if q_kws and s_kws:
                    overlap = len(q_kws & s_kws)
                    if overlap > 0:
                        score = (overlap / max(len(q_kws), len(s_kws))) * 0.6

            if score > 0.1:
                results.append({
                    'answer': sent['text'],
                    'source': 'topic_match',
                    'confidence': score,
                    'topic': sent.get('topic', 'Chung'),
                })

        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:top_k]

    def _search_tfidf(self, query: str, top_k: int) -> List[Dict]:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            qv = self._vectorizer.transform([query])
            sims = cosine_similarity(qv, self._tfidf_matrix)[0]
            idxs = np.argsort(sims)[::-1][:top_k * 2]
            n_qa = len(self.qa_pairs)
            results = []

            for idx in idxs:
                score = float(sims[idx])
                if score < 0.05:
                    break
                if idx < n_qa:
                    qa = self.qa_pairs[idx]
                    results.append({
                        'answer': qa['answer'],
                        'source': 'tfidf',
                        'confidence': score,
                        'topic': qa.get('topic', 'Chung'),
                        'matched_question': qa['question'],
                    })
                else:
                    si = idx - n_qa
                    if si < len(self.raw_sentences):
                        s = self.raw_sentences[si]
                        results.append({
                            'answer': s['text'],
                            'source': 'tfidf_topic',
                            'confidence': score * 0.75,
                            'topic': s.get('topic', 'Chung'),
                        })
            return results
        except Exception as e:
            logger.debug(f"TF-IDF search error: {e}")
            return []

    def _search_partial(self, query: str, top_k: int) -> List[Dict]:
        words = [w for w in query.lower().split() if len(w) > 2]
        if not words:
            return []

        results = []
        for qa in self.qa_pairs:
            qa_text = (qa['question'] + ' ' + qa['answer']).lower()
            hit = sum(1 for w in words if w in qa_text)
            if hit > 0:
                score = (hit / len(words)) * 0.45
                results.append({
                    'answer': qa['answer'],
                    'source': 'partial',
                    'confidence': score,
                    'topic': qa.get('topic', 'Chung'),
                })

        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:top_k]

    _STOPWORDS = {
        'và','hoặc','là','có','không','của','cho','với','trong','ngoài','trên',
        'dưới','này','đó','khi','thì','mà','nhưng','vì','để','từ','đến','bởi',
        'tại','hay','cũng','đều','rất','khá','hơn','nhất','được','bị','làm',
        'như','theo','về','ra','vào','lên','xuống','qua','lại','đã','sẽ','đang',
        'cần','muốn','biết','thấy','nên','phải','bạn','shop','ạ','ơi','nhé',
        'nha','thôi','mình','em','anh','chị','dạ','vậy','ấy','thật'
    }

    def _keywords(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r'[^\w\sàáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]', ' ', text)
        words = text.split()
        return list(set(w for w in words if len(w) > 1 and w not in self._STOPWORDS))

    def is_loaded(self) -> bool:
        return self._is_loaded
    
    def get_topic_names(self) -> List[str]:
        return list(self.topics.keys())
    
    def get_qa_count(self) -> int:
        return len(self.qa_pairs)