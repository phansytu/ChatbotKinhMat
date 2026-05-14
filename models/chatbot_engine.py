"""
=============================================================
CHATBOT ENGINE - Fixed v2
=============================================================
Fix:
  1. Tìm sản phẩm DB: tìm cả bằng keyword khi không có tên cụ thể
  2. Lưu unresolved cho MỌI câu không trả lời được (không chỉ missing SP)
  3. Knowledge threshold thấp hơn (0.15)
  4. Log debug rõ ràng để dễ trace
=============================================================
"""

import logging, random
from typing import Dict, List, Optional
from collections import defaultdict

from models.knowledge_base    import KnowledgeBase
from models.intent_classifier import IntentClassifier
from models.product_advisor   import ProductAdvisor
from models.feedback_manager  import FeedbackManager
from utils.db_connector       import DatabaseConnector
from config import Config

logger = logging.getLogger(__name__)


class ChatbotEngine:

    def __init__(self, db_connector: DatabaseConnector = None):
        self.db        = db_connector
        self.knowledge = KnowledgeBase()
        self.clf       = IntentClassifier()
        self.advisor   = ProductAdvisor()
        self.feedback  = FeedbackManager(
            unresolved_path=Config.UNRESOLVED_FILE,
            resolved_path=Config.RESOLVED_FILE,
            knowledge_path=Config.KNOWLEDGE_FILE,
        )
        self._sessions: Dict[str, List] = defaultdict(list)

    # =========================================================
    #  PUBLIC
    # =========================================================

    def load_knowledge(self, path: str) -> Dict:
        return self.knowledge.load_file(path)

    def process_message(self, message: str, session_id: str = 'default') -> Dict:
        analysis  = self.clf.classify(message)
        intent    = analysis['intent']
        entities  = analysis['entities']
        conf      = analysis['confidence']
        is_neg    = analysis.get('is_negative_feedback', False)

        logger.info(f"[{session_id}] intent={intent} conf={conf:.2f} "
                    f"product='{entities.get('product_name','')}' "
                    f"neg={is_neg}")

        # Phản hồi tiêu cực từ khách
        if is_neg:
            return self._handle_negative(session_id, message, entities)

        self._push(session_id, 'user', message, intent, entities.get('product_name'))

        result = self._route(intent, entities, message, session_id, conf)
        self._push(session_id, 'bot', result['reply'], intent)
        return result

    # =========================================================
    #  ROUTING
    # =========================================================

    def _route(self, intent, entities, message, session_id, conf) -> Dict:

        if intent == 'greeting':
            return self._ok(self._greeting(), 'template', conf=1.0)
        if intent == 'thanks':
            return self._ok(random.choice([
                "Không có gì bạn ơi! Cần gì cứ hỏi thêm nhé 😊",
                "Dạ không có chi! Chúc bạn mua kính vui vẻ 🕶️",
            ]), 'template', conf=1.0)
        if intent == 'goodbye':
            return self._ok(random.choice([
                "Tạm biệt bạn! Khi nào cần tư vấn kính cứ quay lại nhé 👋",
                "Bye bạn! Chúc ngày tốt lành 😊",
            ]), 'template', conf=1.0)

        # ── Câu hỏi về sản phẩm cụ thể ───────────────────
        product_name = entities.get('product_name')
        if product_name or intent in ('ask_product', 'buy_intent'):
            return self._handle_product(product_name or message, entities, session_id, message)

        # ── Tìm kiếm theo tiêu chí ────────────────────────
        if intent in ('search_product', 'search_by_price', 'search_by_gender',
                      'search_by_material', 'search_by_style', 'consult_face',
                      'ask_discount'):
            return self._handle_search(intent, entities, message, session_id)

        # ── Câu hỏi tính năng / dịch vụ ──────────────────
        if intent in ('ask_blue_light', 'ask_uv', 'ask_photochromic',
                      'ask_shipping', 'ask_warranty', 'ask_payment', 'ask_compare'):
            return self._handle_knowledge(message, intent, session_id)

        # ── Fallback ──────────────────────────────────────
        return self._handle_fallback(message, entities, session_id)

    # =========================================================
    #  HỎI VỀ SẢN PHẨM CỤ THỂ
    # =========================================================

    def _handle_product(self, name_query: str, entities: Dict,
                         session_id: str, raw_message: str) -> Dict:
        """
        1. Tìm trong DB theo tên
        2. Tìm knowledge snippet liên quan
        3. Kết hợp thành tư vấn
        """
        products = []
        if self.db and self.db.test_connection():
            products = self.db.find_by_name(name_query, limit=3)
            logger.info(f"  DB find_by_name('{name_query}') → {len(products)} results")

        # Tìm knowledge snippet
        kn_snippet = self._knowledge_for_product(name_query, products)

        if not products:
            # Không có trong DB → lưu unresolved + gợi ý knowledge
            self.feedback.save_missing_product(session_id, name_query, raw_message)
            reply = self.advisor.build_not_found_reply(name_query)
            if kn_snippet:
                reply += f"\n\n💡 Shop có thể tư vấn chung:\n{kn_snippet}"
            return self._ok(reply, 'not_found', conf=0.3, unresolved=True)

        # Có sản phẩm → build reply đầy đủ
        if len(products) == 1:
            reply = self.advisor.build_product_reply(products[0], kn_snippet)
        else:
            reply = self.advisor.build_multi_product_reply(products, kn_snippet)

        return self._ok(reply, 'db+knowledge', products=products, conf=0.92)

    def _knowledge_for_product(self, name_query: str, products: List[Dict]) -> str:
        """Lấy snippet từ knowledge.txt liên quan đến sản phẩm"""
        if not self.knowledge.is_loaded():
            return ''

        # Danh sách terms để tìm: tên SP + brand + material + lens_type
        terms = [name_query]
        for p in products:
            for field in ('brand', 'frame_material', 'lens_type'):
                v = (p.get(field) or '').strip()
                if v and len(v) > 2:
                    terms.append(v)

        best_ans  = ''
        best_conf = 0.0
        for term in terms:
            res = self.knowledge.search(term, top_k=1, threshold=0.1)
            if res and res[0]['confidence'] > best_conf:
                best_conf = res[0]['confidence']
                best_ans  = res[0]['answer']

        return best_ans[:300] + ('...' if len(best_ans) > 300 else '')

    # =========================================================
    #  TÌM KIẾM THEO TIÊU CHÍ
    # =========================================================

    def _handle_search(self, intent, entities, message, session_id) -> Dict:
        filters = self._build_filters(intent, entities, message)
        products = []

        if self.db and self.db.test_connection() and filters:
            products = self.db.search_products({**filters, 'limit': Config.MAX_PRODUCTS_RETURN})
            logger.info(f"  DB search {filters} → {len(products)} products")

        # Knowledge snippet
        kn = self._search_knowledge(message)

        if products:
            intro = kn + "\n\n" if kn else ""
            intro += random.choice([
                "Dựa theo yêu cầu của bạn, shop gợi ý những mẫu này:",
                "Shop tìm được những sản phẩm phù hợp:",
                "Bạn xem qua những mẫu sau nhé:",
            ])
            return self._ok(intro, 'db_search', products=products, conf=0.85)

        if kn:
            return self._ok(kn, 'knowledge', conf=0.7)

        # Không có gì → lưu unresolved
        self.feedback.save_no_knowledge(session_id, message)
        return self._ok(
            "Shop chưa tìm được sản phẩm phù hợp 😅 "
            "Bạn mô tả thêm (giá, chất liệu, phong cách) để shop tư vấn chính xác hơn nhé!",
            'fallback', conf=0.2, unresolved=True
        )

    def _build_filters(self, intent, entities, message) -> Dict:
        f: Dict = {}
        if entities.get('price_min'):   f['min_price']      = entities['price_min']
        if entities.get('price_max'):   f['max_price']       = entities['price_max']
        if entities.get('gender'):      f['gender']          = entities['gender']
        if entities.get('material'):    f['frame_material']  = entities['material']
        if entities.get('face_shape'):  f['keyword']         = entities['face_shape']
        if entities.get('style'):       f['keyword']         = entities['style']
        if intent == 'ask_discount':    f['has_discount']    = True

        # Nếu chưa có keyword nào, dùng message gốc (loại bỏ stopwords)
        if not f.get('keyword') and not f.get('min_price') and not f.get('max_price'):
            kw = self._clean_keyword(message)
            if kw:
                f['keyword'] = kw
        return f

    @staticmethod
    def _clean_keyword(msg: str) -> str:
        noise = ['shop ơi', 'cho mình', 'cho tôi', 'cho em', 'bạn ơi',
                 'giúp mình', 'tư vấn', 'muốn mua', 'cần mua', 'tìm',
                 'kiếm', 'có bán', 'giới thiệu', 'gợi ý', 'show']
        m = msg.lower()
        for n in noise:
            m = m.replace(n, '')
        words = [w for w in m.split() if len(w) > 2]
        return ' '.join(words[:6])

    # =========================================================
    #  KNOWLEDGE ONLY
    # =========================================================

    def _handle_knowledge(self, message, intent, session_id) -> Dict:
        kn = self._search_knowledge(message)
        if kn:
            return self._ok(kn, 'knowledge', conf=0.8)

        # Không có trong knowledge → lưu unresolved
        self.feedback.save_no_knowledge(session_id, message)
        default = self._service_default(intent)
        return self._ok(default, 'template', conf=0.5, unresolved=True)

    def _search_knowledge(self, query: str) -> str:
        """Tìm trong knowledge.txt, trả về answer string hoặc rỗng"""
        if not self.knowledge.is_loaded():
            return ''
        res = self.knowledge.search(query, top_k=1, threshold=0.15)
        if res:
            logger.info(f"  Knowledge hit: conf={res[0]['confidence']:.2f} "
                        f"src={res[0]['source']} q='{res[0].get('matched_question','')[:40]}'")
            return res[0]['answer']
        return ''

    # =========================================================
    #  FALLBACK
    # =========================================================

    def _handle_fallback(self, message, entities, session_id) -> Dict:
        # Thử knowledge
        kn = self._search_knowledge(message)
        if kn:
            return self._ok(kn, 'knowledge', conf=0.6)

        # Thử DB với từ khóa thô
        if self.db and self.db.test_connection():
            kw = self._clean_keyword(message)
            if kw:
                products = self.db.search_products({'keyword': kw, 'limit': 3})
                if products:
                    return self._ok(
                        "Shop tìm được một số sản phẩm liên quan, bạn xem thử nhé:",
                        'db_fallback', products=products, conf=0.5
                    )

        # Thực sự không có gì → lưu unresolved
        self.feedback.save_fallback(session_id, message)
        return self._ok(random.choice([
            "Dạ shop chưa hiểu rõ câu hỏi 😅 Bạn có thể hỏi theo cách khác không? Ví dụ:\n"
            "• \"Kính RayBan Aviator giá bao nhiêu?\"\n"
            "• \"Gợi ý kính cho mặt tròn dưới 400k\"\n"
            "• \"Kính chống ánh sáng xanh loại nào tốt?\"",

            "Shop chưa nắm được ý bạn hỏi ơi 🤔 "
            "Bạn đang hỏi về sản phẩm cụ thể, giá cả, hay tính năng gì ạ?",
        ]), 'fallback', conf=0.1, unresolved=True)

    # =========================================================
    #  NEGATIVE FEEDBACK
    # =========================================================

    def _handle_negative(self, session_id, message, entities) -> Dict:
        history = self._sessions.get(session_id, [])
        prev_q, prev_a = '', ''
        for item in reversed(history[:-1]):
            if item['role'] == 'bot' and not prev_a:
                prev_a = item['message']
            elif item['role'] == 'user' and not prev_q and prev_a:
                prev_q = item['message']
                break

        self.feedback.save_unresolved(
            session_id=session_id,
            user_question=prev_q or message,
            bot_answer=prev_a,
            user_feedback=message,
            product_context=entities.get('product_name', ''),
            reason='user_complaint'
        )

        return self._ok(random.choice([
            "Xin lỗi bạn vì câu trả lời chưa đúng ý! 🙏 "
            "Bạn có thể mô tả lại cụ thể hơn không? Shop sẽ cố gắng tư vấn đúng hơn!",
            "Ối shop hiểu nhầm rồi, sorry bạn nhé 😅 "
            "Bạn muốn hỏi về điều gì cụ thể ạ?",
        ]), 'feedback', conf=1.0)

    # =========================================================
    #  HELPERS
    # =========================================================

    def _greeting(self) -> str:
        return random.choice([
            "Xin chào! 👋 Mình là trợ lý tư vấn kính mắt.\n"
            "Bạn cần:\n"
            "• Thông tin sản phẩm cụ thể?\n"
            "• Tư vấn chọn kính theo khuôn mặt?\n"
            "• Tìm kính theo giá / phong cách?\n"
            "Cứ hỏi thoải mái nhé! 😊",
            "Chào bạn! 🕶️ Shop kính mắt sẵn sàng tư vấn.\n"
            "Bạn đang tìm mẫu kính gì, hay cần tư vấn theo khuôn mặt?",
        ])

    @staticmethod
    def _service_default(intent: str) -> str:
        d = {
            'ask_shipping':    "Shop ship toàn quốc qua GHN/GHTK. Nội thành 1-2 ngày, tỉnh 2-4 ngày. Đơn trên 500k miễn phí ship!",
            'ask_warranty':    "Shop bảo hành gọng kính 6 tháng (bong sơn, gãy bản lề do lỗi sản xuất). Đổi trả 7 ngày nếu hàng không đúng mô tả!",
            'ask_payment':     "Thanh toán: chuyển khoản ngân hàng, Momo, ZaloPay, VNPay, hoặc COD (trả tiền khi nhận hàng).",
            'ask_blue_light':  "Tròng chống ánh sáng xanh lọc blue light từ màn hình, giúp mắt ít mỏi. Thêm 100-200k, rất xứng đáng nếu hay dùng máy tính!",
            'ask_uv':          "Kính mát bên shop đều có chống UV400, lọc 100% tia UVA và UVB. Bảo vệ mắt khỏi tia cực tím hiệu quả!",
            'ask_photochromic':"Kính đổi màu tự động tối khi ra nắng, trong suốt khi vào nhà. Tiện lợi thay cho 2 cặp kính. Giá từ 350k tróng!",
        }
        return d.get(intent, "Bạn có thể hỏi chi tiết hơn không ạ? Shop sẵn sàng tư vấn!")

    def _push(self, sid, role, msg, intent='', product_name=''):
        h = self._sessions[sid]
        h.append({'role': role, 'message': msg, 'intent': intent, 'product_name': product_name})
        max_len = Config.MAX_HISTORY_PER_SESSION * 2
        if len(h) > max_len:
            self._sessions[sid] = h[-max_len:]

    @staticmethod
    def _ok(text: str, source: str,
            products: List[Dict] = None,
            conf: float = 0.5,
            unresolved: bool = False) -> Dict:
        return {
            'reply':            text,
            'source':           source,
            'products':         products or [],
            'confidence':       conf,
            'is_unresolved':    unresolved,
            'unresolved_saved': unresolved,
        }

    # ─── Info ─────────────────────────────────────────────────

    def is_ready(self)         -> bool:       return self.knowledge.is_loaded()
    def get_topics(self)       -> List[str]:  return self.knowledge.get_topic_names()
    def get_qa_count(self)     -> int:        return self.knowledge.get_qa_count()
    def get_feedback_stats(self) -> Dict:     return self.feedback.get_stats()
    def get_session_history(self, sid: str) -> List[Dict]:
        return self._sessions.get(sid, [])