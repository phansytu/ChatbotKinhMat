-- =============================================================
-- DATABASE SETUP - KinhMat Chatbot
-- MySQL Workbench
-- =============================================================
-- Chạy file này trong MySQL Workbench để tạo database và bảng
-- =============================================================

-- 1. Tạo database
CREATE DATABASE IF NOT EXISTS kinh_mat_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE kinh_mat_db;

-- 2. Tạo bảng products
CREATE TABLE IF NOT EXISTS products (
    id              INT             NOT NULL AUTO_INCREMENT,
    name            VARCHAR(255)    NOT NULL,
    brand           VARCHAR(100)    DEFAULT NULL,
    price           DECIMAL(12, 0)  NOT NULL,
    sale_price      DECIMAL(12, 0)  DEFAULT NULL,
    description     TEXT            DEFAULT NULL,
    gender          ENUM('male','female','unisex') DEFAULT 'unisex',
    frame_material  VARCHAR(100)    DEFAULT NULL,
    stock           INT             NOT NULL DEFAULT 0,
    status          ENUM('active','inactive') DEFAULT 'active',
    image           VARCHAR(500)    DEFAULT NULL,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_brand    (brand),
    INDEX idx_gender   (gender),
    INDEX idx_price    (price),
    INDEX idx_status   (status),
    INDEX idx_material (frame_material),
    FULLTEXT INDEX ft_search (name, brand, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Dữ liệu mẫu
INSERT INTO products (name, brand, price, sale_price, description, gender, frame_material, stock, image) VALUES

-- Gọng kim loại nam
('Gọng Kính Titan Siêu Nhẹ Classic', 'ProVision', 850000, 680000,
 'Gọng titan siêu nhẹ chỉ 8g, không gây dị ứng, thiết kế tối giản lịch sự. Phù hợp đi làm và dự tiệc.',
 'male', 'Titan', 15, 'titan_classic_m.jpg'),

('Gọng Kính Kim Loại Mỏng Vuông', 'StyleMen', 320000, NULL,
 'Gọng kim loại inox mỏng, kiểu chữ nhật cổ điển. Phù hợp khuôn mặt tròn và bầu dục.',
 'male', 'Kim loại inox', 30, 'metal_square_m.jpg'),

('Gọng Kính Phi Công Vintage', 'AviatorX', 450000, 380000,
 'Gọng phi công kim loại mạ vàng, tông đen, kiểu dáng cổ điển. Phù hợp mặt dài và trái xoan.',
 'male', 'Kim loại mạ vàng', 20, 'aviator_m.jpg'),

-- Gọng nhựa nam
('Gọng Nhựa Đen Vuông Cá Tính', 'UrbanStyle', 280000, NULL,
 'Gọng nhựa ABS cao cấp màu đen bóng, thiết kế vuông vắn góc cạnh mạnh mẽ.',
 'male', 'Nhựa ABS', 25, 'plastic_black_m.jpg'),

('Gọng Acetate Đồi Mồi Retro', 'RetroLens', 520000, 420000,
 'Gọng acetate tortoise (đồi mồi) phong cách vintage. Màu nâu vân đặc trưng, sang trọng.',
 'male', 'Acetate', 12, 'acetate_tortoise_m.jpg'),

-- Gọng nữ
('Gọng Mèo Mắt Cat Eye Hàn Quốc', 'KoreanEye', 350000, 280000,
 'Gọng cat eye trendy, góc vểnh nhẹ nhàng nữ tính. Đang là kiểu hot nhất từ Hàn Quốc.',
 'female', 'Nhựa acetate', 35, 'cat_eye_f.jpg'),

('Gọng Tròn Nhỏ Pastel Nữ', 'SoftCircle', 290000, NULL,
 'Gọng tròn nhỏ xinh màu pastel (hồng nhạt, xanh mint, trắng sữa). Phong cách Hàn Quốc nhẹ nhàng.',
 'female', 'Nhựa TR90', 40, 'round_pastel_f.jpg'),

('Gọng Kim Loại Mỏng Oval Nữ', 'GoldFrame', 380000, 320000,
 'Gọng kim loại mỏng màu vàng hồng rose gold, kiểu oval thanh lịch. Phù hợp công sở và dạo phố.',
 'female', 'Kim loại mạ rose gold', 28, 'oval_rosegold_f.jpg'),

('Gọng Trong Suốt Butterfly Nữ', 'ClearWing', 410000, NULL,
 'Gọng nhựa trong suốt kiểu cánh bướm, trẻ trung và hiện đại. Mix được nhiều outfit.',
 'female', 'Nhựa trong suốt', 18, 'butterfly_clear_f.jpg'),

-- Unisex
('Gọng Tròn Kim Loại Unisex Lennon', 'ClassicRound', 300000, 250000,
 'Gọng tròn kim loại mỏng kiểu John Lennon cổ điển. Unisex, phù hợp mặt vuông.',
 'unisex', 'Kim loại inox', 45, 'lennon_round_u.jpg'),

('Gọng Boston Nhựa Unisex', 'BostonLine', 330000, NULL,
 'Gọng Boston nhựa màu đen/nâu/trong suốt. Kiểu dáng cân đối, hợp cả nam lẫn nữ.',
 'unisex', 'Nhựa acetate', 38, 'boston_u.jpg'),

('Gọng Geometric Lục Giác Unisex', 'GeoStyle', 390000, 320000,
 'Gọng hình lục giác độc đáo, cá tính. Rất hot trong cộng đồng streetwear và thời trang.',
 'unisex', 'Kim loại inox', 16, 'hexagon_u.jpg'),

('Gọng Trong Suốt TR90 Unisex', 'ClearView', 260000, NULL,
 'Gọng TR90 trong suốt siêu nhẹ, dẻo dai, không bị gãy. An toàn cho hoạt động ngoài trời.',
 'unisex', 'Nhựa TR90', 55, 'clear_tr90_u.jpg'),

-- Kính mát
('Kính Mát Phi Công Polarized', 'SunAvia', 520000, 420000,
 'Kính mát phi công tròng phân cực (polarized) chống chói. Chống UV400. Phù hợp lái xe và ngoài trời.',
 'male', 'Kim loại inox', 22, 'sunglass_aviator.jpg'),

('Kính Mát Oval Nữ Chống UV400', 'SunOval', 350000, 290000,
 'Kính mát oval nhỏ, tròng chống UV400, nhiều màu: đen, nâu, xanh dương. Phong cách Hàn Quốc.',
 'female', 'Kim loại mạ', 30, 'sunglass_oval_f.jpg'),

-- Cao cấp
('Gọng Titanium Premium Siêu Mỏng', 'TitanPro', 1200000, 980000,
 'Gọng titan nguyên khối cao cấp, mỏng chỉ 1.5mm, siêu nhẹ 6g. Bảo hành 1 năm.',
 'unisex', 'Titanium nguyên khối', 8, 'titanium_premium.jpg'),

('Gọng Acetate Handmade Italy', 'ItalyFrame', 950000, NULL,
 'Gọng acetate nhập khẩu từ Ý, làm thủ công, màu sắc độc đáo, chất liệu cao cấp bền bỉ.',
 'unisex', 'Acetate Italy', 6, 'acetate_italy.jpg'),

-- Giá rẻ
('Gọng Nhựa Cơ Bản Đen', 'BasicWear', 159000, NULL,
 'Gọng nhựa cơ bản màu đen, đơn giản, phù hợp dùng hàng ngày.',
 'unisex', 'Nhựa ABS', 100, 'basic_black.jpg'),

('Gọng Nhựa Tròn Màu Pastel', 'PastelRound', 189000, NULL,
 'Gọng tròn nhựa màu pastel nhẹ nhàng, nhiều màu sắc tươi tắn.',
 'female', 'Nhựa ABS', 80, 'pastel_round_cheap.jpg'),

('Gọng Kim Loại Mỏng Giá Tốt', 'ValueMetal', 220000, 180000,
 'Gọng kim loại mỏng giá tốt nhất phân khúc, thiết kế lịch sự cơ bản.',
 'unisex', 'Kim loại mạ', 60, 'metal_value.jpg');

-- 4. Xem kết quả
SELECT 
    id, name, brand,
    FORMAT(price, 0) AS gia_goc,
    FORMAT(sale_price, 0) AS gia_sale,
    gender, frame_material, stock, status
FROM products
ORDER BY id;

-- =============================================================
-- QUERY MẪU ĐỂ TEST
-- =============================================================

-- Tìm kính giá dưới 300k
-- SELECT id, name, price, sale_price FROM products 
-- WHERE COALESCE(sale_price, price) <= 300000 AND status = 'active' AND stock > 0;

-- Tìm kính nữ
-- SELECT id, name, gender, price FROM products 
-- WHERE gender IN ('female', 'unisex') AND status = 'active';

-- Tìm kính titan
-- SELECT id, name, frame_material, price FROM products 
-- WHERE frame_material LIKE '%titan%' AND status = 'active';
