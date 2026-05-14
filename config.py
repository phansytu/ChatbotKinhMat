"""
=============================================================
CONFIG v2 - Cấu hình hệ thống Chatbot Kính Mắt
=============================================================
"""
import os


class Config:
    # ─── Flask ────────────────────────────────────────────
    HOST       = '0.0.0.0'
    PORT       = 5000
    DEBUG      = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'kinh-mat-chatbot-2024')

    # ─── MySQL ────────────────────────────────────────────
    # ⚠️  Sửa DB_PASSWORD theo MySQL Workbench của bạn
    DB_HOST            = os.environ.get('DB_HOST',     'localhost')
    DB_PORT            = int(os.environ.get('DB_PORT',  3306))
    DB_USER            = os.environ.get('DB_USER',     'root')
    DB_PASSWORD        = os.environ.get('DB_PASSWORD', '240805')
    DB_NAME            = os.environ.get('DB_NAME',     'eyewear_shop')
    DB_CHARSET         = 'utf8mb4'
    DB_POOL_SIZE       = 5
    DB_CONNECT_TIMEOUT = 10

    # ─── Files ────────────────────────────────────────────
    KNOWLEDGE_FILE  = os.path.join('data', 'knowledge.txt')
    UNRESOLVED_FILE = os.path.join('data', 'unresolved.txt')
    RESOLVED_FILE   = os.path.join('data', 'resolved.txt')

    # ─── Chatbot ──────────────────────────────────────────
    SIMILARITY_THRESHOLD    = 0.30   # ngưỡng chấp nhận kết quả knowledge
    AUTO_SAVE_THRESHOLD     = 0.20   # tự động lưu unresolved khi confidence thấp
    MAX_PRODUCTS_RETURN     = 5      # số SP tối đa trả về
    TOP_K_ANSWERS           = 3
    MAX_HISTORY_PER_SESSION = 10