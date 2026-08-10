import hashlib
import sqlite3
import os

# Đường dẫn tới DB
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def update_all_passwords_to_sha256(default_password="123456"):
    if not os.path.exists(DB_PATH):
        print(f"❌ Không tìm thấy file database tại {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tính hash SHA-256 chuẩn cho mật khẩu mặc định "123456"
    new_hash = hash_password(default_password)
    print(f"🔑 Chuỗi Hash SHA-256 chuẩn của '{default_password}':\n👉 {new_hash}\n")

    # Cập nhật tất cả tài khoản trong bảng users về Hash SHA-256 mới
    cursor.execute("UPDATE users SET password_hash = ?", (new_hash,))
    conn.commit()
    
    updated_rows = cursor.rowcount
    conn.close()

    print(f"✅ Đã cập nhật thành công {updated_rows} tài khoản!")
    print(f"👉 Bây giờ BẤT KỲ TÀI KHOẢN NÀO (bao gồm 'admin1') đều có mật khẩu đăng nhập là: {default_password}")

if __name__ == "__main__":
    update_all_passwords_to_sha256("123456")