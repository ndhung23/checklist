# Daily Checklist Factory Inspection - Detailed System Handoff

## 1. Mục đích file này

File này là bản bàn giao kỹ thuật chi tiết cho toàn bộ project hiện tại, để một AI hoặc một developer khác có thể tiếp tục làm mà không phải đọc mò toàn bộ code từ đầu.

Tài liệu này mô tả:

- Cấu trúc thư mục hiện tại
- Phần nào đang là luồng chạy chính
- Phần nào là mã cũ / không còn dùng
- Database model hiện tại
- Luồng request chính của Flask
- UI / template / CSS / JS đang hoạt động như thế nào
- Seed data tạo gì
- Những lỗi / mismatch / technical debt đang tồn tại
- Những yêu cầu mới của user đã nói nhưng chưa được implement hoàn chỉnh

## 2. Tổng quan trạng thái hệ thống

### 2.1 Luồng chính hiện tại

Hệ thống hiện tại đang chạy chủ yếu bằng stack:

- Python Flask
- SQLite
- SQLAlchemy ORM
- Jinja2
- Bootstrap local trong `python/static/vendor/bootstrap`

Entry point thực tế đang dùng:

- `python/app.py`

Database file thực tế:

- `python/database.db`

Seed data:

- `python/seed.py`

### 2.2 Những phần cũ vẫn còn trong repo

Trong repo vẫn còn:

- `backend/` dùng Node/json-server cũ
- `frontend/` dùng React cũ

Hai phần này không còn là hướng triển khai chính nữa. Chúng chỉ còn tồn tại như legacy snapshot / tham chiếu cũ. Nếu tiếp tục project theo yêu cầu hiện tại, nên ưu tiên hoàn toàn phần `python/`.

### 2.3 Mức độ hoàn thiện hiện tại

Đã có:

- login theo role
- dashboard checklist
- in checklist
- cập nhật kết quả `o / x / △ / empty`
- abnormal modal
- filter theo ngày / line / user / keyword / result
- admin user management cơ bản
- hỗ trợ đa ngôn ngữ ở mức khung
- bootstrap local

Chưa hoàn thiện hoặc đang lệch với yêu cầu mới:

- logic line theo ngày hiệu lực chưa có
- chưa có bảng lịch sử line assignment
- `daily_check_sheets` chưa có `line_id`
- dashboard vẫn đang lấy line theo `users.line_name` + `user_lines`
- một số text tiếng Việt / Nhật đang bị lỗi encoding trong source hiện tại
- còn file route/template cũ tham chiếu model cũ, không còn tương thích

## 3. Cấu trúc thư mục

### 3.1 Root

- `PYTHON_HANDOFF.md`
  - File bàn giao cũ, ngắn hơn và không còn phản ánh đầy đủ toàn bộ hiện trạng mới.
- `REACT_NODE_HANDOFF.md`
  - File bàn giao cho stack cũ React + Node.
- `SYSTEM_DETAILED_HANDOFF.md`
  - File này.

### 3.2 `python/`

Đây là thư mục chính đang chạy.

- `app.py`
- `config.py`
- `models.py`
- `seed.py`
- `init_db.py`
- `database.db`
- `requirements.txt`
- `routes/`
- `templates/`
- `static/`

### 3.3 `backend/`

Legacy json-server / Node backend cũ.

Các file chính:

- `server.js`
- `db.json`
- `package.json`

Hiện không được Flask dùng tới.

### 3.4 `frontend/`

Legacy React frontend cũ.

Các file chính:

- `src/App.js`
- `src/pages/*.js`
- `src/components/*.js`
- `src/context/AuthProvider.js`

Hiện không còn là UI chính của project.

## 4. Luồng chạy hiện tại

### 4.1 Khởi động app

File: `python/app.py`

Vai trò:

- tạo Flask app
- load config
- init SQLAlchemy
- register blueprint
- inject helper cho template
- khai báo translations
- route đổi ngôn ngữ

Blueprint đang register:

- `auth_bp` từ `routes/auth_routes.py`
- `checklist_bp` từ `routes/checklist_routes.py`
- `admin_bp` từ `routes/admin_routes.py`

### 4.2 Config

File: `python/config.py`

Nội dung:

