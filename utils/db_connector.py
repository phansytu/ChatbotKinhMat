"""
=============================================================
DATABASE CONNECTOR - Khớp đúng bảng products thực tế
=============================================================
Bảng: products
  id, name, description, price, sale_price, stock,
  sold_quantity, total_reviews, average_rating,
  category_id, image, created_at, brand, gender,
  frame_material, lens_type, uv_protection,
  is_featured, status
=============================================================
"""

import mysql.connector
from mysql.connector import pooling, Error
import logging
import re
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)


class DatabaseConnector:

    def __init__(self):
        self._pool = None
        self._init_pool()

    # ─── Kết nối ──────────────────────────────────────────

    def _init_pool(self):
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="kinh_mat_pool",
                pool_size=Config.DB_POOL_SIZE,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                charset=Config.DB_CHARSET,
                use_unicode=True,
                connect_timeout=Config.DB_CONNECT_TIMEOUT,
                autocommit=True
            )
            logger.info(f"✅ MySQL pool: {Config.DB_HOST}/{Config.DB_NAME}")
        except Error as e:
            logger.error(f"❌ MySQL: {e}")
            self._pool = None

    def test_connection(self) -> bool:
        try:
            conn = self._get_connection()
            if conn:
                conn.close()
                return True
        except Exception:
            pass
        return False

    def _get_connection(self):
        if not self._pool:
            return None
        try:
            return self._pool.get_connection()
        except Error as e:
            logger.error(f"Get conn error: {e}")
            return None

    # =========================================================
    #  TÌM SẢN PHẨM THEO TÊN (quan trọng nhất)
    # =========================================================

    def find_by_name(self, name_query: str, limit: int = 3) -> List[Dict]:
        """
        Tìm sản phẩm theo tên — FUZZY match.
        Trả về cả description để chatbot dùng tư vấn.
        """
        conn = self._get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            # Tách từ khóa rồi tìm từng từ
            words = [w.strip() for w in name_query.split() if len(w.strip()) > 1]
            if not words:
                return []

            # Tìm bằng LIKE cho từng từ (OR) để bắt được tên gần đúng
            like_conds = " OR ".join(["name LIKE %s"] * len(words))
            params = [f"%{w}%" for w in words]
            params.append(limit)

            cursor.execute(f"""
                SELECT
                    id, name, description, price, sale_price,
                    stock, sold_quantity, total_reviews, average_rating,
                    brand, gender, frame_material, lens_type,
                    uv_protection, is_featured, image,
                    COALESCE(sale_price, price) AS effective_price,
                    CASE
                        WHEN sale_price IS NOT NULL AND sale_price < price
                        THEN ROUND((1 - sale_price/price)*100)
                        ELSE 0
                    END AS discount_pct
                FROM products
                WHERE status = 'active'
                  AND ({like_conds})
                ORDER BY
                    CASE WHEN name LIKE %s THEN 0 ELSE 1 END,
                    is_featured DESC,
                    average_rating DESC
                LIMIT %s
            """, params + [f"%{name_query}%"] + [limit])

            return [self._serialize(r) for r in cursor.fetchall()]
        except Error as e:
            logger.error(f"find_by_name error: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_product_detail(self, product_id: int) -> Optional[Dict]:
        """Lấy chi tiết 1 sản phẩm theo ID — bao gồm description đầy đủ"""
        conn = self._get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    id, name, description, price, sale_price,
                    stock, sold_quantity, total_reviews, average_rating,
                    brand, gender, frame_material, lens_type,
                    uv_protection, is_featured, image, created_at,
                    COALESCE(sale_price, price) AS effective_price,
                    CASE WHEN sale_price IS NOT NULL AND sale_price < price
                         THEN ROUND((1 - sale_price/price)*100) ELSE 0
                    END AS discount_pct
                FROM products
                WHERE id = %s AND status = 'active'
            """, (product_id,))
            row = cursor.fetchone()
            return self._serialize(row) if row else None
        except Error as e:
            logger.error(f"get_detail error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    # =========================================================
    #  TÌM KIẾM ĐA TIÊU CHÍ
    # =========================================================

    def search_products(self, filters: Dict) -> List[Dict]:
        """
        Tìm sản phẩm theo nhiều tiêu chí kết hợp.

        filters:
            keyword      : từ khóa tự do (tìm trong name + description)
            brand        : thương hiệu
            gender       : male | female | unisex
            frame_material: chất liệu gọng
            lens_type    : loại tròng
            min_price    : giá tối thiểu
            max_price    : giá tối đa
            uv_protection: True/False
            is_featured  : True/False
            sort         : price_asc | price_desc | rating | popular | discount
            limit        : số kết quả
        """
        conn = self._get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            conds = ["status = 'active'", "stock > 0"]
            params = []

            # Từ khóa (tìm trong name + description)
            kw = (filters.get('keyword') or '').strip()
            if kw:
                conds.append("(name LIKE %s OR description LIKE %s OR brand LIKE %s)")
                params.extend([f'%{kw}%', f'%{kw}%', f'%{kw}%'])

            # Thương hiệu
            brand = (filters.get('brand') or '').strip()
            if brand:
                conds.append("brand LIKE %s")
                params.append(f'%{brand}%')

            # Giới tính
            gender = self._normalize_gender(filters.get('gender', ''))
            if gender in ('male', 'female'):
                conds.append("(gender = %s OR gender = 'unisex')")
                params.append(gender)
            elif gender == 'unisex':
                conds.append("gender = 'unisex'")

            # Chất liệu gọng
            material = (filters.get('frame_material') or '').strip()
            if material:
                conds.append("frame_material LIKE %s")
                params.append(f'%{material}%')

            # Loại tròng
            lens = (filters.get('lens_type') or '').strip()
            if lens:
                conds.append("lens_type LIKE %s")
                params.append(f'%{lens}%')

            # Khoảng giá
            min_p = filters.get('min_price')
            max_p = filters.get('max_price')
            if min_p is not None:
                conds.append("COALESCE(sale_price, price) >= %s")
                params.append(float(min_p))
            if max_p is not None:
                conds.append("COALESCE(sale_price, price) <= %s")
                params.append(float(max_p))

            # UV
            if filters.get('uv_protection') is True:
                conds.append("uv_protection = 1")

            # Nổi bật
            if filters.get('is_featured') is True:
                conds.append("is_featured = 1")

            # Chỉ có giảm giá
            if filters.get('has_discount'):
                conds.append("sale_price IS NOT NULL AND sale_price < price")

            where = " AND ".join(conds)
            sort_map = {
                'price_asc':  "COALESCE(sale_price,price) ASC",
                'price_desc': "COALESCE(sale_price,price) DESC",
                'rating':     "average_rating DESC, total_reviews DESC",
                'popular':    "sold_quantity DESC",
                'discount':   "CASE WHEN sale_price IS NOT NULL AND sale_price<price THEN ROUND((1-sale_price/price)*100) ELSE 0 END DESC",
            }
            order = sort_map.get(filters.get('sort', ''), "is_featured DESC, average_rating DESC")
            limit = min(int(filters.get('limit', 5)), 20)

            cursor.execute(f"""
                SELECT
                    id, name, description, price, sale_price,
                    stock, sold_quantity, total_reviews, average_rating,
                    brand, gender, frame_material, lens_type,
                    uv_protection, is_featured, image,
                    COALESCE(sale_price, price) AS effective_price,
                    CASE WHEN sale_price IS NOT NULL AND sale_price < price
                         THEN ROUND((1 - sale_price/price)*100) ELSE 0
                    END AS discount_pct
                FROM products
                WHERE {where}
                ORDER BY {order}
                LIMIT {limit}
            """, params)

            return [self._serialize(r) for r in cursor.fetchall()]
        except Error as e:
            logger.error(f"search_products error: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    # ─── Các query chuyên biệt ─────────────────────────────

    def get_featured_products(self, limit: int = 4) -> List[Dict]:
        return self.search_products({'is_featured': True, 'sort': 'rating', 'limit': limit})

    def get_by_price_range(self, min_p: float, max_p: float, limit: int = 6) -> List[Dict]:
        return self.search_products({'min_price': min_p, 'max_price': max_p,
                                     'sort': 'price_asc', 'limit': limit})

    def get_by_gender(self, gender: str, limit: int = 5) -> List[Dict]:
        return self.search_products({'gender': gender, 'sort': 'rating', 'limit': limit})

    def get_by_material(self, material: str, limit: int = 5) -> List[Dict]:
        return self.search_products({'frame_material': material, 'limit': limit})

    def get_discounted(self, limit: int = 5) -> List[Dict]:
        return self.search_products({'has_discount': True, 'sort': 'discount', 'limit': limit})

    def get_top_rated(self, limit: int = 5) -> List[Dict]:
        return self.search_products({'sort': 'rating', 'limit': limit})

    def get_all_brands(self) -> List[str]:
        conn = self._get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT brand FROM products WHERE status='active' AND brand IS NOT NULL ORDER BY brand")
            return [r[0] for r in cursor.fetchall()]
        except Error:
            return []
        finally:
            cursor.close()
            conn.close()

    def get_statistics(self) -> Dict:
        conn = self._get_connection()
        if not conn:
            return {}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    MIN(COALESCE(sale_price,price)) AS min_price,
                    MAX(COALESCE(sale_price,price)) AS max_price,
                    AVG(average_rating) AS avg_rating,
                    SUM(CASE WHEN sale_price IS NOT NULL AND sale_price<price THEN 1 ELSE 0 END) AS discounted,
                    SUM(CASE WHEN is_featured=1 THEN 1 ELSE 0 END) AS featured
                FROM products WHERE status='active' AND stock>0
            """)
            return self._serialize(cursor.fetchone() or {})
        except Error as e:
            logger.error(f"stats error: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()

    # ─── Helpers ──────────────────────────────────────────

    @staticmethod
    def _normalize_gender(raw: str) -> str:
        raw = (raw or '').strip().lower()
        m = {'nam': 'male', 'con trai': 'male', 'ban trai': 'male', 'male': 'male',
             'nu': 'female', 'con gai': 'female', 'ban gai': 'female', 'female': 'female',
             'unisex': 'unisex'}
        return m.get(raw, raw)

    @staticmethod
    def _serialize(row: Dict) -> Dict:
        if not row:
            return {}
        out = {}
        for k, v in row.items():
            if hasattr(v, '__float__'):
                out[k] = float(v)
            elif hasattr(v, 'isoformat'):
                out[k] = v.isoformat()
            else:
                out[k] = v
        return out