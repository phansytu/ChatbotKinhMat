"""
=============================================================
INTENT CLASSIFIER - Fixed v2
=============================================================
Fix:
  1. Không nhận nhầm "mặt tròn", "chống ánh sáng xanh" là tên SP
  2. Tách biệt rõ intent consult_face / ask_feature / ask_product
  3. Chỉ extract product_name khi thực sự có tên SP cụ thể
=============================================================
"""

import re
from typing import Dict, List, Tuple, Optional


# ── INTENTS ─────────────────────────────────────────────────

INTENTS = {
    'ask_product':        ['thông tin', 'giới thiệu', 'mô tả', 'chi tiết', 'specs',
                           'đặc điểm', 'như thế nào', 'ra sao', 'có gì đặc biệt'],
    'search_product':     ['tìm', 'kiếm', 'có bán', 'gợi ý', 'đề xuất', 'liệt kê',
                           'danh sách', 'show', 'cho xem'],
    'search_by_price':    ['giá', 'bao nhiêu tiền', 'rẻ nhất', 'đắt nhất',
                           'tầm giá', 'khoảng giá', 'dưới', 'trên', 'budget', 'chi phí'],
    'search_by_gender':   ['cho nam', 'cho nữ', 'của nam', 'của nữ'],
    'search_by_material': ['kim loại', 'nhựa acetate', 'titan', 'tr90', 'inox',
                           'chất liệu gọng', 'gọng kim loại', 'gọng nhựa'],
    'search_by_style':    ['phong cách', 'vintage', 'hàn quốc', 'công sở',
                           'cá tính', 'retro', 'thời trang', 'classic', 'streetwear'],
    'consult_face':       ['mặt tròn', 'mặt vuông', 'mặt dài', 'mặt trái xoan',
                           'mặt tim', 'khuôn mặt', 'hợp mặt', 'phù hợp mặt', 'hình mặt'],
    'ask_blue_light':     ['chống ánh sáng xanh', 'blue light', 'anti blue',
                           'chống sáng xanh', 'bảo vệ mắt màn hình'],
    'ask_uv':             ['chống uv', 'uv400', 'tia cực tím', 'chống nắng uv'],
    'ask_photochromic':   ['đổi màu', 'photochromic', 'transition'],
    'ask_shipping':       ['ship', 'giao hàng', 'vận chuyển', 'giao bao lâu',
                           'phí ship', 'mấy ngày nhận'],
    'ask_warranty':       ['bảo hành', 'đổi trả', 'hoàn tiền', 'trả hàng', 'hỏng'],
    'ask_payment':        ['thanh toán', 'chuyển khoản', 'cod', 'momo', 'zalopay'],
    'ask_discount':       ['giảm giá', 'khuyến mãi', 'sale', 'ưu đãi', 'combo', 'mã giảm'],
    'ask_compare':        ['so sánh', 'khác nhau', 'tốt hơn', 'nên chọn cái nào'],
    'feedback_negative':  ['sai rồi', 'không đúng', 'chưa đúng', 'không phải vậy',
                           'hiểu nhầm', 'trả lời nhầm', 'không đúng ý', 'không giống'],
    'buy_intent':         ['muốn mua', 'đặt hàng', 'order', 'chốt đơn', 'cho mình lấy'],
    'greeting':           ['xin chào', 'hello', 'hi ', 'chào ', 'hey', 'alo', 'cho hỏi'],
    'thanks':             ['cảm ơn', 'thank', 'cám ơn', 'ok rồi', 'hiểu rồi', 'vậy thôi'],
    'goodbye':            ['tạm biệt', 'bye', 'thôi nhé', 'gặp lại'],
    'urgent':             ['gấp lắm', 'cần gấp', 'nhanh nhất', 'hôm nay cần'],
}

# Từ/cụm từ KHÔNG phải tên sản phẩm
NOT_PRODUCT_NAME = {
    # Intent keywords
    'mặt tròn', 'mặt vuông', 'mặt dài', 'mặt trái xoan', 'mặt tim',
    'cho mặt tròn', 'cho mặt vuông', 'cho mặt dài',
    'chống ánh sáng xanh', 'blue light', 'chống uv', 'uv400',
    'phong cách', 'vintage', 'hàn quốc', 'công sở', 'cá tính',
    # Giá
    'giá rẻ', 'giá tốt', 'giá thấp', 'giá cao', 'giá bao nhiêu',
    # Chung
    'kính', 'gọng', 'mắt kính', 'loại nào', 'cái nào', 'loại kính',
    'sản phẩm', 'hàng', 'mẫu', 'nào', 'gì', 'đó',
    'rẻ', 'đẹp', 'tốt', 'bền', 'nhẹ', 'phù hợp',
    'cho tôi', 'cho mình', 'cho em', 'giúp tôi',
    'kinh', 'gong', 'mat kinh',
}

