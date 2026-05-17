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
        # ─── Templates cho câu hỏi phân loại ───────────────────
    
    TYPE_QUERY_INTRO = [
        "📚 **Phân loại {category}:**\n{content}",
        "🕶️ **Các loại {category} phổ biến:**\n{content}",
        "✨ **{category} được chia thành các nhóm sau:**\n{content}",
        "📖 **Chi tiết phân loại {category}:**\n{content}",
    ]
    
    TYPE_QUERY_FOLLOWUP = [
        "\n\n💡 Bạn muốn tìm hiểu thêm về loại nào không ạ?",
        "\n\n🔍 Nếu cần tư vấn chọn loại phù hợp, hãy cho shop biết thêm nhé!",
        "\n\n❓ Bạn đang phân vân giữa các loại nào? Shop sẵn sàng tư vấn thêm!",
        "\n\n📌 Bạn muốn xem sản phẩm cụ thể của loại nào không?",
    ]
    
    CATEGORY_NOT_FOUND = [
        "Shop chưa có thông tin phân loại về **{category}** bạn ơi 😅",
        "Hiện tại shop chưa cập nhật chi tiết các loại **{category}** ạ.",
        "Rất tiếc, shop chưa có dữ liệu phân loại cho **{category}** bạn hỏi 🙏",
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
                             extra_context: str = "",
                             is_type_query: bool = False) -> str:
        """
        Tạo câu trả lời tư vấn cho một sản phẩm cụ thể.

         Args:
            product          : dict từ DB
            knowledge_snippet: đoạn kiến thức liên quan
            extra_context    : ngữ cảnh thêm
            is_type_query    : có phải câu hỏi phân loại không  # THÊM
        """
        # Nếu là type query và có knowledge, ưu tiên format type
        if is_type_query and knowledge_snippet and len(knowledge_snippet) > 200:
            category = product.get('name', 'kính')
            return self.build_type_query_reply(category, knowledge_snippet)
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
        # =========================================================
    #  XỬ LÝ CÂU HỎI PHÂN LOẠI SẢN PHẨM
    # =========================================================
    
    def build_type_query_reply(self, category: str, knowledge_content: str) -> str:
        """
        Tạo câu trả lời cho câu hỏi phân loại sản phẩm
        
        Args:
            category: Tên danh mục sản phẩm (kính râm, kính cận, etc.)
            knowledge_content: Nội dung phân loại từ knowledge base
        
        Returns:
            Câu trả lời hoàn chỉnh
        """
        import random
        
        if not knowledge_content:
            return self._pick(self.CATEGORY_NOT_FOUND, category=category)
        
        # Chọn template intro
        intro = self._pick(self.TYPE_QUERY_INTRO, category=category, content=knowledge_content)
        
        # Thêm câu hỏi gợi ý
        followup = random.choice(self.TYPE_QUERY_FOLLOWUP)
        
        return intro + followup
    
    def build_type_query_with_products(self, category: str, 
                                        knowledge_content: str,
                                        products: List[Dict]) -> str:
        """
        Kết hợp phân loại + gợi ý sản phẩm cụ thể
        
        Args:
            category: Tên danh mục
            knowledge_content: Nội dung phân loại
            products: Danh sách sản phẩm gợi ý
        """
        # Phần phân loại
        reply = self.build_type_query_reply(category, knowledge_content)
        
        # Thêm sản phẩm gợi ý nếu có
        if products and len(products) > 0:
            reply += "\n\n🛍️ **Một số sản phẩm tiêu biểu:**\n"
            for i, p in enumerate(products[:3], 1):
                name = p.get('name', '')
                price = p.get('effective_price') or p.get('price', 0)
                reply += f"{i}. **{name}** - {self._fmt(price)}\n"
            reply += "\nBạn có muốn xem chi tiết sản phẩm nào không ạ?"
        
        return reply
    
    def extract_type_info(self, knowledge_content: str, max_length: int = 2000) -> Dict:
        """
        Trích xuất thông tin phân loại từ knowledge content
        Trả về dict với các phần: main_types, sub_types, recommendations
        """
        if not knowledge_content:
            return {'main_types': [], 'sub_types': {}, 'recommendations': []}
        
        result = {
            'main_types': [],
            'sub_types': {},
            'recommendations': []
        }
        
        # Tìm các mục phân loại chính (có dấu ** hoặc số thứ tự)
        lines = knowledge_content.split('\n')
        current_main = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Phát hiện mục chính (có **, hoặc số, hoặc chữ in hoa đầu dòng)
            if line.startswith('**') or re.match(r'^\d+\.', line) or line.isupper():
                # Làm sạch tên mục
                main_name = re.sub(r'[**\d\.\s]+', '', line).strip()
                if main_name and len(main_name) < 50:
                    result['main_types'].append(main_name)
                    current_main = main_name
                    result['sub_types'][main_name] = []
            
            # Phát hiện mục con (có dấu - hoặc •)
            elif line.startswith('-') or line.startswith('•') or line.startswith('+'):
                sub_item = line.lstrip('-•+ ').strip()
                if current_main and sub_item:
                    result['sub_types'][current_main].append(sub_item)
            
            # Phát hiện gợi ý (chứa "gợi ý", "nên chọn", "phù hợp")
            elif any(keyword in line.lower() for keyword in ['gợi ý', 'nên chọn', 'phù hợp', 'theo nhu cầu']):
                result['recommendations'].append(line)
        
        return result
    
    def format_type_info_table(self, type_info: Dict) -> str:
        """
        Format thông tin phân loại thành bảng đẹp
        """
        if not type_info['main_types']:
            return ""
        
        lines = []
        
        for main_type in type_info['main_types']:
            lines.append(f"**{main_type}**")
            sub_items = type_info['sub_types'].get(main_type, [])
            for item in sub_items[:5]:  # Giới hạn 5 mục con
                lines.append(f"  • {item}")
            lines.append("")
        
        if type_info['recommendations']:
            lines.append("📌 **Gợi ý theo nhu cầu:**")
            for rec in type_info['recommendations'][:3]:
                lines.append(f"  ✨ {rec[:100]}")
        
        return "\n".join(lines)
        # =========================================================
    #  TƯ VẤN THEO NGỮ CẢNH NÂNG CAO
    # =========================================================
    
    def build_contextual_reply(self, intent: str, 
                                entities: Dict,
                                products: List[Dict],
                                knowledge: str) -> str:
        """
        Xây dựng câu trả lời theo intent và entities
        """
        if intent == 'ask_types':
            category = entities.get('product_category', 'kính')
            return self.build_type_query_reply(category, knowledge)
        
        elif intent == 'consult_face':
            face_shape = entities.get('face_shape', '')
            if face_shape and knowledge:
                return self.build_face_advice(face_shape, knowledge, products)
        
        elif intent == 'search_by_price':
            return self.build_price_recommendation(entities, products, knowledge)
        
        elif intent == 'ask_compare':
            return self.build_comparison_reply(products, knowledge)
        
        else:
            # Fallback: trả về product reply bình thường
            if products:
                return self.build_multi_product_reply(products, knowledge)
            return knowledge or "Shop chưa có thông tin cho câu hỏi này bạn ơi 😅"
    
    def build_face_advice(self, face_shape: str, knowledge: str, products: List[Dict]) -> str:
        """Tư vấn theo khuôn mặt"""
        shape_names = {
            'tròn': 'mặt tròn',
            'vuông': 'mặt vuông',
            'dài': 'mặt dài',
            'trái xoan': 'mặt trái xoan',
            'tim': 'mặt trái tim'
        }
        shape_display = shape_names.get(face_shape, face_shape)
        
        reply = f"🫢 **Tư vấn cho {shape_display}:**\n{knowledge}\n\n"
        
        if products:
            reply += "🛒 **Mẫu kính phù hợp:**\n"
            for p in products[:2]:
                name = p.get('name', '')
                price = self._fmt(p.get('effective_price') or p.get('price', 0))
                reply += f"  • {name} - {price}\n"
        
        return reply
    
    def build_price_recommendation(self, entities: Dict, products: List[Dict], knowledge: str) -> str:
        """Tư vấn theo giá"""
        min_price = entities.get('price_min', 0)
        max_price = entities.get('price_max', 0)
        
        if min_price and max_price:
            price_range = f"{self._fmt(min_price)} - {self._fmt(max_price)}"
        elif min_price:
            price_range = f"từ {self._fmt(min_price)}"
        elif max_price:
            price_range = f"dưới {self._fmt(max_price)}"
        else:
            price_range = "tầm giá bạn mong muốn"
        
        reply = f"💰 **Sản phẩm trong {price_range}:**\n"
        
        if products:
            for p in products[:3]:
                name = p.get('name', '')
                price = self._fmt(p.get('effective_price') or p.get('price', 0))
                reply += f"  • {name} - {price}\n"
        else:
            reply += "  • Chưa có sản phẩm phù hợp trong tầm giá này bạn ơi 😅\n"
        
        if knowledge:
            reply += f"\n💡 **Gợi ý thêm:**\n{knowledge[:300]}"
        
        return reply
    
    def build_comparison_reply(self, products: List[Dict], knowledge: str) -> str:
        """So sánh sản phẩm"""
        if not products or len(products) < 2:
            return "Shop cần ít nhất 2 sản phẩm để so sánh bạn ơi 😅"
        
        reply = "📊 **So sánh sản phẩm:**\n\n"
        
        # Tạo bảng so sánh đơn giản
        reply += "| Sản phẩm | Thương hiệu | Chất liệu | Giá |\n"
        reply += "|----------|-------------|-----------|-----|\n"
        
        for p in products[:3]:
            name = p.get('name', 'N/A')[:20]
            brand = p.get('brand', 'N/A')
            material = p.get('frame_material', 'N/A')
            price = self._fmt(p.get('effective_price') or p.get('price', 0))
            reply += f"| {name} | {brand} | {material} | {price} |\n"
        
        if knowledge:
            reply += f"\n💡 **Lưu ý khi chọn:**\n{knowledge[:200]}"
        
        return reply