- `SECRET_KEY`
- `SQLALCHEMY_DATABASE_URI`
- `SQLALCHEMY_TRACK_MODIFICATIONS = False`
- `PER_PAGE = 15`

Hiện tại:

- DB là SQLite local trỏ vào `python/database.db`

### 4.3 Init database

File: `python/init_db.py`

Vai trò:

- tạo app context
- `db.drop_all()`
- `db.create_all()`

Lưu ý:

- script này reset schema nhưng không seed dữ liệu
- nếu chạy xong muốn có data demo thì phải chạy tiếp `seed.py`

### 4.4 Seed dữ liệu

File: `python/seed.py`

Vai trò:

- reset database
- đọc Excel checklist
- tạo template và item checklist
- tạo line mẫu
- tạo user mẫu
- tạo mapping user-line hiện tại
- tạo daily sheet và daily results mẫu cho ngày hiện tại
- tạo abnormal report mẫu
- tạo confirmation mẫu

Lưu ý quan trọng:

- file này đang đọc Excel từ đường dẫn cứng:
  - `c:\Users\zoxy4\Downloads\TL.SL.xlsx`
- nếu AI khác chạy trên máy khác, rất có thể phải sửa `DEFAULT_EXCEL_PATH`

## 5. Database model hiện tại

File: `python/models.py`

Đây là file quan trọng nhất của hệ thống.

### 5.1 Hằng số

Có các nhóm hằng số:

- role:
  - `admin`
  - `manager`
  - `leader`
  - `staff`
- daily sheet status:
  - `draft`
  - `checking`
  - `submitted`
  - `confirmed`
  - `rejected`
- result:
  - `o`
  - `x`
  - `△`
  - `""`
- abnormal status:
  - `open`
  - `processing`
  - `fixed`
  - `confirmed`
  - `cancelled`

### 5.2 `User`

Mô tả:

- bảng user đăng nhập
- có role
- có `line_name` và `department` hiện tại dạng snapshot đơn giản

Field chính:

- `id`
- `username`
- `password_hash`
- `full_name`
- `employee_code`
- `department`
- `line_name`
- `role`
- `is_active`
- `created_at`

Relationship:

- `daily_sheets`
- `daily_results`
- `abnormal_reports`
- `owned_confirmations`
- `signed_confirmations`
- `user_lines`

Method:

- `set_password()`
- `check_password()`
- property `can_confirm`

### 5.3 `ChecklistTemplate`

Mô tả:

- master template checklist
- ví dụ VN / JP

Field:

- `template_code`
- `template_name`
- `description`
- `version`
- `is_active`

Relationship:

- `checklist_items`
- `daily_sheets`

### 5.4 `ChecklistItem`

Mô tả:

- master item của checklist
- hỗ trợ đa ngôn ngữ

Field chính:

- `template_id`
- `symbol`
- `check_time`
- `time_group`
- `item_order`
- `category_type`
- `content`
- `content_vi`
- `content_en`
- `content_ja`
- `note`
- `is_active`

Lưu ý:

- `content` hiện đang giữ gần giống `content_vi`
- UI mới chủ yếu dùng `content_vi/content_en/content_ja`

### 5.5 `DailyCheckSheet`

Mô tả:

- phiếu checklist theo user + template + ngày

Field chính:

- `user_id`
- `template_id`
- `check_date`
- `month`
- `year`
- `line_name`
- `department`
- `shift`
- `status`
- `created_at`
- `updated_at`

Unique:

- `(user_id, template_id, check_date)`

Lưu ý:

- hiện chưa có `line_id`
- đây là một thiếu sót so với yêu cầu line effective-date của user

### 5.6 `DailyCheckResult`

Mô tả:

- kết quả check cho từng item trong từng sheet

Field chính:

- `daily_sheet_id`
- `checklist_item_id`
- `user_id`
- `check_date`
- `symbol`
- `check_time`
- `content`
- `result`
- `checked_at`
- `abnormal_note`
- `created_at`
- `updated_at`

Unique:

- `(daily_sheet_id, checklist_item_id)`

Lưu ý:

- `content` là snapshot text tại thời điểm generate
- UI đang hiển thị nội dung bằng `get_item_content(result.checklist_item, lang)`, không chỉ dùng field snapshot `content`

### 5.7 `AbnormalReport`

Mô tả:

