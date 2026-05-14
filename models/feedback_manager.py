"""
=============================================================
FEEDBACK MANAGER - Fixed v2
=============================================================
Fix:
  1. Lưu TẤT CẢ câu hỏi bot không trả lời được (không chỉ missing product)
  2. Phân loại rõ: missing_product | low_confidence | user_complaint | no_knowledge
  3. Admin xem được đầy đủ câu hỏi cần bổ sung
=============================================================
"""

import os, re, logging
from datetime import datetime
from typing import List, Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)

# Phân loại lý do chưa trả lời được
REASON = {
    'missing_product':  '❌ Sản phẩm không có trong DB',
    'low_confidence':   '⚠️  Bot không chắc (confidence thấp)',
    'user_complaint':   '👎 Khách phản hồi chưa đúng',
    'no_knowledge':     '📚 Không có trong knowledge.txt',
    'fallback':         '🔄 Trả lời fallback chung',
}


class FeedbackManager:

    def __init__(self,
                 unresolved_path: str = 'data/unresolved.txt',
                 resolved_path:   str = 'data/resolved.txt',
                 knowledge_path:  str = 'data/knowledge.txt'):
        self.unresolved_path = unresolved_path
        self.resolved_path   = resolved_path
        self.knowledge_path  = knowledge_path
        self._lock = Lock()
        self._ensure_files()

    def _ensure_files(self):
        for path in [self.unresolved_path, self.resolved_path]:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(f"# Tạo lúc {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    # =========================================================
    #  LƯU CÂU HỎI CHƯA TRẢ LỜI ĐƯỢC
    # =========================================================

    def save_unresolved(self,
                        session_id:      str,
                        user_question:   str,
                        bot_answer:      str  = '',
                        user_feedback:   str  = '',
                        product_context: str  = '',
                        reason:          str  = 'low_confidence') -> bool:
        """
        Lưu câu hỏi chưa trả lời đúng vào unresolved.txt.

        reason:
          missing_product  - tên SP có trong câu hỏi nhưng không có trong DB
          low_confidence   - bot trả lời nhưng confidence < ngưỡng
          user_complaint   - khách bấm "chưa đúng"
          no_knowledge     - không tìm được trong knowledge.txt
          fallback         - bot trả lời fallback chung chung
        """
        try:
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reason_label = REASON.get(reason, reason)

            with self._lock:
                with open(self.unresolved_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n[{ts}] SESSION:{session_id}\n")
                    f.write(f"REASON: {reason_label}\n")
                    f.write(f"USER_QUESTION: {user_question.strip()}\n")
                    if bot_answer:
                        f.write(f"BOT_ANSWER: {bot_answer.strip()[:300]}\n")
                    if user_feedback:
                        f.write(f"USER_FEEDBACK: {user_feedback.strip()}\n")
                    if product_context:
                        f.write(f"PRODUCT_CONTEXT: {product_context.strip()}\n")
                    f.write(f"STATUS: unresolved\n")
                    f.write(f"{'─' * 55}\n")

            logger.info(f"💾 Unresolved [{reason}]: '{user_question[:60]}'")
            return True
        except Exception as e:
            logger.error(f"save_unresolved error: {e}")
            return False

    def save_missing_product(self, session_id: str, product_name: str,
                              user_question: str) -> bool:
        return self.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer='[Sản phẩm không tìm thấy trong database]',
            product_context=product_name,
            reason='missing_product'
        )

    def save_no_knowledge(self, session_id: str, user_question: str,
                           bot_answer: str = '') -> bool:
        return self.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer=bot_answer,
            reason='no_knowledge'
        )

    def save_low_confidence(self, session_id: str, user_question: str,
                             bot_answer: str, confidence: float) -> bool:
        return self.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer=bot_answer,
            user_feedback=f'[AUTO] confidence={confidence:.2f}',
            reason='low_confidence'
        )

    def save_fallback(self, session_id: str, user_question: str) -> bool:
        return self.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer='[Fallback]',
            reason='fallback'
        )

    # =========================================================
    #  ĐỌC UNRESOLVED
    # =========================================================

    def get_unresolved_list(self, limit: int = 100,
                             reason_filter: str = '') -> List[Dict]:
        """
        Đọc danh sách câu hỏi chưa xử lý.

        reason_filter: lọc theo loại (để rỗng = lấy tất cả)
        """
        items = []
        try:
            if not os.path.exists(self.unresolved_path):
                return []
            with open(self.unresolved_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for block in content.split('─' * 55):
                block = block.strip()
                if 'USER_QUESTION:' not in block:
                    continue
                item = self._parse_block(block)
                if not item:
                    continue
                if reason_filter and reason_filter not in item.get('reason', ''):
                    continue
                items.append(item)

        except Exception as e:
            logger.error(f"get_unresolved error: {e}")

        # Mới nhất lên đầu, giới hạn limit
        return list(reversed(items))[:limit]

    def get_unresolved_count(self) -> int:
        try:
            if not os.path.exists(self.unresolved_path):
                return 0
            with open(self.unresolved_path, 'r', encoding='utf-8') as f:
                return f.read().count('STATUS: unresolved')
        except Exception:
            return 0

    def get_frequent_questions(self, top_n: int = 10) -> List[Dict]:
        """Câu hỏi xuất hiện nhiều lần — ưu tiên bổ sung trước"""
        items = self.get_unresolved_list(limit=500)
        freq: Dict[str, int] = {}
        for it in items:
            q = it.get('question', '').lower().strip()
            if q:
                freq[q] = freq.get(q, 0) + 1
        return [{'question': q, 'count': c}
                for q, c in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]]

    def get_stats_by_reason(self) -> Dict[str, int]:
        """Thống kê số lượng theo loại lý do"""
        items = self.get_unresolved_list(limit=1000)
        stats: Dict[str, int] = {}
        for it in items:
            r = it.get('reason', 'other')
            stats[r] = stats.get(r, 0) + 1
        return stats

    # =========================================================
    #  BỔ SUNG ĐÁP ÁN → KNOWLEDGE
    # =========================================================

    def add_answer_to_knowledge(self, question: str, answer: str,
                                 topic: str = 'Bổ sung từ feedback') -> bool:
        """Ghi Q&A mới vào knowledge.txt — bot học ngay khi retrain"""
        try:
            with self._lock:
                with open(self.knowledge_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n## {topic}\n\n")
                    f.write(f"Q: {question.strip()}\n")
                    f.write(f"A: {answer.strip()}\n\n")
                    f.write("-----\n")
            self._log_resolved(question, answer)
            logger.info(f"✅ Added Q&A: '{question[:60]}'")
            return True
        except Exception as e:
            logger.error(f"add_answer error: {e}")
            return False

    def bulk_add_from_unresolved(self, qa_pairs: List[Dict]) -> int:
        count = 0
        for p in qa_pairs:
            q = p.get('question', '').strip()
            a = p.get('answer', '').strip()
            t = p.get('topic', 'Bổ sung từ feedback')
            if q and a and self.add_answer_to_knowledge(q, a, t):
                count += 1
        return count

    def generate_knowledge_template(self) -> str:
        """Tạo file template để admin điền đáp án"""
        items = self.get_unresolved_list(limit=200)
        if not items:
            return ''
        path = 'data/knowledge_template.txt'
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"# TEMPLATE BỔ SUNG - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write("# Điền A: rồi copy vào knowledge.txt và gọi /api/retrain\n\n")
                f.write("## Câu hỏi cần bổ sung\n\n")
                seen = set()
                for it in items:
                    q = it.get('question', '').strip()
                    if q and q not in seen:
                        seen.add(q)
                        reason = it.get('reason', '')
                        f.write(f"# {reason}\n")
                        f.write(f"Q: {q}\n")
                        f.write("A: [ĐIỀN ĐÁP ÁN VÀO ĐÂY]\n\n")
                f.write("-----\n")
            return path
        except Exception as e:
            logger.error(f"Template error: {e}")
            return ''

    def get_stats(self) -> Dict:
        return {
            'unresolved_count': self.get_unresolved_count(),
            'by_reason':        self.get_stats_by_reason(),
            'top_questions':    self.get_frequent_questions(5),
        }

    # ─── Parse ────────────────────────────────────────────────

    @staticmethod
    def _parse_block(block: str) -> Optional[Dict]:
        item = {}
        for line in block.split('\n'):
            line = line.strip()
            if not line:
                continue
            if re.match(r'^\[.+\]\s*SESSION:', line):
                m = re.match(r'^\[(.+?)\]\s*SESSION:(\S+)', line)
                if m:
                    item['timestamp']  = m.group(1)
                    item['session_id'] = m.group(2)
            elif line.startswith('REASON:'):
                item['reason'] = line[7:].strip()
            elif line.startswith('USER_QUESTION:'):
                item['question'] = line[14:].strip()
            elif line.startswith('BOT_ANSWER:'):
                item['bot_answer'] = line[11:].strip()
            elif line.startswith('USER_FEEDBACK:'):
                item['user_feedback'] = line[14:].strip()
            elif line.startswith('PRODUCT_CONTEXT:'):
                item['product_context'] = line[16:].strip()
            elif line.startswith('STATUS:'):
                item['status'] = line[7:].strip()
        return item if 'question' in item else None

    def _log_resolved(self, question: str, answer: str):
        try:
            with open(self.resolved_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
                f.write(f"Q: {question.strip()}\n")
                f.write(f"A: {answer.strip()[:200]}\n")
                f.write("─" * 40 + "\n")
        except Exception:
            pass