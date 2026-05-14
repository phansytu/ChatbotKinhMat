"""
=============================================================
FLASK APP v2 - Chatbot Kính Mắt
=============================================================
Endpoints:
  POST /api/chat              - Nhận tin nhắn, trả lời
  POST /api/feedback/negative - Đánh dấu câu trả lời sai
  POST /api/feedback/add-qa   - Admin bổ sung Q&A mới
  GET  /api/feedback/list     - Xem danh sách câu hỏi chưa xử lý
  GET  /api/feedback/stats    - Thống kê feedback
  POST /api/retrain           - Huấn luyện lại từ knowledge.txt
  GET  /api/health            - Trạng thái server
  GET  /api/topics            - Danh sách chủ đề đã học
=============================================================
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging
import os
from datetime import datetime

from models.chatbot_engine import ChatbotEngine
from utils.db_connector import DatabaseConnector
from config import Config

# ─── App ──────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('chatbot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Khởi tạo ─────────────────────────────────────────
db     = DatabaseConnector()
engine = ChatbotEngine(db_connector=db)

if os.path.exists(Config.KNOWLEDGE_FILE):
    stats = engine.load_knowledge(Config.KNOWLEDGE_FILE)
    logger.info(f"✅ Knowledge: {stats}")
else:
    logger.warning("⚠️  knowledge.txt not found")


# =============================================================
#  GIAO DIỆN
# =============================================================

@app.route('/')
def index():
    return render_template('index.html')


# =============================================================
#  CHAT API
# =============================================================

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Nhận tin nhắn → phân tích → trả lời kết hợp DB + knowledge.

    Request:
      { "message": str, "session_id": str (optional) }

    Response:
      {
        "reply": str,
        "source": str,          # db+knowledge | knowledge | db_search | fallback...
        "products": [...],
        "confidence": float,
        "session_id": str,
        "is_unresolved": bool,  # True nếu bot không chắc
        "timestamp": str
      }
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Thiếu trường message'}), 400

        message    = data.get('message', '').strip()
        session_id = data.get('session_id', f"web_{datetime.now().strftime('%H%M%S')}")

        if not message:
            return jsonify({'error': 'Tin nhắn rỗng'}), 400
        if len(message) > 1000:
            return jsonify({'error': 'Tin nhắn quá dài'}), 400

        logger.info(f"[{session_id}] >>> {message[:80]}")

        result = engine.process_message(
            message=message,
            session_id=session_id,
        )

        logger.info(f"[{session_id}] <<< ({result['source']}, {result['confidence']:.2f}): "
                    f"{result['reply'][:60]}")

        return jsonify({
            'reply':            result['reply'],
            'source':           result['source'],
            'products':         result.get('products', []),
            'confidence':       round(result.get('confidence', 0), 3),
            'session_id':       session_id,
            'is_unresolved':    result.get('is_unresolved', False),
            'unresolved_saved': result.get('unresolved_saved', False),
            'timestamp':        datetime.now().isoformat(),
        })

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({
            'reply': 'Xin lỗi, hệ thống gặp sự cố. Vui lòng thử lại sau!',
            'source': 'error'
        }), 500


# =============================================================
#  FEEDBACK API
# =============================================================

@app.route('/api/feedback/negative', methods=['POST'])
def feedback_negative():
    """
    Khách đánh dấu câu trả lời chưa đúng.
    Câu hỏi + câu trả lời cũ sẽ được lưu vào unresolved.txt.

    Request:
      {
        "session_id": str,
        "user_question": str,    # câu hỏi gốc
        "bot_answer": str,       # câu trả lời sai
        "user_feedback": str,    # user nói sai ở điểm gì (optional)
        "product_context": str   # tên SP đang hỏi (optional)
      }
    """
    try:
        data = request.get_json() or {}
        session_id      = data.get('session_id', 'unknown')
        user_question   = data.get('user_question', '').strip()
        bot_answer      = data.get('bot_answer', '').strip()
        user_feedback   = data.get('user_feedback', '').strip()
        product_context = data.get('product_context', '').strip()

        if not user_question:
            return jsonify({'error': 'Thiếu user_question'}), 400

        saved = engine.feedback.save_unresolved(
            session_id=session_id,
            user_question=user_question,
            bot_answer=bot_answer,
            user_feedback=user_feedback,
            product_context=product_context
        )

        return jsonify({
            'status': 'saved' if saved else 'error',
            'message': 'Đã ghi nhận phản hồi. Shop sẽ cải thiện câu trả lời!',
            'unresolved_count': engine.feedback.get_unresolved_count()
        })

    except Exception as e:
        logger.error(f"Feedback error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/feedback/list', methods=['GET'])
def feedback_list():
    """
    Xem danh sách câu hỏi chưa được trả lời đúng.
    Dành cho admin để bổ sung knowledge.

    Query params:
      limit: số kết quả (default 50)
    """
    limit = request.args.get('limit', 50, type=int)
    items = engine.feedback.get_unresolved_list(limit=limit)
    freq  = engine.feedback.get_frequent_questions(10)

    return jsonify({
        'unresolved': items,
        'count': len(items),
        'total_unresolved': engine.feedback.get_unresolved_count(),
        'frequent_questions': freq,
    })


@app.route('/api/feedback/stats', methods=['GET'])
def feedback_stats():
    """Thống kê feedback"""
    return jsonify(engine.get_feedback_stats())


@app.route('/api/feedback/add-qa', methods=['POST'])
def feedback_add_qa():
    """
    Admin bổ sung Q&A mới vào knowledge.txt.
    Tự động retrain sau khi thêm.

    Request:
      {
        "question": str,
        "answer": str,
        "topic": str (optional),
        "retrain": true (optional, default true)
      }

    Hoặc batch:
      {
        "qa_pairs": [{"question": ..., "answer": ..., "topic": ...}, ...]
      }
    """
    try:
        data = request.get_json() or {}

        # Batch mode
        if 'qa_pairs' in data:
            count = engine.feedback.bulk_add_from_unresolved(data['qa_pairs'])
            if data.get('retrain', True) and count > 0:
                engine.load_knowledge(Config.KNOWLEDGE_FILE)
            return jsonify({
                'status': 'success',
                'added': count,
                'message': f'Đã thêm {count} cặp Q&A và huấn luyện lại!'
            })

        # Single mode
        question = data.get('question', '').strip()
        answer   = data.get('answer', '').strip()
        topic    = data.get('topic', 'Tư vấn sản phẩm')

        if not question or not answer:
            return jsonify({'error': 'Thiếu question hoặc answer'}), 400

        saved = engine.feedback.add_answer_to_knowledge(question, answer, topic)

        # Retrain ngay
        if saved and data.get('retrain', True):
            stats = engine.load_knowledge(Config.KNOWLEDGE_FILE)
            return jsonify({
                'status': 'success',
                'message': 'Đã thêm Q&A và huấn luyện lại thành công!',
                'retrain_stats': stats
            })

        return jsonify({
            'status': 'success' if saved else 'error',
            'message': 'Đã thêm Q&A vào knowledge.txt'
        })

    except Exception as e:
        logger.error(f"Add QA error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/feedback/generate-template', methods=['POST'])
def generate_template():
    """
    Tạo file template từ unresolved.txt để admin điền đáp án.
    """
    path = engine.feedback.generate_knowledge_template()
    if path:
        return jsonify({
            'status': 'success',
            'template_path': path,
            'message': 'Mở file data/knowledge_template.txt, điền A: rồi gọi /api/retrain'
        })
    return jsonify({'status': 'empty', 'message': 'Không có câu hỏi nào chưa xử lý'}), 200


# =============================================================
#  RETRAIN
# =============================================================

@app.route('/api/retrain', methods=['POST'])
def retrain():
    """
    Huấn luyện lại chatbot từ knowledge.txt.
    Gọi sau khi thêm Q&A mới.
    """
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path', Config.KNOWLEDGE_FILE)

        if not os.path.exists(file_path):
            return jsonify({'error': f'File không tồn tại: {file_path}'}), 404

        stats = engine.load_knowledge(file_path)
        logger.info(f"✅ Retrain: {stats}")

        return jsonify({
            'status': 'success',
            'message': '🎉 Huấn luyện lại thành công!',
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================
#  UTILITY
# =============================================================

@app.route('/api/health', methods=['GET'])
def health():
    db_ok = db.test_connection()
    stats = db.get_statistics() if db_ok else {}
    fb_stats = engine.get_feedback_stats()
    return jsonify({
        'status':           'ok',
        'database':         'connected' if db_ok else 'disconnected',
        'db_stats':         stats,
        'knowledge_loaded': engine.is_ready(),
        'topics_count':     len(engine.get_topics()),
        'qa_count':         engine.get_qa_count(),
        'unresolved_count': fb_stats.get('unresolved_count', 0),
        'timestamp':        datetime.now().isoformat(),
        'version':          '2.0.0'
    })


@app.route('/api/topics', methods=['GET'])
def topics():
    t = engine.get_topics()
    return jsonify({'topics': t, 'count': len(t)})


@app.route('/api/products/search', methods=['GET'])
def products_search():
    """Tìm kiếm sản phẩm trực tiếp"""
    if not db.test_connection():
        return jsonify({'error': 'Database không khả dụng'}), 503
    filters = {
        'keyword':        request.args.get('q', ''),
        'brand':          request.args.get('brand', ''),
        'gender':         request.args.get('gender', ''),
        'frame_material': request.args.get('material', ''),
        'min_price':      request.args.get('min_price', type=float),
        'max_price':      request.args.get('max_price', type=float),
        'sort':           request.args.get('sort', 'rating'),
        'limit':          request.args.get('limit', 10, type=int),
    }
    products = db.search_products(filters)
    return jsonify({'products': products, 'count': len(products)})


# =============================================================
#  MAIN
# =============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  CHATBOT TƯ VẤN KÍNH MẮT v2.0")
    print("=" * 60)
    print(f"  Web:          http://localhost:{Config.PORT}")
    print(f"  Chat API:     POST http://localhost:{Config.PORT}/api/chat")
    print(f"  Feedback:     GET  http://localhost:{Config.PORT}/api/feedback/list")
    print(f"  Thêm Q&A:     POST http://localhost:{Config.PORT}/api/feedback/add-qa")
    print(f"  Retrain:      POST http://localhost:{Config.PORT}/api/retrain")
    print(f"  Health:       GET  http://localhost:{Config.PORT}/api/health")
    print("=" * 60)
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)