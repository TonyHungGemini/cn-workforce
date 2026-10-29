# Triển khai CN Workforce lên máy chủ công ty

Mục tiêu: sếp và nhân viên mở **một đường link HTTPS** là xem được dữ liệu, không phụ thuộc máy tính của bạn. GitHub chỉ chứa mã nguồn; **không** chứa dữ liệu thật, ảnh giấy tờ, chân dung hay khoá bí mật.

## 1. Mô hình truy cập

- Một **mã truy cập công ty** dùng chung cho tất cả nhân viên (`CN_ACCESS_CODE`).
- Mỗi người đăng nhập một lần, phiên kéo dài 12 giờ.
- Không có link công khai ẩn danh: 567 hồ sơ thật, số CMND và chân dung không được đặt sau một URL ai cũng mở được.
- GitHub Pages **không** dùng để chạy app này vì là máy chủ tĩnh, không bảo vệ được dữ liệu.

## 2. Chuẩn bị Google Drive

1. Vào Google Cloud Console, tạo project, bật **Google Drive API**.
2. Tạo **Service Account**, vào *Keys* → *Add key* → *JSON*. Tải tệp về máy, **không** đưa lên GitHub.
3. Ghi lại email dạng `ten@project.iam.gserviceaccount.com`.
4. Trong Google Drive, chia sẻ thư mục chứa ảnh CMND/chân dung cho email đó với quyền **Viewer**.
5. Kiểm tra `cn-dsx02-main/data/images.json`: mỗi mã hồ sơ trỏ tới đúng file ID trên Drive. App chỉ đọc theo file ID, không liệt kê hay tải cả thư mục.
6. Trên Render, thêm biến `CN_DRIVE_CREDENTIALS_JSON`, dán **toàn bộ nội dung** tệp JSON ở bước 2 (giữ nguyên các ký tự `\n` trong `private_key`, không thêm dấu nháy bao ngoài). `render.yaml` đã khai báo biến này ở chế độ nhập tay.
7. Kiểm tra khoá trước khi dùng: `python3 scripts/check_drive.py` — in `OK` kèm số byte là đọc được ảnh.

### Tệp sao lưu cơ sở dữ liệu (bắt buộc với gói Free)

Gói Free không có ổ đĩa bền, nên database được sao lưu vào một tệp Drive do **bạn** sở hữu:

1. Tạo thư mục `CN_Workforce_Backup` trong Drive, tải lên một tệp rỗng tên `cn-workforce.sqlite3`.
2. Chia sẻ **chỉ tệp đó** cho email service account với quyền **Editor**.
3. Mở tệp, lấy mã trong URL `https://drive.google.com/file/d/<MÃ_TỆP>/view` và nhập vào `CN_BACKUP_FILE_ID` trên Render.

Service account không có dung lượng lưu trữ riêng, nên tệp phải do bạn tạo trước; app chỉ ghi đè nội dung tệp đó (mỗi 60 giây khi có thay đổi, và khi dịch vụ tắt). Khi máy chủ khởi động lại với ổ đĩa trống, app tự tải bản sao lưu mới nhất trước khi mở dữ liệu.

Không dùng khoá admin/tài khoản cá nhân. Thư mục ảnh vẫn chỉ cấp **Viewer**; quyền **Editor** chỉ áp cho tệp sao lưu.

## 3. Triển khai trên Render

1. Đẩy mã nguồn lên repo GitHub mới **sau khi được duyệt** (không đè repo cũ).
2. Render → *New* → *Blueprint* → chọn repo. Render đọc `render.yaml` và tạo:
   - Web service Docker, gói **Free**, vùng Singapore, health check `/healthz`.
   - Không có ổ đĩa bền: SQLite nằm ở `/data/demo.sqlite3` trong container và được sao lưu lên Drive.
3. Nhập các biến bí mật trong Dashboard:
   - `CN_ACCESS_CODE`: mã công ty, tối thiểu 16 ký tự ngẫu nhiên.
   - `CN_SYNC_TOKEN`: token riêng để đẩy dữ liệu ban đầu, tối thiểu 32 ký tự.
   - `CN_PUBLIC_URL`: URL Render cấp, ví dụ `https://cn-workforce.onrender.com`.
   - `CN_SECRET_KEY`: Render tự sinh.
   - `CN_BACKUP_FILE_ID`: mã tệp `cn-workforce.sqlite3` đã chia sẻ cho service account.
   - `CN_SEED_DEMO=0`: **bắt buộc** để máy chủ không tạo 48 hồ sơ minh họa trước khi nhận dữ liệu thật. Khi có `CN_SYNC_TOKEN`, app cũng tự tắt seed nếu biến này chưa đặt.
4. Deploy. Mở `https://<tên-app>.onrender.com/healthz` phải trả `{"ok":true,...}`.
5. Gói Free ngủ sau khoảng 15 phút không có truy cập; lần mở đầu tiên chậm khoảng 30–60 giây. Dữ liệu vẫn còn vì app khôi phục từ tệp sao lưu trên Drive khi khởi động.

## 4. Đưa dữ liệu thật lần đầu lên máy chủ

Dữ liệu nguồn nằm trên máy bạn, không nằm trong Git. Trên máy bạn:

