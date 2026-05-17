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
        'type_query_no_data':   '📋 Câu hỏi phân loại chưa có dữ liệu',
    'semantic_no_match':    '🔍 Semantic search không tìm thấy kết quả',
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
    #  PHƯƠNG THỨC MỚI CHO CÂU HỎI PHÂN LOẠI
    # =========================================================
    
    def save_type_query_missing(self, session_id: str, 
                                 user_question: str,
                                 category: str = '',
                                 confidence: float = 0.0) -> bool:
        """
        Lưu câu hỏi phân loại sản phẩm chưa có dữ liệu
        """
        bot_answer = f'[Chưa có dữ liệu phân loại cho {category}]' if category else ''
        return self.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer=bot_answer,
            product_context=category,
            user_feedback=f'type_query|category={category}|conf={confidence:.2f}',
            reason='type_query_no_data'
        )
    
    def save_semantic_no_match(self, session_id: str,
                                user_question: str,
                                top_scores: list = None) -> bool:
        """
        Lưu câu hỏi semantic search không tìm thấy kết quả
        """
        feedback = f'semantic_no_match|top_scores={top_scores}' if top_scores else ''
        return self.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer='[Semantic search không tìm thấy câu trả lời phù hợp]',
            user_feedback=feedback,
            reason='semantic_no_match'
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
    #  LỌC THEO CATEGORY VÀ TYPE
    # =========================================================
    
    def get_unresolved_by_category(self, category: str = '', limit: int = 50) -> List[Dict]:
        """
        Lọc câu hỏi chưa xử lý theo danh mục sản phẩm
        """
        items = self.get_unresolved_list(limit=limit)
        if not category:
            return items
        
        filtered = []
        category_lower = category.lower()
        
        for item in items:
            product_ctx = item.get('product_context', '').lower()
            question = item.get('question', '').lower()
            
            if category_lower in product_ctx or category_lower in question:
                filtered.append(item)
        
        return filtered
    
    def get_type_query_unresolved(self, limit: int = 50) -> List[Dict]:
        """
        Lấy các câu hỏi phân loại chưa được trả lời
        """
        items = self.get_unresolved_list(limit=limit, reason_filter='type_query_no_data')
        
        # Thêm các câu hỏi có chứa từ khóa phân loại
        type_keywords = ['loại', 'phân loại', 'các loại', 'những loại', 'dạng', 'kiểu']
        all_items = self.get_unresolved_list(limit=limit)
        
        for item in all_items:
            question = item.get('question', '').lower()
            if any(kw in question for kw in type_keywords):
                if item not in items:
                    items.append(item)
        
        return items[:limit]
    
    def get_semantic_failed_queries(self, limit: int = 30) -> List[Dict]:
        """
        Lấy các câu hỏi semantic search không tìm thấy kết quả
        """
        return self.get_unresolved_list(limit=limit, reason_filter='semantic_no_match')

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
        # =========================================================
    #  EXPORT CHO HUẤN LUYỆN SEMANTIC
    # =========================================================
    
    def export_for_training(self, output_path: str = 'data/training_data.json') -> str:
        """
        Export câu hỏi chưa trả lời thành file JSON để huấn luyện thêm
        """
        import json
        
        items = self.get_unresolved_list(limit=500)
        training_data = []
        
        for item in items:
            training_data.append({
                'question': item.get('question', ''),
                'answer': '',  # Admin sẽ điền sau
                'category': self._extract_category_from_question(item.get('question', '')),
                'reason': item.get('reason', ''),
                'timestamp': item.get('timestamp', ''),
                'priority': self._calculate_priority(item)
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Exported {len(training_data)} questions to {output_path}")
        return output_path
    
    def _extract_category_from_question(self, question: str) -> str:
        """Trích xuất category từ câu hỏi"""
        question_lower = question.lower()
        
        categories = {
            'kính râm': ['kính râm', 'kính mát', 'sunglass'],
            'kính cận': ['kính cận', 'kính thuốc'],
            'kính đổi màu': ['kính đổi màu', 'photochromic'],
        }
        
        for cat, keywords in categories.items():
            if any(kw in question_lower for kw in keywords):
                return cat
        
        return 'general'
    
    def _calculate_priority(self, item: Dict) -> int:
        """
        Tính priority (1-5) dựa trên số lần xuất hiện và reason
        5 = cần xử lý ngay, 1 = có thể để sau
        """
        question = item.get('question', '')
        
        # Kiểm tra tần suất
        freq_items = self.get_frequent_questions(20)
        for f in freq_items:
            if f['question'] == question.lower():
                if f['count'] >= 3:
                    return 5
                elif f['count'] >= 2:
                    return 4
        
        # Priority theo reason
        reason = item.get('reason', '')
        if 'missing_product' in reason:
            return 5
        elif 'type_query' in reason:
            return 4
        elif 'no_knowledge' in reason:
            return 3
        elif 'semantic_no_match' in reason:
            return 3
        
        return 2
    
    def get_training_summary(self) -> Dict:
        """
        Tổng kết dữ liệu cần huấn luyện thêm
        """
        type_queries = self.get_type_query_unresolved(100)
        semantic_fails = self.get_semantic_failed_queries(100)
        missing_products = self.get_unresolved_by_category('', 100)
        
        return {
            'total_unresolved': self.get_unresolved_count(),
            'type_queries_needed': len(type_queries),
            'semantic_failures': len(semantic_fails),
            'missing_products': len(missing_products),
            'by_reason': self.get_stats_by_reason(),
            'top_10_frequent': self.get_frequent_questions(10),
            'estimated_training_effort': self._estimate_effort()
        }
    
    def _estimate_effort(self) -> str:
        """Ước lượng công việc cần làm"""
        count = self.get_unresolved_count()
        
        if count == 0:
            return "✅ Không cần bổ sung"
        elif count <= 10:
            return "🟢 Nhẹ - có thể bổ sung trong 5-10 phút"
        elif count <= 30:
            return "🟡 Trung bình - cần 15-20 phút"
        elif count <= 50:
            return "🟠 Nhiều - cần 30-40 phút"
        else:
            return "🔴 Rất nhiều - ưu tiên xử lý các câu hỏi tần suất cao trước"

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
        # =========================================================
    #  MERGE DỮ LIỆU TỪ NHIỀU NGUỒN
    # =========================================================
    
    def merge_from_logs(self, log_path: str = 'chatbot.log') -> int:
        """
        Đọc log và trích xuất các câu hỏi chưa được trả lời
        """
        if not os.path.exists(log_path):
            return 0
        
        count = 0
        pattern = r'\[(.*?)\].*?>>> (.*?)$'
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    match = re.search(pattern, line)
                    if match:
                        timestamp = match.group(1)
                        question = match.group(2).strip()
                        
                        # Kiểm tra xem đã có trong unresolved chưa
                        existing = self.get_unresolved_list(limit=500)
                        if not any(q.get('question') == question for q in existing):
                            self.save_unresolved(
                                session_id='log_import',
                                user_question=question,
                                bot_answer='[Từ log]',
                                reason='no_knowledge'
                            )
                            count += 1
            
            logger.info(f"✅ Imported {count} questions from logs")
            return count
        except Exception as e:
            logger.error(f"Merge from logs error: {e}")
            return 0
    
    def clear_resolved(self, question_pattern: str = None) -> int:
        """
        Xóa các câu hỏi đã được giải quyết khỏi unresolved
        """
        items = self.get_unresolved_list(limit=1000)
        removed = 0
        
        try:
            # Đọc nội dung hiện tại
            with open(self.unresolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = []
            blocks = content.split('─' * 55)
            
            for block in blocks:
                if 'USER_QUESTION:' not in block:
                    if block.strip():
                        new_content.append(block)
                    continue
                
                # Kiểm tra có cần giữ lại không
                keep = True
                if question_pattern:
                    match = re.search(r'USER_QUESTION:\s*(.+)', block)
                    if match:
                        question = match.group(1).strip()
                        if question_pattern.lower() in question.lower():
                            keep = False
                            removed += 1
                
                if keep:
                    new_content.append(block)
            
            # Ghi lại
            with open(self.unresolved_path, 'w', encoding='utf-8') as f:
                f.write('─' * 55 + '\n'.join(new_content))
            
            logger.info(f"✅ Removed {removed} resolved questions")
            return removed
        except Exception as e:
            logger.error(f"Clear resolved error: {e}")
            return 0