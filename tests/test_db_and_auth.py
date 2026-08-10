# edu_app/tests/test_db_and_auth.py
import pytest
import sqlite3
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.db_connection import get_connection
from data.seed_data import seed_database
from auth.auth_service import register_user, login_user, save_essay_submission

@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    seed_database()
    yield

def test_essay_question_structure():
    """Kiểm tra ngân hàng câu hỏi chứa đúng định dạng essay và lời giải chi tiết"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions WHERE question_format = 'essay'")
    essay_qs = cursor.fetchall()

    assert len(essay_qs) > 0
    assert essay_qs[0]['essay_solution'] is not None
    conn.close()

def test_save_essay_submission():
    """Kiểm tra tính năng lưu lời giải và điểm tự chấm của học sinh"""
    ok, msg = save_essay_submission(
        user_id=1, 
        question_id=1, 
        student_solution="Lời giải mẫu của học sinh: BC = 10cm", 
        self_score=9.0, 
        self_eval_notes="Tính toán đúng nhưng quên ghi đơn vị ở câu a"
    )
    assert ok is True
    assert "thành công" in msg