# Thương hiệu đã biết — ưu tiên tìm tên SP khi có
KNOWN_BRANDS = {
    'rayban', 'ray-ban', 'ray ban', 'oakley', 'gucci', 'prada', 'dior',
    'versace', 'polaroid', 'zeiss', 'essilor', 'hoya', 'nikon',
    'titanpro', 'italyframe', 'provison', 'koreanreye', 'aviatorx',
    'retrolens', 'softcircle', 'geostyle', 'urbanstyle', 'bostonline',
}


class IntentClassifier:

    def classify(self, message: str) -> Dict:
        norm = self._normalize(message)

        matched   = self._match_intents(norm)
        primary   = matched[0][0] if matched else 'unknown'
        conf      = matched[0][1] if matched else 0.0
        sub       = [i for i, _ in matched[1:4]]

        entities  = self._extract_entities(message, norm, primary)

        # Điều chỉnh intent dựa trên entities
        if entities.get('product_name') and \
                primary not in ('feedback_negative','greeting','thanks',
                                'goodbye','consult_face','ask_blue_light',
                                'ask_uv','ask_photochromic'):
            if primary not in ('ask_product','buy_intent','ask_compare','search_by_price'):
                primary = 'ask_product'
                conf    = max(conf, 0.7)

        return {
            'intent':              primary,
            'sub_intents':         sub,
            'entities':            entities,
            'confidence':          conf,
            'is_question':         '?' in message or any(
                                       w in norm for w in
                                       ['không', 'bao nhiêu', 'như thế nào',
                                        'nào', 'gì', 'có không', 'sao']),
            'is_negative_feedback': primary == 'feedback_negative',
            'normalized':           norm,
        }

    # ── Intent matching ─────────────────────────────────────

    def _match_intents(self, msg: str) -> List[Tuple[str, float]]:
        matched = []
        for intent, kws in INTENTS.items():
            hits = [kw for kw in kws if kw in msg]
            if hits:
                # Score: tổng độ dài keyword hits / tổng số keyword
                score = sum(len(h.split()) for h in hits)
                conf  = min(0.95, score / max(len(kws) * 0.25, 1))
                if len(hits) >= 2:
                    conf = min(0.95, conf * 1.3)
                matched.append((intent, conf))
        matched.sort(key=lambda x: x[1], reverse=True)
        return matched

    # ── Entity extraction ────────────────────────────────────

    def _extract_entities(self, raw: str, norm: str, intent: str) -> Dict:
        ent = {}

        # Tên sản phẩm — CHỈ extract khi intent không phải là tư vấn chung
        if intent not in ('consult_face','ask_blue_light','ask_uv',
                          'ask_photochromic','ask_shipping','ask_warranty',
                          'ask_payment','greeting','thanks','goodbye',
                          'search_by_style','search_by_material'):
            pn = self._extract_product_name(raw, norm)
            if pn:
                ent['product_name'] = pn

        # Khoảng giá
        ent.update(self._extract_price(norm))

        # Giới tính
        g = self._extract_gender(norm)
        if g:
            ent['gender'] = g

        # Khuôn mặt
        f = self._extract_face(norm)
        if f:
            ent['face_shape'] = f

        # Chất liệu
        for m in ['titan', 'titanium', 'acetate', 'tr90', 'inox', 'kim loại', 'nhựa']:
            if m in norm:
                ent['material'] = m
                break

        # Phong cách
        for s in ['vintage', 'hàn quốc', 'công sở', 'thể thao', 'cá tính', 'retro']:
            if s in norm:
                ent['style'] = s
                break

        return ent

    def _extract_product_name(self, raw: str, norm: str) -> Optional[str]:
        """
        Chỉ extract tên SP khi:
          - Có thương hiệu đã biết (RayBan, Zeiss...)
          - Hoặc câu có pattern "kính/gọng [TÊN_CỤ_THỂ]" dài hơn 5 ký tự
          - Và tên đó KHÔNG nằm trong danh sách NOT_PRODUCT_NAME
        """
        # 1. Tên thương hiệu đã biết trong raw
        raw_lower = raw.lower()
        for brand in KNOWN_BRANDS:
            if brand in raw_lower:
                # Lấy cụm từ xung quanh brand
                idx = raw_lower.find(brand)
                start = max(0, idx - 5)
                end   = min(len(raw), idx + len(brand) + 40)
                fragment = raw[start:end].strip()
                # Làm sạch các từ thừa
                fragment = re.sub(r'^(kính|gọng|mắt kính|cho|của|hỏi|về)\s*', '', fragment, flags=re.IGNORECASE)
                fragment = re.sub(r'\s*(giá|bao nhiêu|có không|như thế nào|\?).*$', '', fragment, flags=re.IGNORECASE).strip()
                if len(fragment) > 3:
                    return fragment

        # 2. Pattern "kính [tên dài >= 5 chữ]" — loại trừ NOT_PRODUCT_NAME
        patterns = [
            r'(?:kính|gọng|mắt kính)\s+([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9\s]{4,60}?)(?:\s+(?:giá|bao nhiêu|có không|như thế nào|là gì)|\?|$)',
            r'(?:hỏi về|thông tin|chi tiết|mô tả)\s+(?:kính\s+)?([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9\s]{4,60}?)(?:\s+(?:giá|bao nhiêu|\?)|\?|$)',
            r'(?:muốn mua|đặt)\s+(?:kính\s+)?([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9\s]{4,60}?)(?:\s+(?:đó|này|\?)|\?|$)',
        ]
        for pat in patterns:
            m = re.search(pat, raw, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                # Kiểm tra không phải từ chung
                if name.lower() not in NOT_PRODUCT_NAME and len(name) >= 5:
                    # Xác nhận thêm: có ít nhất 1 chữ hoa hoặc dài hơn 8 ký tự
                    if re.search(r'[A-Z]', name) or len(name) > 8:
                        return name

        # 3. Viết hoa liên tiếp (tên riêng)
        caps = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+\b', raw)
        for c in caps:
            if c.lower() not in NOT_PRODUCT_NAME and len(c) > 5:
                return c

        return None

    # ── Price ────────────────────────────────────────────────

    def _extract_price(self, msg: str) -> Dict:
        result = {}
        patterns = [
            (r'(?:từ|trên|hơn)\s*(\d[\d,\.]*)\s*(?:k|nghìn|ngàn|triệu|tr\b)', 'min'),
            (r'(?:dưới|không quá|tối đa|đến)\s*(\d[\d,\.]*)\s*(?:k|nghìn|ngàn|triệu|tr\b)', 'max'),
            (r'(?:tầm|khoảng|cỡ)\s*(\d[\d,\.]*)\s*(?:k|nghìn|ngàn|triệu|tr\b)', 'approx'),
            (r'(\d[\d,\.]*)\s*(?:k|nghìn|ngàn|triệu|tr\b)\s*[-–đến]+\s*(\d[\d,\.]*)\s*(?:k|nghìn|ngàn|triệu|tr\b)', 'range'),
        ]
        for pat, t in patterns:
            m = re.search(pat, msg)
            if not m:
                continue
            if t == 'range':
                v1 = self._parse_money(m.group(1), msg)
                v2 = self._parse_money(m.group(2), msg)
                if v1: result['price_min'] = v1
                if v2: result['price_max'] = v2
            elif t == 'min':
                v = self._parse_money(m.group(1), msg)
                if v: result['price_min'] = v
            elif t == 'max':
                v = self._parse_money(m.group(1), msg)
                if v: result['price_max'] = v
            elif t == 'approx':
                v = self._parse_money(m.group(1), msg)
                if v:
                    result['price_min'] = v * 0.8
                    result['price_max'] = v * 1.25
        return result

    @staticmethod
    def _parse_money(s: str, ctx: str) -> Optional[float]:
        try:
            n = float(re.sub(r'[,\.]', '', s))
            if 'triệu' in ctx or ' tr' in ctx:
                return n * 1_000_000
            if 'nghìn' in ctx or 'ngàn' in ctx or 'k' in ctx:
                return n * 1_000 if n < 10_000 else n
            return n * 1_000 if n < 1_000 else n
        except Exception:
            return None

    # ── Gender / Face ────────────────────────────────────────

    @staticmethod
    def _extract_gender(msg: str) -> Optional[str]:
        if any(w in msg for w in ['cho nam', 'của nam', ' nam ', 'con trai', 'bạn trai', 'đàn ông']):
            return 'male'
        if any(w in msg for w in ['cho nữ', 'của nữ', ' nữ ', 'con gái', 'bạn gái', 'phụ nữ']):
            return 'female'
        if 'unisex' in msg:
            return 'unisex'
        return None

    @staticmethod
    def _extract_face(msg: str) -> Optional[str]:
        faces = {
            'tròn':      ['mặt tròn', 'khuôn mặt tròn'],
            'vuông':     ['mặt vuông', 'khuôn mặt vuông'],
            'dài':       ['mặt dài',  'khuôn mặt dài'],
            'trái xoan': ['mặt trái xoan', 'mặt oval', 'khuôn mặt oval'],
            'tim':       ['mặt tim',  'khuôn mặt tim'],
        }
        for shape, variants in faces.items():
            if any(v in msg for v in variants):
                return shape
        return None

    # ── Normalize ─────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r'\s+', ' ', t)
        abbrs = {
            'ko ': 'không ', ' k ': ' không ', 'dc ': 'được ',
            'đc ': 'được ', 'mk ': 'mình ', 'bn ': 'bạn ',
            'bnh ': 'bao nhiêu ', 'ntn ': 'như thế nào ',
            'oke': 'ok', 'oki': 'ok',
        }
        for a, b in abbrs.items():
            t = t.replace(a, b)
        return t