```bash
cd "cn-workforce"
python3 scripts/import_dsx02.py --force        # kiểm tra cục bộ tại .local/dsx02
CN_SYNC_TOKEN="token-tren-render" \
  python3 scripts/push_snapshot.py --url https://<tên-app>.onrender.com
```

Lệnh này gửi `records.json` + `images.json` qua HTTPS tới `/api/v1/admin/sync`, có xác thực bằng token. Máy chủ tạo hồ sơ, phòng ở, liên kết ảnh Drive, lịch sử và outbox; không trả về tên/CMND.

Sau đó mở app, đăng nhập, kiểm tra:
- Tổng hồ sơ (567), số lao động/gia thuộc.
- Tìm theo tên, mã `CN-xxxx`, CMND, số điện thoại.
- Mở hồ sơ có ảnh: chân dung và ảnh giấy tờ hiển thị để **đối chiếu thủ công**.

Nếu trước đó máy chủ đã seed dữ liệu minh họa (48 hồ sơ), số hồ sơ sẽ thành 615 và không còn sạch. Khi đó xóa `/data/demo.sqlite3` trên ổ đĩa, đặt `CN_SEED_DEMO=0`, khởi động lại rồi đẩy snapshot lại. Không trộn dữ liệu minh họa với dữ liệu thật.

## 5. Đồng bộ về sau

ĐSX02 là nguồn chuẩn. Có ba cách, chọn một:

1. **Đẩy lại từ máy bạn** (đơn giản nhất): chạy lại `push_snapshot.py` sau khi cập nhật ĐSX02. Việc xem của sếp vẫn không phụ thuộc máy bạn; chỉ lần cập nhật mới cần máy bạn.
2. **Máy chủ tự kéo từ ĐSX02** (khuyến nghị khi ĐSX02 đã có URL): đặt `CN_MASTER_URL`, `CN_MASTER_IMAGES_URL` và `CN_MASTER_TOKEN` trên Render. Sau đó gọi endpoint kéo dữ liệu từ một lịch định kỳ:
   ```bash
   curl -X POST https://<tên-app>.onrender.com/api/v1/admin/pull \
     -H "Authorization: Bearer $CN_SYNC_TOKEN"
   ```
   Endpoint chạy trong chính web service nên ghi đúng ổ đĩa `/data`. Có thể dùng Render Cron Job hoặc bất kỳ scheduler nào giữ được token.
3. **Chạy sync ngay trên máy chủ** bằng Render Shell:
   ```bash
   python3 scripts/sync_master.py --source "$CN_MASTER_URL" \
     --images "$CN_MASTER_IMAGES_URL" --data-dir /data
   ```

Không chạy `sync_master.py` trong một Render Cron Job riêng nếu cron đó không gắn cùng ổ đĩa `/data`: nó sẽ ghi vào SQLite tạm và không ảnh hưởng web service.

Quy tắc đồng bộ: ĐSX02 thắng ở các trường hồ sơ; hồ sơ mới được tạo; hồ sơ đã có được cập nhật và tăng `version`; hồ sơ thiếu ở master **không bị xoá** mà chỉ được báo trong `sync-report.json`. Ảnh được cập nhật theo `images.json`.

## 6. Mobile / PWA

- App có manifest, icon, service worker chỉ cache vỏ giao diện (không cache API, không cache ảnh).
- Trên iPhone: Safari → *Chia sẻ* → *Thêm vào Màn hình chính*.
- Trên Android: Chrome → menu → *Cài đặt ứng dụng*.
- Thanh điều hướng dưới màn hình, ảnh lazy-load, trình xem ảnh toàn màn hình.

## 7. Bảo mật và vận hành

- Toàn bộ traffic qua HTTPS của Render; cookie `HttpOnly`, `SameSite=Strict`, `Secure`.
- Host/Origin được giới hạn theo `CN_PUBLIC_URL`; API từ chối cross-site.
- Đăng nhập sai quá 8 lần/10 phút sẽ bị chặn tạm.
- Không ghi mã truy cập, token, tệp service account vào chat, ảnh chụp hay Git.
- Dữ liệu tự sao lưu lên tệp `cn-workforce.sqlite3` trên Drive mỗi ~60 giây khi có thay đổi và khi dịch vụ tắt; muốn bản sao ngoài Drive thì tải tệp đó về máy.
- `image-cache/` chỉ là bộ nhớ đệm ảnh, mất khi khởi động lại và tự tải lại từ Drive — không cần sao lưu.
- Khi nhân viên nghỉ việc: đổi `CN_ACCESS_CODE` để vô hiệu phiên cũ.
- Ảnh giấy tờ là dữ liệu nhạy cảm: chỉ chia sẻ thư mục Drive cho đúng service account; kiểm tra lại quyền mỗi quý.

## 8. Kiểm thử trước khi giao sếp

```bash
python3 -m unittest discover -s tests -v          # Python + HTTP + auth
npm run test:ocr                                  # OCR cục bộ
```

Kiểm tra thủ công trên điện thoại: đăng nhập, tìm một hồ sơ, mở ảnh, khôi phục phiên, đăng xuất, đăng nhập lại.
