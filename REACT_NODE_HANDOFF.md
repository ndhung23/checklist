# Daily Check React/Node Handoff

## Mục đích file này

File này dùng để giải thích nhanh nhưng đủ sâu về project cũ trong thư mục `daily-check-app` để có thể ném tiếp cho AI khác mà không phải tốn token đọc lại toàn bộ codebase từ đầu.

Project này là bản gốc của hệ thống Daily Check, dùng:

- Frontend: ReactJS Create React App
- UI: React Bootstrap
- Backend: NodeJS
- Mock database: `json-server` + `db.json`
- Auth hiện tại: login rất đơn giản, không token, không session server-side

## Cấu trúc thư mục

```txt
daily-check-app/
├── backend/
│   ├── server.js
│   ├── db.json
│   ├── package.json
│   └── package-lock.json
└── frontend/
    ├── package.json
    ├── package-lock.json
    ├── public/
    │   └── index.html
    └── src/
        ├── App.js
        ├── App.css
        ├── index.js
        ├── api/
        │   └── axiosClient.js
        ├── components/
        │   ├── CheckTable.js
        │   ├── Loading.js
        │   ├── NavbarCustom.js
        │   └── StatusBadge.js
        ├── context/
        │   └── AuthProvider.js
        ├── pages/
        │   ├── AdminPage.js
        │   ├── DashboardPage.js
        │   ├── LoginPage.js
        │   └── UserPage.js
        └── utils/
            └── helpers.js
```

## Backend hiện tại đang làm gì

File chính là `daily-check-app/backend/server.js`.

Nó dùng `json-server` để vừa cung cấp CRUD tự động cho dữ liệu trong `db.json`, vừa thêm một số custom route.

### 1. Login

Route:

```txt
POST /login
```

Logic:

- Nhận `username`, `password`
- Đọc từ `users` trong `db.json`
- Nếu match thì trả về user object, nhưng bỏ field password
- Nếu sai thì trả về `401`

Điểm quan trọng:

- Không có JWT
- Không có session backend
- Frontend tự giữ user trong `localStorage`

### 2. Checklist cho user thường

Route:

```txt
GET /my-checks?userId=...&date=...
```

Logic:

- Bắt buộc có `userId`
- Lọc `dailyChecks` theo `userId`
- Nếu có `date` thì lọc thêm theo ngày
- Sort theo:
  - `date ASC`
  - `limitTime ASC`

### 3. Checklist cho admin/manager

Route:

```txt
GET /admin/checks?role=admin|manager&date=...
```

Logic:

- Chỉ cho `admin` hoặc `manager`
- Lấy toàn bộ `dailyChecks`
- Nếu có `date` thì lọc theo ngày
- Sort theo:
  - `date ASC`
  - `limitTime ASC`

Lưu ý:

- Backend cũ chỉ check role qua query string, không có auth thật

### 4. Danh sách users

Route:

```txt
GET /users-list
```

Logic:

- Trả về toàn bộ users
- Loại bỏ password

### 5. Notification incomplete/abnormal

Route:

```txt
GET /notifications/incomplete?userId=...&date=...
```

Logic:

- Bắt buộc có `userId` và `date`
- Lấy tất cả `dailyChecks` theo user và ngày
- Tách ra 2 nhóm:
  - `incomplete`: status = `x`
  - `abnormal`: status = `△`
- Join thủ công với `abnormalNotes` để gắn note cho nhóm abnormal

### 6. Generate checklist theo category

Route:

```txt
POST /generate-daily-checks
```

Body:

```json
{
  "userId": 2,
  "date": "2026-05-11"
}
```

Logic:

- Lấy toàn bộ `categories`
- Kiểm tra user/ngày đó đã có checklist chưa
- Nếu đã có thì reject
- Nếu chưa có thì tạo 1 `dailyCheck` cho mỗi category
- `status` mặc định là `x`

### 7. Daily confirmation

Route:

```txt
GET /daily-confirmations?userId=...&date=...
```

Logic:

- Tìm xác nhận theo `userId` + `date`
- Trả về 1 bản ghi hoặc `null`

## Dữ liệu trong `db.json`

Các collection chính:

- `users`
- `categories`
- `dailyChecks`
- `abnormalNotes`
- `dailyConfirmations`

### 1. users

Role hiện có:

- `admin`
- `user`
- `manager`

### 2. categories

Là master data của checklist.

Field thực tế:

- `id`
- `symbol`
- `category`
- `limitTime`

### 3. dailyChecks

Là checklist sinh ra theo từng user và từng ngày.

Field thực tế:

- `id`
- `userId`
- `categoryId`
- `symbol`
- `category`
- `date`
- `status`
- `limitTime`

Status:

- `o`: hoàn thành
- `x`: chưa hoàn thành
- `△`: bất thường

### 4. abnormalNotes

Note cho các checklist bị bất thường.

Field:

- `id`
- `userId`
- `dailyCheckId`
- `symbol`
- `category`
- `note`

### 5. dailyConfirmations

Xác nhận checklist theo user/ngày.

Field:

- `id`
- `userId`
- `date`
- `confirmedBy`
- `confirmedByName`
- `confirmedAt`
- `signatureNote`

## Frontend hiện tại đang làm gì

### 1. AuthProvider

File: `daily-check-app/frontend/src/context/AuthProvider.js`

Logic:

- Login gọi `POST /login`
- User data lưu vào `localStorage`
- `logout()` chỉ xóa `localStorage`
- Không có refresh token
- Không có session server

### 2. LoginPage

File: `daily-check-app/frontend/src/pages/LoginPage.js`

