# 🕶️ KinhMat AI Chatbot

Chatbot tư vấn kính mắt thông minh, chạy bằng Python Flask, kết nối MySQL, hỗ trợ tiếng Việt.

---

## 📁 Cấu trúc dự án

```
kinh_mat_chatbot/
├── app.py                      ← Flask server chính (chạy file này)
├── config.py                   ← Cấu hình DB, port, ngưỡng...
├── requirements.txt            ← Thư viện cần cài
├── setup_database.sql          ← Script tạo database MySQL
├── start.bat                   ← Click đúp để chạy (Windows)
│
├── data/
│   └── knowledge.txt           ← File dữ liệu huấn luyện chatbot
│
├── models/
│   ├── chatbot_engine.py       ← Điều phối toàn bộ logic chatbot
│   ├── knowledge_base.py       ← Đọc & tìm kiếm trong knowledge.txt
│   ├── intent_classifier.py    ← Phân loại ý định người dùng
│   └── response_generator.py   ← Tạo câu trả lời tự nhiên
│
├── utils/
│   └── db_connector.py         ← Kết nối & truy vấn MySQL
│
└── templates/
    └── index.html              ← Giao diện chat web
```

---

## 🚀 Cài đặt và chạy

### Bước 1: Cài Python (nếu chưa có)

Tải Python 3.8+ tại https://python.org và cài đặt.

### Bước 2: Cài thư viện

```bash
pip install -r requirements.txt
```

### Bước 3: Tạo database MySQL

1. Mở **MySQL Workbench**
2. Kết nối vào MySQL server
3. Mở và chạy file `setup_database.sql`
4. Database `kinh_mat_db` và bảng `products` sẽ được tạo kèm dữ liệu mẫu

### Bước 4: Cấu hình kết nối database

Mở `config.py` và sửa thông tin MySQL:

```python
DB_HOST     = 'localhost'
DB_USER     = 'root'
DB_PASSWORD = '240805'  # ← Sửa chỗ này
DB_NAME     = 'eyewear_shop'
```

### Bước 5: Chạy chatbot

**Windows:** Click đúp file `start.bat`

**Hoặc dùng terminal:**

```bash
python app.py
```

### Bước 6: Mở trình duyệt

Truy cập: http://localhost:5000

---

## 🔗 API Endpoints

### POST /api/chat

Gửi tin nhắn và nhận câu trả lời.

**Request:**

```json
{
  "message": "Kính cho mặt tròn giá 300k",
  "session_id": "user_123",
  "context": "auto"
}
```

**Response:**

```json
{
  "reply": "Mặt tròn huyền hợp với gọng chữ nhật...",
  "source": "qa_pair",
  "products": [...],
  "confidence": 0.85,
  "session_id": "user_123",
  "timestamp": "2024-01-15T10:30:00"
}
```

### POST /api/retrain

Huấn luyện lại chatbot từ file knowledge.txt.

```json
{}
```

### GET /api/health

Kiểm tra trạng thái server.

### GET /api/topics

Lấy danh sách chủ đề đã học.

### GET /api/products/search

Tìm kiếm sản phẩm từ database.

**Query params:** `q`, `brand`, `gender`, `material`, `min_price`, `max_price`, `limit`

---

## 📝 Cấu trúc file knowledge.txt

```
## Tên chủ đề

Q: Câu hỏi của khách
A: Câu trả lời của shop

Q: Câu hỏi khác
A: Trả lời khác

-----

## Chủ đề 2
...
```

### Quy tắc viết knowledge.txt:

- `##` bắt đầu một chủ đề mới
- `Q:` bắt đầu câu hỏi
- `A:` bắt đầu câu trả lời
- `-----` phân cách các nhóm (không bắt buộc)
- Hỗ trợ tiếng Việt có dấu đầy đủ

---

## 🔧 Tích hợp với Java Frontend

Gọi API từ Java:

```java
// POST /api/chat
String url = "http://localhost:5000/api/chat";
JSONObject body = new JSONObject();
body.put("message", userMessage);
body.put("session_id", sessionId);

// Gửi HTTP POST request và parse JSON response
String response = sendPost(url, body.toString());
JSONObject result = new JSONObject(response);
String reply = result.getString("reply");
```

---

## ⚙️ Cấu hình nâng cao (config.py)

| Tham số                   | Mặc định | Mô tả                            |
| ------------------------- | -------- | -------------------------------- |
| `SIMILARITY_THRESHOLD`    | 0.35     | Ngưỡng tin cậy tối thiểu         |
| `MAX_PRODUCTS_RETURN`     | 5        | Số sản phẩm tối đa trả về        |
| `TOP_K_ANSWERS`           | 3        | Số câu trả lời backup            |
| `USE_EMBEDDING`           | False    | Dùng AI embedding (cần cài thêm) |
| `MAX_HISTORY_PER_SESSION` | 10       | Lịch sử hội thoại mỗi session    |

---

## ❓ Xử lý sự cố

**Lỗi kết nối MySQL:**

- Kiểm tra MySQL đang chạy
- Kiểm tra user/password trong config.py
- Đảm bảo đã chạy setup_database.sql

**Chatbot trả lời không chính xác:**

- Thêm Q&A vào data/knowledge.txt
- Gọi POST /api/retrain để huấn luyện lại

**Lỗi import module:**

- Chạy lại `pip install -r requirements.txt`