- bản ghi lỗi / bất thường gắn 1-1 với `DailyCheckResult`

Field chính:

- `daily_sheet_id`
- `daily_check_result_id`
- `user_id`
- `symbol`
- `occurred_date`
- `abnormal_content`
- `countermeasure`
- `confirm_date_before_fix`
- `result_after_fix`
- `status`
- `created_at`
- `updated_at`

Unique:

- `daily_check_result_id`

### 5.8 `DailyConfirmation`

Mô tả:

- lưu xác nhận checklist theo vai trò xác nhận

Field chính:

- `daily_sheet_id`
- `user_id`
- `confirmed_by`
- `confirmed_by_name`
- `confirmed_role`
- `confirmed_at`
- `signature_note`

Unique:

- `(daily_sheet_id, confirmed_role)`

### 5.9 `Line`

Mô tả:

- danh mục line nhà máy

Field:

- `line_name`
- `department`
- `description`
- `is_active`

### 5.10 `UserLine`

Mô tả:

- mapping user với nhiều line
- đang được dùng cho leader quản lý nhiều line

Field:

- `user_id`
- `line_id`

Lưu ý:

- bảng này chỉ biểu diễn quan hệ line hiện tại
- không có `effective_from/effective_to`
- chưa đáp ứng yêu cầu quản lý line theo ngày hiệu lực

## 6. Routes hiện tại

### 6.1 `routes/auth_routes.py`

Vai trò:

- load current user từ session
- decorator `login_required`
- decorator `admin_required`
- login/logout

Các hàm chính:

- `get_current_user()`
- `login_required()`
- `admin_required()`
- `load_logged_in_user()`
- `login()`
- `logout()`

Flow login:

1. lấy `username/password` từ form
2. query `User` với `is_active=True`
3. check hash password
4. ghi session:
   - `user_id`
   - `role`
   - `lang`

### 6.2 `routes/checklist_routes.py`

Đây là route file quan trọng nhất của app.

#### Hàm helper

- `parse_date()`
  - parse `YYYY-MM-DD`
- `managed_line_names(user)`
  - admin/manager thấy mọi line active
  - leader thấy line từ `user.user_lines`
- `can_view_sheet(user, sheet)`
  - admin/manager: toàn quyền
  - leader: line thuộc phạm vi quản lý
  - staff: chỉ sheet của chính mình
- `can_edit_result(user, result)`
  - admin hoặc chính chủ result
- `get_template_id()`
  - lấy template đầu tiên từ DB
- `ensure_daily_sheet_and_results(user_id, template_id, selected_date)`
  - nếu chưa có `daily_check_sheet` thì tạo
  - nếu chưa có `daily_check_result` cho item active thì generate result rỗng
  - đây là logic bảo đảm chọn ngày mới vẫn luôn hiện full checklist master

#### Hàm build context

- `get_target_users(...)`
  - xác định tập user cần prepare sheet theo role/filter
- `build_dashboard_context(...)`
  - chuẩn bị toàn bộ data cho dashboard:
    - sheets
    - selected_sheet
    - results
    - abnormal_reports
    - confirmations
    - result_summary
    - visible_lines
    - visible_users
    - filter state

#### Routes chính

- `GET /`
  - redirect về dashboard hoặc login
- `GET /dashboard`
  - trang checklist chính
- `POST /check-result/<result_id>/update`
  - update nhanh `o` hoặc `empty`
- `POST /check-result/<result_id>/abnormal`
  - update `x` hoặc `△` và ghi abnormal report
- `GET /abnormal-reports`
  - render lại dashboard với section abnormal
- `GET /checklist/print/<sheet_id>`
  - trang in

#### Logic filter/search hiện tại

Dashboard hỗ trợ:

- date
- line
- user_id
- keyword
- result_filter

`keyword` search vào:

- `DailyCheckResult.symbol`
- `DailyCheckResult.content`
- `DailyCheckResult.abnormal_note`
- `DailyCheckResult.result`
- `ChecklistItem.content_vi`
- `ChecklistItem.content_en`
- `ChecklistItem.content_ja`

`result_filter` hỗ trợ:

- `all`
- `o`
- `x`
- `△`
- `none`

### 6.3 `routes/admin_routes.py`

Vai trò:

