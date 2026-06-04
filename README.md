# Tokyo Metro Predictor

Ứng dụng tìm đường tàu điện Tokyo bằng bản đồ web. Người dùng có thể đăng ký, đăng nhập, chọn ga đi/ga đến hoặc chọn vị trí trên bản đồ, sau đó hệ thống sẽ gợi ý tuyến đường, khoảng cách, giá vé và số lần đổi tàu.

Repo GitHub: https://github.com/nguyenquanganh102006-beep/tokyo_metro_predictor

## 1. Cần cài gì trước?

Bạn cần cài 3 thứ:

1. Python 3.11
   Tải tại https://www.python.org/downloads/

2. PostgreSQL
   Tải tại https://www.postgresql.org/download/windows/

3. PostGIS
   Khi cài PostgreSQL trên Windows, mở thêm **Stack Builder** và cài **PostGIS** cho đúng phiên bản PostgreSQL đang dùng.

Nếu dùng Windows, khi cài Python nhớ tick ô **Add python.exe to PATH**.

## 2. Tải project về máy

Mở Terminal, PowerShell hoặc CMD rồi chạy:

```bash
git clone https://github.com/nguyenquanganh102006-beep/tokyo_metro_predictor.git
cd tokyo_metro_predictor
```

Nếu bạn đã có sẵn thư mục project thì chỉ cần mở terminal tại thư mục đó.

## 3. Tạo môi trường Python

 1.Tạo môi trường mới với Python 3.11: 
 conda create -n tokyo_subway python=3.11 -y
 2. Kích hoạt môi trường: 
 conda activate tokyo_subway

## 4. Cài thư viện Python

Chạy:

```bash
pip install -r requirements.txt
```

## 5. Tạo database PostgreSQL

Mở **pgAdmin** hoặc **SQL Shell (psql)**.

Tạo database tên:

```text
tokyo_subway
```

Nếu dùng SQL Shell, có thể chạy:

```sql
CREATE DATABASE tokyo_subway;
```

Sau đó kết nối vào database `tokyo_subway` và bật PostGIS:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

## 6. Import file data

File data nằm ở:

```text
data/219_tokyo_station
```

Đây là file dump PostgreSQL dạng custom, nên cần import bằng `pg_restore`.

Ví dụ trên Windows, đứng trong thư mục project và chạy:

```bash
pg_restore -U postgres -d tokyo_subway -v data\219_tokyo_station
```

Ví dụ trên macOS/Linux:

```bash
pg_restore -U postgres -d tokyo_subway -v data/219_tokyo_station
```

Nếu terminal hỏi password, nhập password PostgreSQL bạn đặt lúc cài PostgreSQL.

Nếu báo lỗi `pg_restore is not recognized`, nghĩa là PostgreSQL chưa được thêm vào PATH. Trên Windows, thử dùng đường dẫn đầy đủ, ví dụ:

```bash
"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -U postgres -d tokyo_subway -v data\219_tokyo_station
```

Thay `18` bằng phiên bản PostgreSQL bạn đang cài, ví dụ `16`, `17` hoặc `18`.

## 7. Tạo file cấu hình `.env`

Trong thư mục project, tạo file tên:

```text
.env
```

Bạn có thể copy từ file mẫu `.env.example`, rồi sửa lại password PostgreSQL.

Nội dung mẫu:

```env
DATABASE_URL=postgresql://postgres:1234@localhost:5432/tokyo_subway
SECRET_KEY=change-this-to-a-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

Sửa `1234` trong `DATABASE_URL` thành password PostgreSQL của bạn.

Ví dụ nếu password PostgreSQL là `mypassword`, dùng:

```env
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/tokyo_subway
```

## 9. Chạy backend

Mở terminal thứ nhất, đứng trong thư mục project, kích hoạt môi trường `.venv`, rồi chạy:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend sẽ chạy tại:

```text
http://127.0.0.1:8000
```

Trang kiểm tra API:

```text
http://127.0.0.1:8000/docs
```

Nếu mở `http://127.0.0.1:8000` thấy message API đang chạy là được.

## 10. Chạy frontend

Mở terminal thứ hai, vẫn đứng trong thư mục project, kích hoạt `.venv`, rồi chạy:

```bash
streamlit run frontend.py
```

Frontend sẽ mở ở:

```text
http://localhost:8501
```

Cách dùng cơ bản:

1. Đăng ký tài khoản mới.
2. Đăng nhập.
3. Chọn ga đi và ga đến.
4. Chọn ưu tiên tìm đường.
5. Bấm tìm đường để xem kết quả trên bản đồ.

## 11. Tạo tài khoản admin

Trước tiên hãy đăng ký tài khoản trong giao diện web. Ví dụ username là:

```text
quanganh
```

Sau đó chạy:

```bash
python set_admin.py quanganh
```

Thay `quanganh` bằng username bạn muốn nâng lên admin.

Đăng xuất rồi đăng nhập lại trên giao diện web. Nếu thành công, tài khoản sẽ có quyền admin.

Admin có thể khóa/mở:

- Ga
- Tuyến tàu
- Đoạn đường giữa hai ga


### Xem danh sách line hiện có

Chạy SQL:

```sql
SELECT line_id, line_name, color
FROM line
ORDER BY line_id;
```

Kết quả sẽ cho bạn biết mỗi tuyến có `line_id` nào.

## 13. Các bảng database chính

Project dùng các bảng chính:

```text
line
```

Lưu thông tin tuyến tàu:

```text
line_id, line_name, color, is_active
```

```text
stations
```

Lưu thông tin ga:

```text
station_id, station_name, line_id, lat, lon, geom, is_active
```

```text
edges
```

Lưu đoạn đường giữa hai ga:

```text
edge_id, source_id, target_id, distance_km, time_min, fare_yen, is_transfer, is_active
```

```text
users
```

Lưu tài khoản:

```text
username, password, role, is_active, created_at
```

## 14. Lỗi thường gặp

### Backend báo không kết nối được database

Kiểm tra lại file `.env`, đặc biệt là:

```env
DATABASE_URL=postgresql://postgres:password_cua_ban@localhost:5432/tokyo_subway
```

Đảm bảo:

- PostgreSQL đang chạy.
- Database tên đúng là `tokyo_subway`.
- Password PostgreSQL đúng.

### Lỗi thiếu bảng hoặc thiếu cột `is_active`

Chạy lại bước 7:

```sql
ALTER TABLE line
ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;

ALTER TABLE stations
ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;

ALTER TABLE edges
ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;
```

### Lỗi thiếu thư viện Streamlit hoặc Folium

Chạy:

```bash
pip install -r requirements.txt
```

### Frontend không gọi được backend

Kiểm tra backend có đang chạy ở:

```text
http://127.0.0.1:8000
```

Trong `frontend.py`, biến API đang là:

```python
API_BASE = "http://127.0.0.1:8000/api"
```

Nếu bạn chạy backend ở port khác, cần sửa lại dòng này.

### Lỗi PostGIS khi import data

Nếu restore báo lỗi liên quan `postgis` hoặc `geometry`, hãy cài PostGIS bằng Stack Builder rồi chạy trong database:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

Sau đó import lại file data.

## 15. Lệnh chạy nhanh

Terminal 1:

```bash
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
.venv\Scripts\activate
streamlit run frontend.py
```

Mở trình duyệt:

```text
http://localhost:8501
```
