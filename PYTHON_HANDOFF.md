# Daily Check Python Handoff

## Mục đích file này

File này giải thích bản Python mới trong thư mục `python` để có thể ném tiếp cho AI khác mà không phải bắt nó đọc lại toàn bộ project từ đầu.

Project này là bản chuyển đổi từ React/Node sang Python fullstack, dùng:

- Flask
- Jinja2
- Bootstrap 5
- SQLite
- SQLAlchemy
- Flask session auth

Project mới được viết trong:

```txt
python/
```

Không thay thế file nào trong `daily-check-app`.

## Cấu trúc hiện tại của project Python

```txt
python/
├── app.py
├── config.py
├── requirements.txt
├── database.db
├── models.py
├── seed.py
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py
│   ├── category_routes.py
│   ├── checklist_routes.py
│   └── confirmation_routes.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── admin_categories.html
│   ├── print_checklist.html
│   └── partials/
│       ├── navbar.html
│       ├── pagination.html
│       └── status_badge.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

## Ý tưởng thiết kế hiện tại

Bản Python này không dùng SPA nữa.

Thay vào đó:

- Flask render HTML bằng Jinja2
- Form POST trực tiếp về server
- Session lưu ở Flask session
- SQLAlchemy dùng cho toàn bộ dữ liệu

## Các file chính và vai trò

### 1. `app.py`

File boot app Flask.

Nó làm các việc:

- tạo app
- load `Config`
- init `db`
- register các blueprint:
  - `auth_bp`
  - `checklist_bp`
  - `category_bp`
  - `confirmation_bp`
- inject `current_user` vào template
- tạo filter Jinja cho date/time/datetime
- tạo route `/health`

### 2. `config.py`

Chứa:

- `SECRET_KEY`
- `SQLALCHEMY_DATABASE_URI`
- `SQLALCHEMY_TRACK_MODIFICATIONS = False`
- `PER_PAGE = 15`

### 3. `models.py`

Chứa toàn bộ model SQLAlchemy.

Model hiện có:

- `User`
- `Category`
- `DailyCheck`
- `AbnormalNote`
- `DailyConfirmation`

Các constant nghiệp vụ:

- `STATUS_DONE = "o"`
- `STATUS_PENDING = "x"`
- `STATUS_ABNORMAL = "△"`
- `VALID_STATUSES`

#### User

Field:

- `id`
- `username`
- `password`
- `name`
- `role`

Password đang được hash bằng `werkzeug.security`.

#### Category

Field:

- `id`
- `symbol`
- `category`
- `limit_time`
- `created_at`

#### DailyCheck

Field:

- `id`
- `user_id`
- `category_id`
- `symbol`
- `category`
- `date`
- `status`
- `limit_time`
- `created_at`
- `updated_at`

Ràng buộc:

- unique theo `(user_id, category_id, date)`

Mục tiêu:

- tránh tạo trùng checklist cho cùng user, cùng category, cùng ngày

#### AbnormalNote

Field:

- `id`
- `user_id`
- `daily_check_id`
- `symbol`
- `category`
- `note`
- `created_at`

Ràng buộc:

- mỗi `daily_check_id` chỉ có 1 abnormal note

#### DailyConfirmation

Field:

- `id`
- `user_id`
- `date`
- `confirmed_by`
- `confirmed_by_name`
- `confirmed_at`
- `signature_note`

Ràng buộc:

- unique theo `(user_id, date)`

## Auth flow hiện tại

File: `python/routes/auth_routes.py`

### Decorators đã có

- `login_required`
- `admin_required`
- `manager_or_admin_required`

### Session được lưu thế nào

Sau login thành công:

```python
session["user_id"]
session["role"]
session["name"]
```

### Current user

`get_current_user()` đọc `session["user_id"]` rồi query `User`.

`before_app_request` load vào:

```python
g.current_user
```

### Route auth

- `GET /login`
- `POST /login`
- `GET /logout`

## Checklist flow hiện tại

File: `python/routes/checklist_routes.py`

Đây là file quan trọng nhất của app.

### Route chính

- `GET /`
- `GET /dashboard`

### Logic dashboard hiện tại

Dashboard đang:

- default ngày hiện tại nếu không có filter
- query checklist theo ngày
- nếu là `user` thì chỉ lấy checklist của chính họ
- nếu là `admin/manager` thì có thể filter theo user
- hỗ trợ filter:
  - `date`
  - `status`
  - `user_id`
  - `keyword`
- sort theo:
  - `DailyCheck.date ASC`
  - `DailyCheck.limit_time ASC`
  - `DailyCheck.id ASC`

### Pagination

Đang dùng:

```python
per_page = 15
```

Và template hiển thị:

```txt
Hiển thị X-Y / Z mục
```

### Highlight nearest time

Đã có helper:

- `time_to_minutes()`
- `find_nearest_check()`

Hiện tại chỉ highlight khi:

- user đang xem checklist của chính mình và không có filter `keyword/status`
- hoặc admin/manager đã chọn một user cụ thể và không có `keyword/status`

Lý do:

- nếu admin đang xem toàn bộ nhiều user cùng lúc thì highlight nearest không có nghĩa nghiệp vụ rõ ràng

### Update status

Route:

```txt
POST /checklist/update-status
```

Logic:

- user chỉ được sửa checklist của chính họ
- admin/manager hiện không có UI sửa status
- status hợp lệ:
  - `o`
  - `x`
  - `△`
- nếu chuyển sang `△` và có note thì tạo/cập nhật `AbnormalNote`
- nếu chuyển từ `△` sang trạng thái khác thì xóa abnormal note cũ

### Generate daily checklist

Route:

```txt
POST /checklist/generate
```

Chỉ admin được gọi.

Logic:

- lấy toàn bộ `Category`
- lấy user được chọn
- với mỗi category:
  - nếu chưa tồn tại `DailyCheck` cho `user/category/date` đó thì tạo mới
- `status` mặc định là `x`

Khác với backend cũ:

- backend mới không reject cả request nếu đã tồn tại một phần
- nó sẽ bỏ qua những item đã có và tạo phần còn thiếu

Đây là chủ đích để mềm hơn khi dùng thật.

### Print checklist

Route:

```txt
GET /checklist/print
```

Query:

- `user_id`
- `date`

Logic:

- user thường chỉ được in checklist của chính họ
- admin/manager có thể in của user khác
- load checklist theo user/ngày
- load abnormal note
- load daily confirmation
- render `print_checklist.html`

## Category flow hiện tại

File: `python/routes/category_routes.py`

### Route chính

- `GET /categories`
- `POST /categories`

### Các route phụ

- `POST /categories/<id>/update`
- `POST /categories/<id>/delete`

### Quyền

- chỉ admin được vào

### Logic update category

Khi sửa category:

- update record trong `Category`
- đồng thời update toàn bộ `DailyCheck` liên quan:
  - `symbol`
  - `category`
  - `limit_time`

Lý do:

- `DailyCheck` đang là snapshot theo ngày
- nhưng vì yêu cầu muốn giữ logic category dùng chung, việc sync field giúp dữ liệu đồng nhất hơn

### Logic delete category

Hiện tại:

- nếu category đã được dùng trong `DailyCheck` thì không cho xóa

Đây là lựa chọn an toàn.

Nếu AI khác muốn đổi hành vi, có thể chuyển sang soft-delete hoặc cascade.

## Confirmation flow hiện tại

File: `python/routes/confirmation_routes.py`

### Route

```txt
POST /confirm
```

### Quyền

- chỉ `admin` hoặc `manager`

### Logic

- nhận `user_id`
- nhận `date`
- nhận `signature_note`
- nếu ngày đó đã có `DailyConfirmation` thì không tạo lại
- nếu chưa có thì tạo:
  - `confirmed_by = current_user.id`
  - `confirmed_by_name = current_user.name`
  - `confirmed_at = datetime.now()`
  - `signature_note`

## Template/UI hiện tại

### 1. `login.html`

Trang login đơn giản:

- form username/password
- hiển thị tài khoản demo

### 2. `base.html`

Layout chung:

- Bootstrap 5 CDN
- CSS local
- navbar partial
- flash messages

### 3. `dashboard.html`

Đây là view trung tâm.

Nó đang có:

- hero section
- stat cards
- bộ filter
- khối generate checklist cho admin
- khối confirmation cho manager/admin
- bảng checklist
- modal thông báo checklist chưa hoàn thành/bất thường
- modal ghi chú abnormal cho từng dòng checklist user
- link sang print page

### 4. `admin_categories.html`

Trang CRUD category:

- form thêm
- bảng danh sách
- collapse inline edit
- delete button

### 5. `print_checklist.html`

Trang in:

- thông tin người thực hiện
- ngày
- bảng checklist
- abnormal note
- confirmation của cấp trên
- nút `window.print()`

### 6. Partial template

- `partials/navbar.html`
- `partials/status_badge.html`
- `partials/pagination.html`

## CSS/UI hiện tại

File: `python/static/css/style.css`

Theme đang dùng đúng định hướng sáng:

- background sáng
- card trắng
- text rõ
- màu primary xanh
- status badge rõ
- responsive

UI không cố clone lại React cũ, mà là bản server-rendered sạch hơn.

## Seed data hiện tại

File: `python/seed.py`

Nó đang:

- `drop_all()`
- `create_all()`
- tạo users:
  - `admin`
  - `manager01`
  - `user01`
  - `user02`
- tạo 30 categories
- tạo checklist hôm nay cho `user01`, `user02`
- tạo một ít dữ liệu ngày hôm qua cho `user01`
- tạo abnormal notes
- tạo một daily confirmation mẫu

### Tài khoản seed

- `admin / 123456`
- `manager01 / 123456`
- `user01 / 123456`
- `user02 / 123456`

## Những gì đã được verify

Tôi đã chạy các kiểm tra sau trên project Python:

### 1. Compile check

Đã compile toàn bộ file Python, không lỗi syntax.

### 2. Install dependency

Đã cài:

- Flask
- Flask-SQLAlchemy
- Werkzeug

### 3. Run seed

`seed.py` chạy thành công và tạo `database.db`.

### 4. Smoke test route

Đã test:

- `GET /login`
- `POST /login`
- `GET /dashboard`
- `GET /categories`
- `GET /checklist/print?...`

Các route này trả về HTTP hợp lệ.

## Những chỗ có thể cần AI khác làm tiếp

Project hiện tại đã chạy được, nhưng nếu muốn polish tiếp thì đây là các hướng ưu tiên:

### 1. Tách logic helper ra file riêng

Hiện tại một số helper như parse date/time, nearest check đang nằm trong route file.

Có thể tách ra:

- `utils/helpers.py`
- `services/checklist_service.py`

### 2. Cải thiện manager UX

Hiện manager dùng chung dashboard với admin-lite:

- xem checklist user
- ký xác nhận

Có thể thêm:

- dropdown user mặc định rõ hơn
- danh sách user cần ký trong ngày

### 3. Tinh chỉnh abnormal workflow

Hiện user bấm `△` thì mở modal nhập note.

Có thể làm tốt hơn:

- bắt buộc note nếu abnormal
- cho phép edit note riêng cả khi trạng thái vẫn giữ `△`

### 4. Xử lý quyền chi tiết hơn

Hiện tại:

- user không thấy UI chỉnh gì ngoài status
- admin/manager chủ yếu là view + confirm/generate/category

Có thể bổ sung:

- chặn sâu hơn ở server cho các route khác nếu mở rộng sau này

### 5. Cải thiện seed

Có thể thêm:

- nhiều ngày hơn
- nhiều confirmation hơn
- nhiều abnormal note hơn

### 6. Test tự động

Hiện chưa có bộ test chính thức.

Có thể thêm:

- pytest
- test auth
- test permission
- test generate checklist
- test confirmation unique

## Những quyết định thiết kế quan trọng

### 1. Giữ `DailyCheck` là snapshot

Tức là trong bảng `daily_checks` vẫn lưu:

- `symbol`
- `category`
- `limit_time`

thay vì chỉ join sang `Category` lúc render.

Lý do:

- đúng với logic project cũ
- dễ in/export
- ổn cho dữ liệu checklist theo ngày

### 2. Session auth thay cho localStorage auth

Khác với React cũ:

- login mới lưu session server-side
- role/user context lấy từ session

### 3. Không dùng API-first

Project Python hiện là server-rendered app.

Nghĩa là:

- form submit trực tiếp
- redirect + flash message
- không có frontend React

## Prompt gợi ý để ném cho AI khác

```txt
Đọc file PYTHON_HANDOFF.md trước, sau đó làm việc trên thư mục python.
Không thay đổi thư mục daily-check-app.
Hãy giữ nguyên stack Flask + Jinja2 + SQLite + SQLAlchemy hiện tại.
Ưu tiên đọc:
- app.py
- models.py
- routes/checklist_routes.py
- templates/dashboard.html
- seed.py

Mục tiêu là tiếp tục cải thiện project Python đã chạy được này, không viết lại từ đầu.
Nếu sửa code, hãy sửa trực tiếp trong thư mục python và giữ nguyên logic business:
- user chỉ cập nhật status checklist của chính mình
- admin quản lý category và generate checklist
- manager/admin ký xác nhận
- sort theo date ASC và limit_time ASC
- pagination 15 mục
- có notification modal, print page, abnormal notes
Không viết pseudo code.
```

## Prompt siêu ngắn để tiết kiệm token

```txt
Đọc PYTHON_HANDOFF.md rồi tiếp tục làm trên thư mục python.
Đây là Flask app thay thế cho daily-check-app cũ.
Không đụng thư mục daily-check-app.
Giữ nguyên logic role/checklist/confirm/category/generate hiện tại, chỉ polish hoặc mở rộng.
```