- admin quản lý tài khoản
- tạo user
- sửa user
- khóa/mở tài khoản
- gán line hiện tại qua `user_lines`

Các hàm:

- `upsert_user_lines(user, line_ids)`
  - clear hết `user.user_lines`
  - thêm line mới
  - cập nhật `user.line_name` và `user.department` bằng line đầu tiên trong danh sách
- `users()`
  - GET: render trang quản lý user
  - POST: create/update user
- `toggle_user(user_id)`
  - khóa / mở tài khoản

Giới hạn hiện tại:

- chưa có route đổi line theo ngày hiệu lực
- chưa có lịch sử line assignment
- đang overwrite line hiện tại trên `users`

## 7. Templates hiện tại

### 7.1 `templates/base.html`

Vai trò:

- layout gốc
- import bootstrap local
- import `style.css`
- navbar top
- language switcher
- flash message
- import bootstrap JS local + `main.js`

### 7.2 `templates/login.html`

Vai trò:

- trang login đơn giản
- hiển thị tài khoản mẫu

Nội dung:

- form username/password
- danh sách account demo

### 7.3 `templates/dashboard.html`

Vai trò:

- trang chính của user/admin/manager/leader

Các block UI chính:

1. hero panel
2. filter form
3. stats cards
4. bảng daily sheets
5. bảng checklist results
6. bảng abnormal report
7. modal cập nhật abnormal

Chi tiết logic template:

- admin sẽ được bọc thêm sidebar trái
- bảng checklist không hiện DB id thật, chỉ dùng `loop.index`
- action form vẫn dùng `result.id` thật trong URL
- content checklist đang render theo:
  - `get_item_content(result.checklist_item, current_lang)`

### 7.4 `templates/print_checklist.html`

Vai trò:

- trang in checklist theo sheet

Có:

- header giống form
- bảng checklist theo ngày
- bảng abnormal history
- bảng khu vực ký xác nhận

### 7.5 `templates/admin_layout.html`

Vai trò:

- layout 2 cột cho admin
- cột trái là sidebar
- cột phải là nội dung admin page

### 7.6 `templates/admin_users.html`

Vai trò:

- form tạo / sửa user
- bảng danh sách user
- cho phép:
  - sửa role
  - sửa profile cơ bản
  - gán line hiện tại
  - khóa / mở user

### 7.7 `templates/partials/sidebar.html`

Vai trò:

- sidebar admin

Trạng thái:

- `Dashboard` và `Quản lý tài khoản` đang là link active thực
- các mục:
  - `Quản lý hạng mục`
  - `Quản lý line`
  - `Báo cáo bất thường`
  - `Xác nhận checklist`
  - hiện chỉ là placeholder disabled

### 7.8 `templates/partials/language_switcher.html`

Vai trò:

- nút đổi ngôn ngữ:
  - Việt
  - English
  - 日本語

Hoạt động bằng:

- gọi route `/set-language/<lang>`
- lưu `lang` vào session

### 7.9 Các template/partial cũ còn tồn tại

Các file này còn trong repo nhưng không thuộc luồng chạy chính hiện tại:

- `templates/admin_categories.html`
- `templates/partials/navbar.html`
- `templates/partials/pagination.html`
- `templates/partials/status_badge.html`

Chúng chủ yếu là di sản từ version cũ.

## 8. Static assets

### 8.1 `static/css/style.css`

Vai trò:

- style toàn bộ app

Các nhóm style chính:

- layout chung
- navbar
- language switcher
- hero panel
- stats grid
- card
- table checklist kiểu Excel
- sticky header
- badge màu theo result
- badge màu theo abnormal status
- sidebar admin
- login page
- print page
- media query responsive
- `@media print`

### 8.2 `static/js/main.js`

Vai trò:

- xử lý modal abnormal

Flow:

1. bắt event `show.bs.modal`
2. lấy `data-*` từ nút bấm
3. fill vào form modal:
   - action
   - id
   - symbol
   - date
   - result
   - content
   - note
   - countermeasure
   - confirm date
   - result after fix
   - status

### 8.3 Bootstrap local

Đang dùng file local:

- `static/vendor/bootstrap/css/bootstrap.min.css`
- `static/vendor/bootstrap/js/bootstrap.bundle.min.js`

Không dùng CDN trong layout chính.