Logic:

- Form username/password
- Submit thì gọi `login()`
- Thành công thì điều hướng `/dashboard`
- Có tài khoản demo hardcoded hiển thị ở UI

### 3. DashboardPage

File: `daily-check-app/frontend/src/pages/DashboardPage.js`

Logic:

- Nếu `user.role === "admin"` thì render `AdminPage`
- Còn lại render `UserPage`

Lưu ý:

- Bản cũ này thực ra chưa tách UI riêng cho manager
- Manager hiện rơi vào luồng giống user

### 4. AdminPage

File: `daily-check-app/frontend/src/pages/AdminPage.js`

Admin có thể:

- Xem toàn bộ checklist
- Lọc theo:
  - ngày
  - status
  - user
  - text search
- Update status checklist
- Xóa checklist
- Thêm checklist mới thủ công

Điểm cần nhớ:

- `ITEMS_PER_PAGE = 10`
- Bản cũ chưa đúng yêu cầu mới là `15`
- Admin page fetch:
  - `/admin/checks?role=admin`
  - `/users-list`
  - `/categories`

### 5. UserPage

File: `daily-check-app/frontend/src/pages/UserPage.js`

User hiện có thể:

- Xem checklist của chính mình
- Lọc theo ngày, status, keyword
- Update status checklist
- Xóa checklist
- Thêm checklist mới thủ công

Điểm quan trọng:

- Logic hiện tại trong code cũ cho phép user add/delete check
- Điều này lệch với yêu cầu nghiệp vụ mới
- Yêu cầu mới đúng là:
  - user chỉ xem checklist của mình
  - user chỉ đổi status
  - không quản lý category
  - không nên add/delete checklist thủ công

### 6. CheckTable

File: `daily-check-app/frontend/src/components/CheckTable.js`

Hiển thị bảng checklist.

Props chính:

- `checks`
- `onUpdateStatus`
- `onDelete`
- `showUser`
- `users`
- `nearestId`
- `isAdmin`

Logic nổi bật:

- Nếu `check.id === nearestId` thì highlight row
- Có 3 nút status:
  - `o`
  - `x`
  - `△`
- Nếu là admin thì có thêm nút xóa

### 7. StatusBadge

File: `daily-check-app/frontend/src/components/StatusBadge.js`

Mapping:

- `o` -> completed -> green
- `x` -> incomplete -> secondary
- `△` -> abnormal -> warning

### 8. NavbarCustom

File: `daily-check-app/frontend/src/components/NavbarCustom.js`

Hiển thị:

- Tên user
- Role
- Nút print
- Nút notification
- Nút logout

### 9. Helper functions

File: `daily-check-app/frontend/src/utils/helpers.js`

Các helper quan trọng:

- `getToday()`
- `getMinutesFromTime(time)`
- `getCurrentMinutes()`
- `findNearestChecklist(checklists)`
- `sortByDateAndLimitTime(checks)`
- `paginateData(data, currentPage, itemsPerPage)`
- `formatDateTime(isoString)`

Đây là nơi thể hiện rõ logic:

- sort theo `date` và `limitTime`
- tìm checklist gần giờ hiện tại

## Tình trạng logic business hiện tại

### Những gì đúng với nghiệp vụ

- Có login/logout
- Có role `admin/user/manager`
- Admin xem được toàn bộ checklist
- User xem checklist của mình
- Sort theo ngày và giờ
- Có generate checklist từ category
- Có abnormal note
- Có daily confirmation

### Những gì còn lệch hoặc chưa hoàn chỉnh

- Manager chưa có luồng UI riêng rõ ràng
- Auth chưa an toàn
- User page đang cho add/delete checklist
- Pagination đang là 10 thay vì 15
- Notification, print, confirm chưa tích hợp đầy đủ thành flow UI hoàn chỉnh trong phần React đã đọc
- Backend check role bằng query string, không phải auth thật

## Những điểm AI khác cần biết nếu tiếp tục sửa bản React/Node

Nếu AI tiếp theo tiếp tục làm trên project `daily-check-app`, cần hiểu:

### 1. Đây là app demo/mock data

- Không có auth production-ready
- Không có database thật
- `json-server` vừa là mock DB vừa là REST CRUD

### 2. Nguồn logic chuẩn nhất nằm ở đâu

- Backend flow: `daily-check-app/backend/server.js`
- Dữ liệu nghiệp vụ mẫu: `daily-check-app/backend/db.json`
- UI role/admin-user: `daily-check-app/frontend/src/pages/AdminPage.js`, `UserPage.js`
- Logic nearest/sort: `daily-check-app/frontend/src/utils/helpers.js`

### 3. Nếu cần nâng cấp bản cũ

Các việc thường sẽ là:

- chặn user add/delete checklist
- thêm manager page rõ ràng
- đồng bộ notification + print + confirmation
- đổi pagination thành 15
- làm auth thực sự

## Prompt gợi ý để ném cho AI khác

```txt
Đọc file REACT_NODE_HANDOFF.md trước, sau đó làm việc trên thư mục daily-check-app.
Không thay đổi thư mục python.
Hãy giữ nguyên stack ReactJS + NodeJS + json-server hiện tại.
Mục tiêu là chỉnh lại logic business cho đúng:
- user chỉ được đổi status checklist của chính mình
- manager xem checklist user và ký xác nhận
- admin quản lý category, generate checklist và xem toàn bộ
- pagination 15 mục
- notification modal và print checklist hoàn chỉnh
Hãy đọc code thật trong daily-check-app rồi sửa code trực tiếp, không viết pseudo code.
```
