import sqlite3
import os

# Tự động xác định đường dẫn tương đối tới file database.db và schema.sql
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "data", "schema.sql")

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def get_connection():
    # Tạo thư mục data nếu chưa tồn tại
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = (dict_factory) # Trả về dict chuẩn Python thay vì sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;') # Tối ưu hóa xử lý ghi đồng thời
    conn.execute('PRAGMA foreign_keys=ON;')  # Bật khóa ngoại
    return conn

def init_db():
    conn = get_connection()
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database connection initialized successfully.")