## 9. Seed data hiện tại

Sau khi chạy `python/seed.py`, hệ thống tạo:

### 9.1 Line mẫu

- Line A - TL/SL
- Line B - TL/SL
- Line C - Assembly
- Line D - Inspection

### 9.2 User mẫu

- `admin / 123456`
- `manager01 / 123456`
- `leader01 / 123456`
- `leader02 / 123456`
- `staff01 / 123456`
- `staff02 / 123456`
- `staff03 / 123456`
- `staff04 / 123456`

### 9.3 User-Line mapping

- `leader01` -> Line A, Line B
- `leader02` -> Line C, Line D
- `staff01` -> Line A
- `staff02` -> Line B
- `staff03` -> Line C
- `staff04` -> Line D

### 9.4 Template

Seed đọc từ file Excel:

- sheet VN
- sheet JP

Tạo:

- template `TL_SL_VN`
- template `TL_SL_JP`

### 9.5 Daily sheet mẫu

Tạo sheet cho ngày hiện tại cho:

- leader01
- leader02
- staff01
- staff02
- staff03
- staff04

### 9.6 Result mẫu

Tạo result theo pattern:

- một số `o`
- một số `x`
- một số `△`
- một số `empty`

### 9.7 Abnormal report mẫu

Tạo tự động từ các result `x` và `△`.

### 9.8 Confirmation mẫu

Tạo 2 confirmation mẫu:

- manager xác nhận cho leader01
- leader xác nhận cho staff02

## 10. Luồng nghiệp vụ chính

### 10.1 Login

1. user vào `/login`
2. submit username/password
3. `auth_routes.login()` xác thực
4. lưu session
5. redirect `/dashboard`

### 10.2 Mở dashboard

1. `checklist_routes.dashboard()` nhận filter
2. `build_dashboard_context()` chạy
3. `ensure_daily_sheet_and_results()` tạo sheet/result nếu thiếu
4. query sheet theo role
5. query result theo selected sheet
6. render `templates/dashboard.html`

### 10.3 Staff update result nhanh

Nếu staff bấm:

- `o`:
  - gọi `POST /check-result/<id>/update`
  - lưu `result = o`
  - clear abnormal note nếu cần
- `Clear`:
  - lưu `result = ""`
  - nếu có abnormal report thì đổi `status = cancelled`

### 10.4 Staff update abnormal

Nếu staff bấm `x` hoặc `△`:

1. mở modal
2. JS fill dữ liệu từ row vào modal
3. submit `POST /check-result/<id>/abnormal`
4. route validate quyền
5. route validate `result` là `x` hoặc `△`
6. bắt buộc `abnormal_content`
7. update `DailyCheckResult`
8. create/update `AbnormalReport`

### 10.5 Print checklist

1. user mở `/checklist/print/<sheet_id>`
2. route check quyền
3. load results + abnormal reports + confirmations
4. render `print_checklist.html`

### 10.6 Admin quản lý tài khoản

1. admin mở `/admin/users`
2. xem danh sách user
3. dùng cùng 1 form để create/update
4. line được gán qua checkbox `line_ids`
5. route `upsert_user_lines()` clear mapping cũ rồi tạo mapping mới

## 11. Những file cũ / không dùng / nguy hiểm nếu AI khác sửa nhầm

### 11.1 `python/routes/category_routes.py`

File này tham chiếu model cũ:

- `Category`
- `DailyCheck`

Hai model này không còn tồn tại trong `models.py` hiện tại.

Kết luận:

- file này là legacy, không dùng được nếu import vào app hiện tại
- nếu register blueprint này sẽ lỗi

### 11.2 `python/routes/confirmation_routes.py`

File này cũng là legacy:

- import `manager_or_admin_required` từ `auth_routes`, nhưng decorator này hiện không còn tồn tại
- logic confirmation cũng dùng schema cũ (`date`, `user_id`) không khớp hoàn toàn với design mới

Kết luận:

- không dùng trong app hiện tại

### 11.3 `python/templates/admin_categories.html`

Template này đi với `category_routes.py` cũ.

Kết luận:

- legacy

### 11.4 `python/templates/partials/navbar.html`

Partial navbar cũ, tham chiếu:

- `current_user.name`

Trong model mới field đúng là:

- `full_name`

Kết luận:

- không dùng
- nếu dùng lại sẽ lỗi dữ liệu

## 12. Vấn đề encoding hiện tại

Đây là điểm rất quan trọng cho AI tiếp theo.

Source hiện tại có dấu hiệu mojibake / encoding hỏng ở nhiều file. Ví dụ:

- tiếng Việt trong `app.py`
- tiếng Việt trong `dashboard.html`
- ký hiệu `△` đôi lúc xuất hiện thành chuỗi hỏng
- tiếng Nhật trong translation table bị lỗi byte

Triệu chứng:

- source file hiển thị kiểu `NgĂ y`, `Káº¿t quáº£`, `â–³`

Nguyên nhân:

- file được lưu / patch qua nhiều vòng với encoding không thống nhất

Hệ quả:

- UI có thể vẫn render được ở vài chỗ nếu browser decode theo UTF-8, nhưng source hiện tại không sạch
- AI tiếp theo nên ưu tiên normalize toàn bộ file text về UTF-8 chuẩn

Ưu tiên sửa:

1. `python/app.py`
2. `python/models.py`
3. `python/routes/*.py`
4. `python/templates/*.html`
5. `python/seed.py`

## 13. Gap giữa code hiện tại và yêu cầu user gần đây

User gần đây yêu cầu:

- quản lý line theo ngày hiệu lực
- không ghi đè line cũ
- thêm `UserLineAssignment`
- `DailyCheckSheet` lưu snapshot `line_id`, `line_name`, `department`
- admin xem lịch sử line
- route đổi line có `effective_from`

Hiện trạng:

- chưa có `UserLineAssignment`
- chưa có helper `get_user_line_by_date()`
- `ensure_daily_sheet_and_results()` vẫn dùng `user.line_name` và `user.department`
- `admin_routes.upsert_user_lines()` đang ghi đè line hiện tại ngay lập tức
- chưa có UI lịch sử line

Kết luận:

- yêu cầu line-effective-date chưa được implement
- đây là hạng mục quan trọng tiếp theo

## 14. File nào cần ưu tiên sửa tiếp

Nếu tiếp tục theo yêu cầu mới nhất, AI tiếp theo nên ưu tiên:

1. `python/models.py`
   - thêm `UserLineAssignment`
   - thêm `line_id` cho `DailyCheckSheet`
2. `python/seed.py`
   - seed assignment theo hiệu lực
3. `python/routes/admin_routes.py`
   - thêm route đổi line theo ngày hiệu lực
4. `python/routes/checklist_routes.py`
   - resolve line theo ngày bằng assignment history
5. `python/templates/admin_users.html`
   - thêm form đổi line có `effective_from`
   - thêm bảng lịch sử line
6. `python/templates/dashboard.html`
   - hiển thị line áp dụng theo ngày

## 15. Cách chạy hiện tại

### 15.1 Cài dependency

```powershell
cd daily-check-app\python
py -m pip install -r requirements.txt
```

### 15.2 Reset DB

```powershell
py init_db.py
```

### 15.3 Seed data

```powershell
py seed.py
```

### 15.4 Chạy app

```powershell
py app.py
```

Mặc định:

- host: `0.0.0.0`
- port: `5000`

## 16. Tài khoản test

- `admin / 123456`
- `manager01 / 123456`
- `leader01 / 123456`
- `leader02 / 123456`
- `staff01 / 123456`
- `staff02 / 123456`
- `staff03 / 123456`
- `staff04 / 123456`

## 17. Kết luận ngắn cho AI tiếp theo

Nếu bạn là AI tiếp theo tiếp quản project này, hãy hiểu như sau:

- Chỉ tập trung vào thư mục `python/`
- `app.py + models.py + routes/checklist_routes.py + routes/admin_routes.py + templates/` là trục chính
- `backend/` và `frontend/` là legacy
- Có technical debt lớn về encoding
- Có technical debt về file route/template cũ chưa xóa
- Feature lớn tiếp theo là line assignment theo ngày hiệu lực
- Khi sửa tiếp, cần giữ nguyên nguyên tắc:
  - không phá dữ liệu checklist cũ
  - không overwrite snapshot quá khứ
  - mọi logic mới phải xoay quanh daily sheet snapshot theo ngày

