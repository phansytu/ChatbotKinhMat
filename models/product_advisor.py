"""
=============================================================
PRODUCT ADVISOR - Tư vấn sản phẩm kết hợp DB + Knowledge
=============================================================
Khi khách hỏi về một sản phẩm cụ thể:
  1. Tìm sản phẩm trong DB (lấy description)
  2. Tìm kiến thức liên quan trong knowledge.txt
  3. Kết hợp thành câu trả lời tư vấn tự nhiên
=============================================================
"""

import logging
import re
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ProductAdvisor:
    """
    Tạo câu trả lời tư vấn sản phẩm kết hợp:
      - Dữ liệu thực tế từ DB (description, giá, chất liệu...)
      - Kiến thức chung từ knowledge.txt (phong cách, khuôn mặt...)
    """

    # ─── Templates trả lời sản phẩm ──────────────────────

    PRODUCT_INTRO = [
        "Dạ shop tìm thấy sản phẩm **{name}** cho bạn!",
        "Bạn đang hỏi về **{name}** đúng không? Để shop giới thiệu nhé!",
        "Shop có **{name}** bạn ơi! Đây là thông tin chi tiết:",
        "Mình biết sản phẩm **{name}** rồi! Shop tư vấn cho bạn nè:",
    ]

    MULTI_RESULT = [
        "Shop tìm được {count} sản phẩm phù hợp, bạn xem qua nhé:",
        "Có {count} mẫu hợp với yêu cầu của bạn:",
        "Dựa theo bạn mô tả, shop gợi ý {count} sản phẩm sau:",
    ]

    NOT_FOUND = [
        "Dạ shop chưa tìm thấy sản phẩm **{name}** trong kho bạn ơi 😅 Bạn có thể mô tả thêm hoặc hỏi về loại kính khác không?",
        "Hmm, shop chưa có thông tin về **{name}** bạn ơi. Bạn thử hỏi theo phong cách hoặc giá tiền để shop gợi ý nhé!",
        "Shop chưa tìm thấy **{name}** ạ. Bạn có thể cho shop biết thêm chi tiết (màu sắc, chất liệu, giá mong muốn) không?",
    ]

    import random as _r

    @classmethod
    def _pick(cls, lst, **kwargs):
        import random
        t = random.choice(lst)
        return t.format(**kwargs) if kwargs else t

    # ─── Build tư vấn cho 1 sản phẩm ────────────────────

    def build_product_reply(self,
                             product: Dict,
                             knowledge_snippet: str = "",
                             extra_context: str = "") -> str:
        """
        Tạo câu trả lời tư vấn cho một sản phẩm cụ thể.

        Args:
            product          : dict từ DB (có description, price, brand...)
            knowledge_snippet: đoạn kiến thức liên quan từ knowledge.txt
            extra_context    : ngữ cảnh thêm (khuôn mặt, phong cách...)

        Returns:
            str câu trả lời hoàn chỉnh
        """
        name = product.get('name', 'sản phẩm này')
        desc = (product.get('description') or '').strip()
        price = product.get('effective_price') or product.get('price', 0)
        sale  = product.get('sale_price')
        orig  = product.get('price', 0)
        disc  = product.get('discount_pct', 0)
        brand = product.get('brand', '')
        material = product.get('frame_material', '')
        lens_type = product.get('lens_type', '')
        gender = product.get('gender', '')
        rating = product.get('average_rating')
        reviews = product.get('total_reviews', 0)
        sold = product.get('sold_quantity', 0)
        stock = product.get('stock', 0)
        uv = product.get('uv_protection', 0)

        parts = []

        # ── Mở đầu ──
        parts.append(self._pick(self.PRODUCT_INTRO, name=name))
        parts.append("")

        # ── Mô tả từ DB ──
        if desc:
            parts.append(f"📝 **Mô tả:** {desc}")
            parts.append("")

        # ── Thông tin kỹ thuật ──
        info_lines = []
        if brand:
            info_lines.append(f"🏷️ Thương hiệu: **{brand}**")
        if material:
            info_lines.append(f"🔧 Chất liệu gọng: **{material}**")
        if lens_type:
            info_lines.append(f"🔍 Loại tròng: **{lens_type}**")
        if uv:
            info_lines.append("☀️ Chống UV: **Có (UV400)**")
        gender_map = {'male': 'Nam', 'female': 'Nữ', 'unisex': 'Nam/Nữ đều dùng được'}
        if gender:
            info_lines.append(f"👤 Dành cho: **{gender_map.get(gender, gender)}**")

        if info_lines:
            parts.extend(info_lines)
            parts.append("")

        # ── Giá ──
        if disc and disc > 0:
            parts.append(f"💰 **Giá:** {self._fmt(price)} ~~{self._fmt(orig)}~~ (-{disc:.0f}% giảm)")
        else:
            parts.append(f"💰 **Giá:** {self._fmt(price)}")

        # ── Đánh giá ──
        if rating and reviews > 0:
            stars = "⭐" * int(rating)
            parts.append(f"{stars} Đánh giá: **{rating}/5** ({reviews} đánh giá, {sold} đã bán)")

        # ── Tồn kho ──
        if stock <= 3:
            parts.append(f"⚠️ Chỉ còn **{stock} sản phẩm** — mua ngay kẻo hết bạn ơi!")
        elif stock <= 10:
            parts.append(f"📦 Còn hàng ({stock} cái)")
        else:
            parts.append("✅ Còn hàng sẵn")

        parts.append("")

        # ── Kiến thức tư vấn từ knowledge.txt ──
        if knowledge_snippet:
            parts.append("💡 **Tư vấn thêm từ shop:**")
            parts.append(knowledge_snippet.strip())
            parts.append("")

        # ── Ngữ cảnh thêm (khuôn mặt, phong cách...) ──
        if extra_context:
            parts.append(extra_context.strip())
            parts.append("")

        # ── Chốt sale ──
        parts.append(self._closing_line(disc, stock))

        return "\n".join(parts)

    def build_multi_product_reply(self, products: List[Dict],
                                   knowledge_snippet: str = "") -> str:
        """
        Trả lời khi tìm được nhiều sản phẩm.
        Hiển thị tóm tắt từng sản phẩm, không chi tiết từng cái.
        """
        count = len(products)
        intro = self._pick(self.MULTI_RESULT, count=count)
        parts = [intro, ""]

        for i, p in enumerate(products, 1):
            name  = p.get('name', '')
            price = p.get('effective_price') or p.get('price', 0)
            disc  = p.get('discount_pct', 0)
            orig  = p.get('price', 0)
            mat   = p.get('frame_material', '')
            brand = p.get('brand', '')
            rating= p.get('average_rating')
            stock = p.get('stock', 0)

            line = f"**{i}. {name}**"
            if brand:
                line += f" ({brand})"
            parts.append(line)

            price_str = self._fmt(price)
            if disc and disc > 0:
                price_str += f" ~~{self._fmt(orig)}~~ 🔥-{disc:.0f}%"
            parts.append(f"   💰 {price_str}")

            if mat:
                parts.append(f"   🔧 {mat}")
            if rating:
                parts.append(f"   ⭐ {rating}/5")
            if stock <= 3:
                parts.append(f"   ⚠️ Còn {stock} cái")
            parts.append("")

        if knowledge_snippet:
            parts.append("💡 " + knowledge_snippet.strip())
            parts.append("")

        parts.append("Bạn muốn xem chi tiết sản phẩm nào, cho shop biết nhé! 😊")
        return "\n".join(parts)

    def build_not_found_reply(self, name_query: str) -> str:
        return self._pick(self.NOT_FOUND, name=name_query)

    # ─── Format tiền tệ ───────────────────────────────────

    @staticmethod
    def _fmt(n) -> str:
        try:
            return f"{float(n):,.0f}₫"
        except Exception:
            return str(n)

    @staticmethod
    def _closing_line(discount: float, stock: int) -> str:
        import random
        if discount and discount >= 20:
            opts = [
                "Sản phẩm đang giảm giá tốt lắm, bạn đặt hàng sớm kẻo hết nhé! 🛒",
                "Đang sale lớn đó bạn, không mua tiếc lắm! Bạn muốn đặt hàng không? 😄",
            ]
        elif stock and stock <= 5:
            opts = [
                "Hàng sắp hết rồi bạn ơi, mình đặt nhanh nhé! ⚡",
                "Chỉ còn ít hàng thôi, bạn có muốn mình giữ cho không? 😊",
            ]
        else:
            opts = [
                "Bạn có muốn đặt hàng hoặc cần tư vấn thêm gì không ạ? 😊",
                "Shop sẵn sàng hỗ trợ bạn thêm nếu cần nhé! 🙌",
                "Bạn thích sản phẩm này không? Cho shop biết để tư vấn thêm nha!",
            ]
        return random.choice(opts)