# edu_app/auth/auth_service.py
import bcrypt
import sys
import os
import hashlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.db_connection import get_connection

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

#def hash_password(password):
#    """Băm mật khẩu bằng thuật toán SHA-256"""
#    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def register_user(username: str, password: str, full_name: str, email: str = "", role: str = "student"):
    username = username.strip().lower()
    if not username or not password or not full_name:
        return False, "Vui lòng điền đầy đủ các thông tin bắt buộc."
    
    if len(password) < 6:
        return False, "Mật khẩu phải chứa ít nhất 6 ký tự."

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "Tên đăng nhập đã tồn tại trên hệ thống."

    pwd_hash = hash_password(password)
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, email, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, pwd_hash, full_name.strip(), email.strip(), role))
        conn.commit()
        conn.close()
        return True, "Đăng ký tài khoản thành công! Bạn có thể đăng nhập ngay."
    except Exception as e:
        conn.close()
        return False, f"Lỗi hệ thống: {str(e)}"

def login_user(username, password):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            # Mã hóa mật khẩu người dùng vừa nhập ở giao diện
            #input_pwd_hash = hash_password(password)
            #db_pwd_hash = user['password_hash']

            # ----------------------------------------------------
            # IN THÔNG TIN DEBUG OUT CONSOLE (TERMINAL)
            # ----------------------------------------------------
            #print("\n=== 🔍 DEBUG ĐĂNG NHẬP ===")
            #print(f"1. Username nhập vào   : {username}")
            #print(f"2. Mật khẩu thô nhập vào: {password}")
            #print(f"3. SHA-256 tính từ nhập: {input_pwd_hash}")
            #print(f"4. SHA-256 trong DB     : {db_pwd_hash}")
            #print(f"5. Khớp mật khẩu không? : {input_pwd_hash == db_pwd_hash}")
            #print("===========================\n")
            # ----------------------------------------------------
                    
            if user['is_active'] == 0:
                return None, "🔒 Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Admin!"
            if user['password_hash'] == hash_password(password):
                return dict(user), "Đăng nhập thành công!"
        return None, "Tên đăng nhập hoặc mật khẩu không chính xác!"
    except Exception as e:
        return None, f"Lỗi hệ thống: {str(e)}"
    finally:
        if conn:
            conn.close() # Đảm bảo luôn luôn giải phóng kết nối DB

def reset_password(user_id, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
    return True, "Đặt lại mật khẩu thành công!"

def toggle_user_status(user_id, current_status):
    new_status = 0 if current_status == 1 else 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return True, "Cập nhật trạng thái tài khoản thành công!"

def save_essay_submission(user_id: int, question_id: int, student_solution: str, self_score: float, self_eval_notes: str):
    """Lưu bài làm tự luận và kết quả tự đánh giá của học sinh"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO student_essay_submissions (user_id, question_id, student_solution, self_score, self_eval_notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, question_id, student_solution, self_score, self_eval_notes))
        conn.commit()
        conn.close()
        return True, "Lưu kết quả tự đánh giá thành công!"
    except Exception as e:
        conn.close()
        return False, f"Lỗi khi lưu bài làm: {str(e)}"