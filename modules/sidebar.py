import streamlit as st
import re
from services.db_connection import get_connection

def get_user_role_permissions(user_id):
    """Lấy thông tin phân quyền trong bảng roles"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM roles WHERE user_id = ?", (user_id,))
    role_data = cursor.fetchone()
    conn.close()
    return role_data

def parse_allowed_ids(allowed_str):
    """Hàm phụ trợ: Chuyển chuỗi '1,2,3' hoặc '*' thành danh sách các ID"""
    if not allowed_str:
        return []
    return [x.strip() for x in allowed_str.split(',')]

def get_user_role(user_id):
    """Lấy thông tin phân quyền từ bảng roles cho học sinh"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM roles WHERE user_id = ? AND role_type = 'student'", (user_id,))
    role = cursor.fetchone()
    conn.close()
    return role

def render_student_sidebar(user_id):
    st.sidebar.title(f"👤 {st.session_state.user['full_name']}")
    st.sidebar.caption(f"Vai trò: **{st.session_state.user['role'].upper()}**")
    
    if st.sidebar.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.user = None
        st.rerun()

    st.sidebar.divider()

    """Lọc Sidebar dựa trên quyền hạn của học sinh trong bảng roles"""
    st.sidebar.title("📚 Danh Mục Học Tập")
    
    role = get_user_role(user_id)
    if not role:
        st.sidebar.error("⚠️ Tài khoản chưa được cấp quyền học tập. Vui lòng liên hệ Admin.")
        return None

    allowed_grades = parse_allowed_ids(role['allowed_grades'])
    allowed_subjects = parse_allowed_ids(role['allowed_subjects'])
    allowed_semesters = parse_allowed_ids(role['allowed_semesters'])

    conn = get_connection()
    cursor = conn.cursor()

    # 1. Lọc Khối Lớp
    cursor.execute("SELECT * FROM grades")
    all_grades = cursor.fetchall()
    if "*" not in allowed_grades:
        filtered_grades = [g for g in all_grades if str(g['id']) in allowed_grades or g.get('code') in allowed_grades]
    else:
        filtered_grades = all_grades

    if not filtered_grades:
        st.sidebar.warning("🔒 Bạn chưa được gán Khối lớp nào.")
        conn.close()
        return None

    sel_grade = st.sidebar.selectbox("Chọn Lớp:", filtered_grades, format_func=lambda x: x['name'])

    # 2. Lọc Môn Học
    cursor.execute("SELECT * FROM subjects")
    all_subjects = cursor.fetchall()
    if "*" not in allowed_subjects:
        filtered_subjects = [s for s in all_subjects if str(s['id']) in allowed_subjects or s.get('code') in allowed_subjects]
    else:
        filtered_subjects = all_subjects

    if not filtered_subjects:
        st.sidebar.warning("🔒 Bạn chưa được gán Môn học nào.")
        conn.close()
        return None

    sel_subject = st.sidebar.selectbox("Chọn Môn:", filtered_subjects, format_func=lambda x: x['name'])

    # 3. Lọc Học Kỳ
    cursor.execute("SELECT id,name FROM semesters")
    all_semesters = cursor.fetchall()
    if "*" not in allowed_semesters:
        filtered_semesters = [se for se in all_semesters if str(se['id']) in allowed_semesters or se.get('code') in allowed_semesters]
    else:
        filtered_semesters = all_semesters

    if not filtered_semesters:
        st.sidebar.warning("🔒 Bạn chưa được gán Học Kỳ nào.")
        conn.close()
        return None

    sel_semester = st.sidebar.selectbox("Chọn Học kỳ:", filtered_semesters, format_func=lambda x: x['name'])

    # 4. Lấy danh sách Bài học khả dụng theo Lớp + Môn + Học kỳ
    cursor.execute("""
        SELECT * FROM lessons 
        WHERE grade_id = ? AND subject_id = ? AND semester_id = ?
    """, (sel_grade['id'], sel_subject['id'], sel_semester['id']))
    lessons = cursor.fetchall()
    
    sel_lesson = None
    if lessons:
        sel_lesson = st.sidebar.selectbox("Chọn Bài học:", lessons, format_func=lambda x: f"{x['chapter_name']} - {x['title']}")
    else:
        st.sidebar.info("📌 Chưa có bài học nào.")

    conn.close()

    return {
        "grade": sel_grade,
        "subject": sel_subject,
        "semester": sel_semester,
        "lessons": lessons,
        "lesson": sel_lesson
    }