"""
=============================================================
KNOWLEDGE BASE - Fixed v2
=============================================================
Fix:
  1. Parse được mọi format file ngoài (không cần ## header)
  2. Threshold thực tế thấp hơn (0.15 thay vì 0.30)
  3. Matching tốt hơn: substring + partial word + TF-IDF
  4. Log rõ khi không tìm được để debug
=============================================================
"""

import re, os, logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class KnowledgeBase:

    def __init__(self):
        self.topics: Dict[str, str] = {}
        self.qa_pairs: List[Dict]   = []
        self.raw_sentences: List[Dict] = []
        self._is_loaded = False
        self._tfidf_matrix = None
        self._vectorizer   = None

    # =========================================================
    #  LOAD FILE
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

        self._parse_all_formats(content)
        self._extract_sentences_from_topics()
        self._build_tfidf()

        self._is_loaded = True
        stats = {
            'topics_count':    len(self.topics),
            'qa_count':        len(self.qa_pairs),
            'sentences_count': len(self.raw_sentences),
            'file_kb':         round(os.path.getsize(file_path) / 1024, 1),
        }
        logger.info(f"✅ Knowledge loaded: {stats}")
        return stats

    # =========================================================
    #  PARSE - hỗ trợ mọi format
    # =========================================================

    def _parse_all_formats(self, content: str):
        """
        Parse được tất cả các format phổ biến:
          Format 1: Q: ...  A: ...          (có trong knowledge.txt cũ)
          Format 2: Khách: ... Shop: ...    (hội thoại)
          Format 3: ## Chủ đề \n nội dung  (markdown header)
          Format 4: Nội dung tự do          (không có marker)
          Format 5: Câu hỏi? \n Trả lời.   (câu hỏi + dòng tiếp theo)
        """
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

            # ── Header chủ đề ──────────────────────────────
            if line.startswith('##') or line.startswith('# '):
                # Lưu Q&A đang dở
                if current_q and current_a_lines:
                    self._add_qa(current_q, ' '.join(current_a_lines), current_topic)
                    current_q, current_a_lines = None, []
                current_topic = re.sub(r'^#+\s*', '', line).strip()
                # Lấy ngày bổ sung nếu có: "Tư vấn (Bổ sung 2024-01-15)" → "Tư vấn"
                current_topic = re.sub(r'\s*\(.+\)\s*$', '', current_topic).strip()
                if not current_topic:
                    current_topic = 'Chung'
                self.topics.setdefault(current_topic, '')
                continue

            # ── Phân cách ──────────────────────────────────
            if re.match(r'^[-─=]{3,}$', line):
                if current_q and current_a_lines:
                    self._add_qa(current_q, ' '.join(current_a_lines), current_topic)
                    current_q, current_a_lines = None, []
                continue

            # ── Q: / Hỏi: / Khách: ─────────────────────────
            q_m = re.match(
                r'^(?:Q\s*:|Hỏi\s*:|Khách\s*:|Question\s*:)\s*(.+)',
                line, re.IGNORECASE
            )
            if q_m:
                if current_q and current_a_lines:
                    self._add_qa(current_q, ' '.join(current_a_lines), current_topic)
                current_q       = q_m.group(1).strip()
                current_a_lines = []
                continue

            # ── A: / Đáp: / Shop: / Answer: ────────────────
            a_m = re.match(
                r'^(?:A\s*:|Đáp\s*:|Shop\s*:|Answer\s*:|Trả lời\s*:)\s*(.+)',
                line, re.IGNORECASE
            )
            if a_m:
                current_a_lines.append(a_m.group(1).strip())
                # Gom thêm dòng tiếp theo nếu không có marker
                while i < len(lines):
                    nxt = lines[i].strip()
                    if not nxt:
                        break
                    if re.match(r'^(?:Q\s*:|A\s*:|Hỏi:|Khách:|Shop:|Đáp:|##|-----)', nxt, re.IGNORECASE):
                        break
                    current_a_lines.append(nxt)
                    i += 1
                continue

            # ── Nội dung gắn vào chủ đề hiện tại ──────────
            if current_topic and current_topic in self.topics:
                self.topics[current_topic] += (' ' + line)
            else:
                # Nếu chưa có topic nào, gắn vào Chung
                self.topics.setdefault('Chung', '')
                self.topics['Chung'] += (' ' + line)

        # Lưu cặp cuối
        if current_q and current_a_lines:
            self._add_qa(current_q, ' '.join(current_a_lines), current_topic)

        logger.info(f"  → topics={len(self.topics)}  qa_pairs={len(self.qa_pairs)}")

    def _add_qa(self, question: str, answer: str, topic: str = 'Chung'):
        q = question.strip()
        a = answer.strip()
        if not q or not a or len(a) < 3:
            return
        # Tránh trùng câu hỏi
        for existing in self.qa_pairs:
            if existing['question'].lower() == q.lower():
                existing['answer'] = a  # cập nhật nếu trùng
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

    # =========================================================
    #  TF-IDF INDEX
    # =========================================================

    def _build_tfidf(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            # Gộp Q&A questions + raw sentences
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
            logger.warning("  ⚠️  sklearn không có — dùng keyword matching")
        except Exception as e:
            logger.error(f"  TF-IDF build error: {e}")

    # =========================================================
    #  SEARCH - FIX CHÍNH
    # =========================================================

    def search(self, query: str, top_k: int = 3,
               threshold: float = 0.15) -> List[Dict]:
        """
        Tìm kiếm đa tầng:
          Tầng 1: Exact / Substring match (nhanh, chính xác cao)
          Tầng 2: Keyword overlap
          Tầng 3: TF-IDF cosine similarity
          Tầng 4: Partial word match (fallback)
        """
        if not self._is_loaded:
            return []

        all_results = []

        # Tầng 1 + 2: exact & keyword
        all_results.extend(self._search_exact_keyword(query, top_k * 2))

        # Tầng 3: TF-IDF
        if self._vectorizer is not None:
            all_results.extend(self._search_tfidf(query, top_k * 2))

        # Tầng 4: partial word fallback (khi không có kết quả nào)
        if not all_results or max((r['confidence'] for r in all_results), default=0) < 0.2:
            all_results.extend(self._search_partial(query, top_k))

        # Deduplicate + filter + sort
        seen = set()
        uniq = []
        for r in sorted(all_results, key=lambda x: x['confidence'], reverse=True):
            key = r['answer'][:60].lower().strip()
            if key not in seen:
                seen.add(key)
                uniq.append(r)

        filtered = [r for r in uniq if r['confidence'] >= threshold]

        if not filtered:
            logger.debug(f"  No results above threshold={threshold} for: '{query[:50]}'")
            # Log top scores để debug
            if uniq:
                top3 = uniq[:3]
                logger.debug(f"  Top candidates: " + "; ".join(
                    f"[{r['confidence']:.2f}] {r['answer'][:50]}" for r in top3
                )
)

        return filtered[:top_k]

    # ── Tầng 1+2: Exact / Substring / Keyword ─────────────

    def _search_exact_keyword(self, query: str, top_k: int) -> List[Dict]:
        q_low  = query.lower().strip()
        q_kws  = set(self._keywords(query))
        results = []

        for qa in self.qa_pairs:
            qa_low = qa['question'].lower().strip()
            score  = 0.0

            # Exact
            if q_low == qa_low:
                score = 1.0
            # Query là substring của câu hỏi
            elif q_low in qa_low:
                score = 0.85
            # Câu hỏi là substring của query
            elif qa_low in q_low:
                score = 0.80
            else:
                # Keyword overlap
                qa_kws = set(qa['keywords'])
                if q_kws and qa_kws:
                    overlap = len(q_kws & qa_kws)
                    if overlap > 0:
                        score = overlap / max(len(q_kws), len(qa_kws))
                        score = min(score * 1.3, 0.75)

            if score > 0.05:
                results.append({
                    'answer':           qa['answer'],
                    'source':           'qa_exact',
                    'confidence':       score,
                    'topic':            qa.get('topic', 'Chung'),
                    'matched_question': qa['question'],
                })

        # Tìm trong topic content cũng
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
                    'answer':     sent['text'],
                    'source':     'topic_match',
                    'confidence': score,
                    'topic':      sent.get('topic', 'Chung'),
                })

        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:top_k]

    # ── Tầng 3: TF-IDF ─────────────────────────────────────

    def _search_tfidf(self, query: str, top_k: int) -> List[Dict]:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            qv   = self._vectorizer.transform([query])
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
                        'answer':           qa['answer'],
                        'source':           'tfidf',
                        'confidence':       score,
                        'topic':            qa.get('topic', 'Chung'),
                        'matched_question': qa['question'],
                    })
                else:
                    si = idx - n_qa
                    if si < len(self.raw_sentences):
                        s = self.raw_sentences[si]
                        results.append({
                            'answer':     s['text'],
                            'source':     'tfidf_topic',
                            'confidence': score * 0.75,
                            'topic':      s.get('topic', 'Chung'),
                        })
            return results
        except Exception as e:
            logger.debug(f"TF-IDF search error: {e}")
            return []

    # ── Tầng 4: Partial word (fallback) ────────────────────

    def _search_partial(self, query: str, top_k: int) -> List[Dict]:
        """Tách query thành từng từ, tìm từng từ riêng lẻ"""
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
                    'answer':     qa['answer'],
                    'source':     'partial',
                    'confidence': score,
                    'topic':      qa.get('topic', 'Chung'),
                })

        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:top_k]

    # =========================================================
    #  HELPERS
    # =========================================================

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

    # ─── Public helpers ───────────────────────────────────

    def is_loaded(self)        -> bool:       return self._is_loaded
    def get_topic_names(self)  -> List[str]:  return list(self.topics.keys())
    def get_qa_count(self)     -> int:        return len(self.qa_pairs)