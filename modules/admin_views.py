# modules/admin_views.py
import streamlit as st
import json
import sqlite3
import pandas as pd
import io
import os
import re
import tempfile

from services.db_connection import DB_PATH, get_connection
from auth.auth_service import register_user, reset_password, toggle_user_status

from services.github_sync import render_admin_github_backup_ui

#BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#DB_PATH = os.path.join(BASE_DIR, "data", "database.db")
IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

def get_db_backup_bytes(db_path):
    # Tạo một file tạm thời
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_path = tmp_file.name

    # Thực hiện copy an toàn từ DB gốc sang file tạm
    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(tmp_path)
    src_conn.backup(dst_conn)
    
    dst_conn.close()
    src_conn.close()

    # Đọc dữ liệu byte từ file tạm
    with open(tmp_path, "rb") as f:
        data = f.read()

    return data

def check_student_permission(user_role, grade_id, subject_id, semester_id):
    """
    Kiểm tra xem học sinh có quyền xem Lớp, Môn, Học kỳ này không.
    allowed_grades có dạng: "8,9"
    """
    if not user_role:
        return False
        
    allowed_grades = user_role['allowed_grades'].split(',') if user_role['allowed_grades'] else []
    allowed_subjects = user_role['allowed_subjects'].split(',') if user_role['allowed_subjects'] else []
    allowed_semesters = user_role['allowed_semesters'].split(',') if user_role['allowed_semesters'] else []
    
    # Kiểm tra điều kiện
    is_grade_ok = str(grade_id) in allowed_grades or "*" in allowed_grades
    is_subject_ok = str(subject_id) in allowed_subjects or "*" in allowed_subjects
    is_semester_ok = str(semester_id) in allowed_semesters or "*" in allowed_semesters
    
    return is_grade_ok and is_subject_ok and is_semester_ok

def save_uploaded_file(uploaded_file):
    if uploaded_file is not None:
        file_path = os.path.join(IMAGE_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return f"assets/images/{uploaded_file.name}"
    return None

def clean_json_string(json_str):
    #Hàm làm sạch chuỗi JSON chứa công thức LaTeX trước khi parse:
    #Xử lý triệt để tất cả các lệnh LaTeX chứa \x, \u, \b, \t... bị lỗi escape JSON.
    if not json_str:
        return ""

    # 1. Loại bỏ ký tự BOM nếu có
    cleaned = json_str.strip('\ufeff\xef\xbb\xbf')
    
    # 2. Xử lý các escape \u hợp lệ trước:
    # Nếu \u theo sau ĐÚNG 4 ký tự Hex, tạm thời bảo vệ nó
    cleaned = re.sub(r'\\u([0-9a-fA-F]{4})', r'__ESCAPED_UNICODE_\1__', cleaned)
    
    # 3. Nhân đôi tất cả các dấu \ trừ khi nó đứng trước dấu ngoặc đôi "
    # (Vì trong chuỗi JSON, ngoài \" ra thì mọi lệnh LaTeX như \n, \t, \x, \b, \d... đều cần \\)
    cleaned = re.sub(r'\\(?!")', r'\\\\', cleaned)
    
    # 4. Phục hồi lại các chuỗi Unicode \uXXXX hợp lệ ban đầu
    cleaned = re.sub(r'__ESCAPED_UNICODE_([0-9a-fA-F]{4})__', r'\\u\1', cleaned)
    
    return cleaned

def render_admin_dashboard():
    #cursor = conn.cursor()
    st.title("⚙️ Trang Quản Trị Hệ Thống (Admin Dashboard)")

    #1. Kích hoạt tính năng kiểm tra tự động đẩy dữ liệu (Interval Check)
    # check_and_auto_push()

    #2. Bảng điều khiển Bật/Tắt module
    # enable_toggle = st.toggle("Kích hoạt Module Tự Động Sao Lưu", value=st.session_state.enable_auto_backup)
    # st.session_state.enable_auto_backup = enable_toggle

    # if not enable_toggle:
        # st.info("⏸️ Module tự động sao lưu đang TẮT.")
        # return

    #3. Giao diện thông tin & Thao tác thủ công
    # col1, col2 = st.columns(2)
    
    # with col1:
        # st.markdown(f"**Repo:** `{cfg.get('GITHUB_REPO')}`")
        # st.markdown(f"**Chu kỳ sao lưu:** Mỗi `{cfg.get('BACKUP_INTERVAL_HOURS')}` giờ")
        
    # with col2:
        # if st.button("📥 Kéo (Pull) DB Mới Nhất Tải Về"):
            # if st.checkbox("Xác nhận ghi đè dữ liệu Local?"):
                # with st.spinner("Đang tải bản backup mới nhất..."):
                    # if pull_latest_db_from_github():
                        # st.rerun()

        # if st.button("📤 Đẩy (Push) DB Hiện Tại Lên GitHub"):
            # with st.spinner("Đang tải dữ liệu lên..."):
                # push_db_to_github()

    conn = get_connection()
    cursor = conn.cursor()

    tab_users, tab_import, tab_add_lesson, tab_add_q, tab_edit, tab_exam_admin, tab_manage = st.tabs([
        "👥 Quản Lý Người Dùng",
        "📥 Nhập Liệu Hàng Loạt",
        "📖 Thêm Bài Học", 
        "❓ Thêm Câu Hỏi Bài Học", 
        "✏️ Sửa Bài Học / Câu Hỏi",
        "⏱️ Quản Lý Đề Thi Định Kỳ",
        "📊 Thống Kê"
    ])

    # ==========================================
    # TAB 1: QUẢN LÝ NGƯỜI DÙNG
    # ==========================================
    with tab_users:
        st.subheader("👥 Quản Lý Tài Khoản Người Dùng")
        sub_u1, sub_u2, sub_u3,sub_u4 = st.tabs([
            "📋 Danh Sách & Thao Tác", 
            "➕ Tạo Nhanh Tài Khoản Mới", 
            "🔑 Phân Quyền (Roles)",
            "💾 Backup & Restore"
        ])

        with sub_u1:
            # Dùng trực tiếp sqlite3 connect & fetchall tuple để an toàn dữ liệu
            conn = sqlite3.connect(DB_PATH)
            all_users = conn.execute("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id DESC").fetchall()
            conn.close()
            
            if not all_users:
                st.info("Chưa có tài khoản nào.")
            else:
                for u_id, u_name, full_name, role, is_active, created_at in all_users:
                    with st.container(border=True):
                        col_info, col_status, col_reset = st.columns([3, 2, 3])
                        
                        with col_info:
                            status_icon = "🟢" if is_active == 1 else "🔴"
                            st.markdown(f"{status_icon} **{full_name}** (`{u_name}`)")
                            st.caption(f"Vai trò: `{role.upper()}` | ID: {u_id} | Ngày tạo: {created_at}")

                        with col_status:
                            btn_label = "🔒 Khóa" if is_active == 1 else "🔓 Kích hoạt"
                            if st.button(btn_label, key=f"btn_toggle_{u_id}", use_container_width=True):
                                toggle_user_status(u_id, is_active)
                                st.rerun()

                        with col_reset:
                            with st.popover("🔑 Đổi MK"):
                                new_pwd = st.text_input("Mật khẩu mới", key=f"pwd_input_{u_id}", type="password")
                                if st.button("Xác nhận đổi", key=f"btn_reset_{u_id}"):
                                    if new_pwd.strip():
                                        reset_password(u_id, new_pwd)
                                        st.success("Đã đổi MK!")
                                        st.rerun()
                                    else:
                                        st.warning("Không được để trống MK")

        with sub_u2:
            with st.form("form_admin_add_user", clear_on_submit=True):
                st.markdown("##### Tạo tài khoản Học sinh / Admin mới")
                c_u1, c_u2 = st.columns(2)
                with c_u1:
                    new_u_name = st.text_input("Tên đăng nhập:")
                    new_u_pass = st.text_input("Mật khẩu:", type="password")
                with c_u2:
                    new_u_fullname = st.text_input("Họ và tên:")
                    #new_u_role = st.selectbox("Vai trò:", ["student", "admin","Teacher"], format_func=lambda x: "Học sinh" if x == "student" else "Quản trị viên (Admin)" if x == "admin" else "Giáo viên")
                    new_u_role = st.selectbox("Vai trò:", ["student", "teacher", "admin"], format_func=lambda x: "Học sinh" if x == "student" else ("Giáo viên" if x == "teacher" else "Quản trị viên (Admin)")
)

                if st.form_submit_button("➕ Tạo Tài Khoản", use_container_width=True):
                    if not new_u_name or not new_u_pass or not new_u_fullname:
                        st.warning("Vui lòng nhập đầy đủ thông tin.")
                    else:
                        ok, msg = register_user(new_u_name, new_u_pass, new_u_fullname, role=new_u_role)
                        if ok: st.success(msg)
                        else: st.error(msg)


        with sub_u3:
            st.subheader("🔑 Cấu hình Phân Quyền Chi Tiết (Bảng Roles)")
            conn = get_connection()
            cursor = conn.cursor()

            # Lấy danh sách users
            cursor.execute("SELECT id, username, full_name, role FROM users ORDER BY id DESC")
            users = cursor.fetchall()
            user_dict = {f"{u['username']} - {u['full_name']} ({u['role']})": u for u in users}

            selected_user_str = st.selectbox("Chọn tài khoản cần phân quyền:", list(user_dict.keys()))
            
            if selected_user_str:
                selected_user = user_dict[selected_user_str]
                user_id = selected_user['id']
                user_role_type = selected_user['role']

                # Lấy dữ liệu phân quyền hiện tại trong bảng roles (nếu có)
                cursor.execute("SELECT * FROM roles WHERE user_id = ?", (user_id,))
                current_role = cursor.fetchone()

                # Đọc danh sách Lớp, Môn học, Học kỳ
                cursor.execute("SELECT id, name FROM grades")
                all_grades = cursor.fetchall()
                cursor.execute("SELECT id, name FROM subjects")
                all_subjects = cursor.fetchall()
                cursor.execute("SELECT id, name FROM semesters")
                all_semesters = cursor.fetchall()

                # SỬA/THÊM: Khởi tạo dictionary Lớp, Môn, Học kỳ ở NGOÀI ĐÂY để dùng chung cho cả Student và Teacher
                grade_options = {str(g['id']): g['name'] for g in all_grades}
                subj_options = {str(s['id']): s['name'] for s in all_subjects}
                sem_options = {str(se['id']): se['name'] for se in all_semesters}
                
                admin_tab_options = {
                    "tab_users": "👥 Quản Lý Người Dùng",
                    "tab_import": "📥 Nhập Liệu Hàng Loạt",
                    "tab_add_lesson": "📖 Thêm Bài Học",
                    "tab_add_q": "❓ Thêm Câu Hỏi Bài Học",
                    "tab_edit": "✏️ Sửa Bài Học / Câu Hỏi",
                    "tab_exam_admin": "⏱️ Quản Lý Đề Thi Định Kỳ",
                    "tab_manage": "📊 Thống Kê"
                }

                # Lấy giá trị cũ
                init_grades = current_role['allowed_grades'].split(',') if current_role and current_role['allowed_grades'] else []
                init_subjects = current_role['allowed_subjects'].split(',') if current_role and current_role['allowed_subjects'] else []
                init_semesters = current_role['allowed_semesters'].split(',') if current_role and current_role['allowed_semesters'] else []
                init_tabs = current_role['allowed_tabs'].split(',') if current_role and current_role['allowed_tabs'] else []

                with st.form(key=f"form_role_{user_id}"):
                    st.info(f"Đang phân quyền cho: **{selected_user['full_name']}** (Loại tài khoản gốc: `{user_role_type}`)")

                    if user_role_type == 'student':
                        st.markdown("### 🎓 Phân Quyền Truy Cập Cho Học Sinh")
                        
                        sel_grades = st.multiselect(
                            "Khối lớp được phép truy cập:",
                            options=list(grade_options.keys()),
                            default=[g for g in init_grades if g in grade_options],
                            format_func=lambda x: grade_options[x]
                        )

                        sel_subjects = st.multiselect(
                            "Môn học được phép truy cập:",
                            options=list(subj_options.keys()),
                            default=[s for s in init_subjects if s in subj_options],
                            format_func=lambda x: subj_options[x]
                        )

                        sel_semesters = st.multiselect(
                            "Học kỳ được phép truy cập:",
                            options=list(sem_options.keys()),
                            default=[s for s in init_semesters if s in sem_options],
                            format_func=lambda x: sem_options[x]
                        )

                        sel_tabs_str = "*"

                    elif user_role_type == 'teacher':
                        st.markdown("### 👩‍🏫 Phân Quyền Cho Giáo Viên")
                        
                        sel_grades = st.multiselect(
                            "Khối lớp phụ trách:",
                            options=list(grade_options.keys()),
                            default=[g for g in init_grades if g in grade_options],
                            format_func=lambda x: grade_options[x]
                        )

                        sel_subjects = st.multiselect(
                            "Môn học phụ trách:",
                            options=list(subj_options.keys()),
                            default=[s for s in init_subjects if s in subj_options],
                            format_func=lambda x: subj_options[x]
                        )

                        sel_semesters = st.multiselect(
                            "Học kỳ phụ trách:",
                            options=list(sem_options.keys()),
                            default=[s for s in init_semesters if s in sem_options],
                            format_func=lambda x: sem_options[x]
                        )

                        sel_tabs = st.multiselect(
                            "Các Tab Admin được phép thao tác:",
                            options=list(admin_tab_options.keys()),
                            default=[t for t in init_tabs if t in admin_tab_options],
                            format_func=lambda x: admin_tab_options[x]
                        )

                    else:  # Admin
                        st.markdown("### 🛠️ Phân Quyền Thao Tác Chức Năng Admin")

                        sel_tabs = st.multiselect(
                            "Các Tab chức năng Admin được phép sử dụng:",
                            options=list(admin_tab_options.keys()),
                            default=[t for t in init_tabs if t in admin_tab_options],
                            format_func=lambda x: admin_tab_options[x]
                        )
                        
                        sel_grades_str = "*"
                        sel_subjects_str = "*"
                        sel_semesters_str = "*"

                    btn_save_role = st.form_submit_button("💾 Lưu Quyền Hạn", use_container_width=True)

                    if btn_save_role:
                        if user_role_type == 'student':
                            sel_grades_str = ",".join(sel_grades)
                            sel_subjects_str = ",".join(sel_subjects)
                            sel_semesters_str = ",".join(sel_semesters)
                        elif user_role_type == 'teacher':
                            sel_grades_str = ",".join(sel_grades)
                            sel_subjects_str = ",".join(sel_subjects)
                            sel_semesters_str = ",".join(sel_semesters)
                            sel_tabs_str = ",".join(sel_tabs)
                        else:  # Admin
                            sel_tabs_str = ",".join(sel_tabs)

                        if current_role:
                            cursor.execute("""
                                UPDATE roles 
                                SET allowed_grades = ?, allowed_subjects = ?, allowed_semesters = ?, allowed_tabs = ?
                                WHERE user_id = ?
                            """, (sel_grades_str, sel_subjects_str, sel_semesters_str, sel_tabs_str, user_id))
                        else:
                            cursor.execute("""
                                INSERT INTO roles (user_id, role_type, allowed_grades, allowed_subjects, allowed_semesters, allowed_tabs)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (user_id, user_role_type, sel_grades_str, sel_subjects_str, sel_semesters_str, sel_tabs_str))

                        conn.commit()
                        st.success("🎉 Đã cập nhật quyền hạn thành công vào bảng `roles`!")
                        st.rerun()
        
            conn.close()
        with sub_u4:
            st.subheader("💾 Backup & Restore")
            sub_u4_1, sub_u4_2, sub_u4_3, sub_u4_4 = st.tabs([
            "💾 Backup file Database", 
            "⬇️ Backup SQLite API", 
            "🔄 Restore Database",
            "🔄 Auto"
        ])
            with sub_u4_1:
                
                with open(DB_PATH, "rb") as fp:
                    st.download_button(
                        label="📦 Tải bản Backup Database (.db)",
                        data=fp,
                        file_name="backup_database.db",
                        mime="application/x-sqlite3"
                    )
                
            with sub_u4_2:
                
                db_bytes = get_db_backup_bytes(DB_PATH)
                st.download_button(
                    label="⬇️ Tải file Database (.db)",
                    data=db_bytes,
                    file_name="backup_system.db",
                    mime="application/x-sqlite3"
                )
                
            with sub_u4_3:            
                
                uploaded_file = st.file_uploader("Tải lên file backup (.db)", type=["db", "sqlite", "sqlite3"])

                if uploaded_file is not None:
                    if st.button("⚠️ Xác nhận khôi phục (Sẽ ghi đè dữ liệu)"):
                        # Ghi đè file upload vào file database chính của ứng dụng
                        with open("database.db", "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.success("Khôi phục thành công! Vui lòng tải lại trang.")
            
            with sub_u4_4:
                render_admin_github_backup_ui()
                
    # ==========================================
    # TAB 2: NHẬP LIỆU HÀNG LOẠT (JSON & EXCEL)
    # ==========================================
    with tab_import:
        st.subheader("📥 Nhập Liệu Hàng Loạt Từ JSON hoặc Excel/CSV")
        import_type = st.radio("Chọn định dạng nguồn dữ liệu:", ["📄 Import từ JSON (4 Prompts AI)", "📊 Import từ Excel / CSV"], horizontal=True)

        conn = get_connection()
        cursor = conn.cursor()

        if import_type == "📄 Import từ JSON (4 Prompts AI)":
            json_category = st.selectbox("Chọn loại dữ liệu JSON:", [
                "1. Bài học Lý thuyết", 
                "2. Câu hỏi Bài học (Luyện tập)", 
                "3. Đề thi Định kỳ (Exam)", 
                "4. Tài liệu & Video bổ trợ (Resources)"
            ])

            # -------------------------------------------------------------
            # BỔ SUNG: Cho phép Admin chọn Lớp, Môn, Học kỳ trực tiếp từ UI
            # -------------------------------------------------------------
            target_les_id = None

            if "Bài học Lý thuyết" in json_category or "3. Đề thi Định kỳ (Exam)" in json_category:
                
                st.markdown("##### 🎯 Chọn mục tiêu lưu dữ liệu:")
                col_g, col_s, col_sem = st.columns(3)
                
                cursor.execute("SELECT id, name FROM grades")
                list_grades = cursor.fetchall()
                cursor.execute("SELECT id, name FROM subjects")
                list_subjects = cursor.fetchall()
                cursor.execute("SELECT id, name FROM semesters")
                list_semesters = cursor.fetchall()

                with col_g:
                    target_grade = st.selectbox("Chọn Lớp:", list_grades, format_func=lambda x: x['name'], key="imp_g")
                with col_s:
                    target_subject = st.selectbox("Chọn Môn học:", list_subjects, format_func=lambda x: x['name'], key="imp_s")
                with col_sem:
                    target_semester = st.selectbox("Chọn Học kỳ:", list_semesters, format_func=lambda x: x['name'], key="imp_sem")

            if "2. Câu hỏi Bài học (Luyện tập)" in json_category or "4. Tài liệu & Video bổ trợ (Resources)" in json_category:
                cursor.execute("SELECT id, chapter_name, title FROM lessons ORDER BY id DESC")
                all_lessons = cursor.fetchall()
                
                if not all_lessons:
                    st.warning("⚠️ Chưa có bài học nào trong hệ thống! Vui lòng thêm/import bài học lý thuyết trước.")
                else:
                    selected_lesson = st.selectbox(
                        "🎯 Chọn Bài học cần gắn dữ liệu này vào:", 
                        all_lessons, 
                        format_func=lambda x: f"[{x['id']}] {x['chapter_name']} - {x['title']}"
                    )
                    target_les_id = selected_lesson['id'] if selected_lesson else None
            
            if "3. Đề thi Định kỳ (Exam)" in json_category:
                cursor.execute("SELECT * FROM exams WHERE grade_id = ? AND subject_id = ? AND semester_id = ? ORDER BY title ASC", (target_grade['id'], target_subject['id'], target_semester['id']))
                matched_exams_ = cursor.fetchall()

                if not matched_exams_:
                    st.info("Chưa có đề thi nào trong phân loại này. Bạn nên thêm trong mục \"Quản Lý Đề Thi Định Kỳ\" > \"Tạo Đề Thi Mới\"")
                else:
                    sel_edit_exam_ = st.selectbox("Chọn Đề Thi:", matched_exams_, format_func=lambda x: x['title'])

            json_input = st.text_area("Dán chuỗi JSON thu được từ AI vào đây:", height=220)
            
            if st.button("🚀 Kiểm Tra & Nạp Dữ Liệu JSON", use_container_width=True):
                if not json_input.strip():
                    st.warning("Vui lòng dán dữ liệu JSON.")
                elif ("2. Câu hỏi Bài học (Luyện tập)" in json_category or "4. Tài liệu & Video bổ trợ (Resources)" in json_category) and not target_les_id:
                    st.error("Vui lòng chọn bài học cần gắn dữ liệu.")
                else:
                    try:
                        # Tự động sửa lỗi escape xuyệt ngược (\) của LaTeX
                        #cleaned_json = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', json_input)
                        #data = json.loads(cleaned_json)
                        # Làm sạch chuỗi trước khi parse
                        cleaned_input = clean_json_string(json_input)
                        data = json.loads(cleaned_input)
                        
                        # 1. Nạp Bài học Lý thuyết (Dùng Lớp/Môn/Học kỳ chọn từ UI)
                        if "1. Bài học Lý thuyết" in json_category:
                            cursor.execute('''
                                INSERT INTO lessons (grade_id, subject_id, semester_id, chapter_name, title, summary, content_markdown)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                target_grade['id'], 
                                target_subject['id'], 
                                target_semester['id'], 
                                data['chapter_name'], 
                                data['title'], 
                                data['summary'], 
                                data['content_markdown']
                            ))
                            conn.commit()
                            st.success(f"🎉 Đã nhập thành công Bài học: '{data['title']}' cho {target_grade['name']} - {target_subject['name']}!")

                        # 2. Nạp Câu hỏi Bài học
                        elif "2. Câu hỏi Bài học (Luyện tập)" in json_category:
                            cursor.execute("SELECT id, title FROM lessons ORDER BY id DESC")
                            all_lessons = cursor.fetchall()
                            if not all_lessons:
                                st.error("Chưa có bài học nào trong CSDL. Vui lòng tạo bài học trước!")
                            else:
                                #target_les = st.selectbox("Chọn Bài học để gắn câu hỏi:", all_lessons, format_func=lambda x: x['title'])
                                for q in data:
                                    cursor.execute('''
                                        INSERT INTO questions (lesson_id, question_format, exam_type, question_text, option_a, option_b, option_c, option_d, correct_option, essay_solution, explanation)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (selected_lesson['id'], q['question_format'], q['exam_type'], q['question_text'], q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d'), q.get('correct_option'), q.get('essay_solution'), q.get('explanation')))
                                conn.commit()
                                st.success(f"🎉 Đã nạp thành công {len(data)} câu hỏi!")

                        # 3. Nạp Đề thi Định kỳ (Dùng Lớp/Môn/Học kỳ chọn từ UI)
                        elif "3. Đề thi Định kỳ (Exam)" in json_category:
                            ex_info = data['exam_info']
                            # cursor.execute('''
                                # INSERT INTO exams (title, grade_id, subject_id, semester_id, duration_minutes) 
                                # VALUES (?, ?, ?, ?, ?)
                            # ''', (sel_edit_exam_['title'], target_grade['id'], target_subject['id'], target_semester['id'], ex_info['duration_minutes']))
                            # exam_id = cursor.lastrowid
                            #print(repr(sel_edit_exam_['title']))
                            
                            for q in data['questions']:
                                cursor.execute('''
                                    INSERT INTO exam_questions (exam_id, question_type, question_num, max_score, question_text, option_a, option_b, option_c, option_d, correct_option, essay_solution, explanation)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (sel_edit_exam_['id'], q['question_type'], q['question_num'], q['max_score'], q['question_text'], q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d'), q.get('correct_option'), q.get('essay_solution'), q.get('explanation')))
                            conn.commit()
                            st.success(f"🎉 Đã tạo Đề thi '{sel_edit_exam_['title']}' cho {target_grade['name']} - {target_subject['name']}!")

                        # 4. Nạp Tài liệu & Video bổ trợ
                        elif "4. Tài liệu & Video bổ trợ (Resources)" in json_category:
                            cursor.execute("SELECT id, title FROM lessons ORDER BY id DESC")
                            all_lessons = cursor.fetchall()
                            #target_les_res = st.selectbox("Chọn Bài học đính kèm:", all_lessons, format_func=lambda x: x['title'])
                            for r in data:
                                cursor.execute('''
                                    INSERT INTO resources (lesson_id, resource_type, title, url_or_path, description)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (selected_lesson['id'], r['resource_type'], r['title'], r['url_or_path'], r.get('description')))
                            conn.commit()
                            st.success(f"🎉 Đã thêm thành công {len(data)} tài liệu bổ trợ!")

                    except Exception as e:
                        st.error(f"❌ Lỗi định dạng JSON hoặc dữ liệu không hợp lệ: {e}")

        conn.close()

    # ==========================================
    # TAB 3: THÊM BÀI HỌC
    # ==========================================
    with tab_add_lesson:
        st.subheader("Tạo Bài Học Mới")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM grades"); grades = cursor.fetchall()
        cursor.execute("SELECT id, name FROM subjects"); subjects = cursor.fetchall()
        cursor.execute("SELECT id, name FROM semesters"); semesters = cursor.fetchall()

        with st.form("form_add_lesson", clear_on_submit=True):
            col_g, col_s, col_sem = st.columns(3)
            with col_g: adm_g = st.selectbox("Chọn Lớp:", grades, format_func=lambda x: x['name'])
            with col_s: adm_s = st.selectbox("Chọn Môn:", subjects, format_func=lambda x: x['name'])
            with col_sem: adm_sem = st.selectbox("Chọn Học kỳ:", semesters, format_func=lambda x: x['name'])

            chap_name = st.text_input("Tên Chương:")
            les_title = st.text_input("Tiêu đề bài học:")
            les_summary = st.text_area("Tóm tắt bài học:", height=70)
            les_markdown = st.text_area("Nội dung Lý thuyết (Markdown/LaTeX):", height=180)
            les_img = st.file_uploader("Ảnh minh họa bài học:", type=["png", "jpg", "jpeg"])

            if st.form_submit_button("➕ Lưu Bài Học Mới", use_container_width=True):
                if not chap_name or not les_title or not les_markdown:
                    st.warning("Vui lòng điền đầy đủ Tên chương, Tiêu đề và Nội dung lý thuyết.")
                else:
                    img_path = save_uploaded_file(les_img)
                    cursor.execute('''
                        INSERT INTO lessons (grade_id, subject_id, semester_id, chapter_name, title, content_markdown, summary, image_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (adm_g['id'], adm_s['id'], adm_sem['id'], chap_name, les_title, les_markdown, les_summary, img_path))
                    conn.commit()
                    st.success("🎉 Thêm bài học mới thành công!")

    # ==========================================
    # TAB 4: THÊM CÂU HỎI BÀI HỌC
    # ==========================================
    with tab_add_q:
        st.subheader("Thêm Câu Hỏi Luyện Tập Cho Bài Học")
        cursor.execute("SELECT id, title, chapter_name FROM lessons")
        all_lessons = cursor.fetchall()

        if not all_lessons:
            st.warning("Chưa có bài học nào. Vui lòng tạo bài học trước!")
        else:
            target_lesson = st.selectbox("Chọn bài học gắn câu hỏi:", all_lessons, format_func=lambda x: f"{x['chapter_name']} - {x['title']}", key="sel_les_q")
            q_format = st.selectbox("Định dạng câu hỏi:", [("mcq", "Trắc nghiệm (MCQ)"), ("essay", "Tự luận (ESSAY)")], format_func=lambda x: x[1], key="sel_fmt_q")

            with st.form("form_add_question", clear_on_submit=True):
                exam_type = st.selectbox("Phân loại câu hỏi:", [
                    ("theory", "💡 Củng cố Lý thuyết"), 
                    ("regular", "✍️ Bài tập Rèn luyện")
                ], format_func=lambda x: x[1])

                q_text = st.text_area("Nội dung đề bài (Hỗ trợ LaTeX $...$):", height=100)
                q_img = st.file_uploader("Hình ảnh minh họa đề bài:", type=["png", "jpg", "jpeg"])

                if q_format[0] == 'mcq':
                    c_a, c_b = st.columns(2)
                    with c_a: opt_a = st.text_input("Đáp án A:"); opt_b = st.text_input("Đáp án B:")
                    with c_b: opt_c = st.text_input("Đáp án C:"); opt_d = st.text_input("Đáp án D:")
                    correct_opt = st.selectbox("Đáp án đúng:", ["A", "B", "C", "D"])
                    q_explain = st.text_area("Lời giải chi tiết / Gợi ý:", height=80)
                    essay_sol = None
                else:
                    essay_sol = st.text_area("Đáp án mẫu & Thang điểm chi tiết:", height=150)
                    q_explain = st.text_input("Ghi chú chung:")
                    opt_a = opt_b = opt_c = opt_d = correct_opt = None

                if st.form_submit_button("➕ Lưu Câu Hỏi Vào Bài Học", use_container_width=True):
                    if not q_text.strip():
                        st.warning("Vui lòng nhập nội dung câu hỏi.")
                    else:
                        img_q_path = save_uploaded_file(q_img)
                        cursor.execute('''
                            INSERT INTO questions (
                                lesson_id, question_format, exam_type, question_text, image_path,
                                option_a, option_b, option_c, option_d, correct_option,
                                essay_solution, explanation
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            target_lesson['id'], q_format[0], exam_type[0], q_text, img_q_path,
                            opt_a, opt_b, opt_c, opt_d, correct_opt,
                            essay_sol, q_explain
                        ))
                        conn.commit()
                        st.success("🎉 Thêm câu hỏi thành công!")

    # ==========================================
    # TAB 5: SỬA BÀI HỌC / CÂU HỎI
    # ==========================================
    with tab_edit:
       
        st.subheader("Chỉnh Sửa Dữ Liệu Bài Học / Câu Hỏi")
        sub_edit_type = st.radio("Chọn đối tượng cần sửa:", ["Bài Học", "Câu Hỏi Theo Bài Học"], horizontal=True)

        cursor.execute("SELECT id, name FROM grades"); ed_grades = cursor.fetchall()
        cursor.execute("SELECT id, name FROM subjects"); ed_subjects = cursor.fetchall()
        cursor.execute("SELECT id, name FROM semesters"); ed_semesters = cursor.fetchall()

        c1, c2, c3 = st.columns(3)
        with c1: sel_ed_g = st.selectbox("Lọc Lớp:", ed_grades, format_func=lambda x: x['name'], key="ed_g")
        with c2: sel_ed_s = st.selectbox("Lọc Môn:", ed_subjects, format_func=lambda x: x['name'], key="ed_s")
        with c3: sel_ed_sem = st.selectbox("Lọc Học kỳ:", ed_semesters, format_func=lambda x: x['name'], key="ed_sem")

        if sub_edit_type == "Bài Học":
            cursor.execute('''
                SELECT id, chapter_name, title FROM lessons 
                WHERE grade_id = ? AND subject_id = ? AND semester_id = ?
                ORDER BY id DESC
            ''', (sel_ed_g['id'], sel_ed_s['id'], sel_ed_sem['id']))
            filtered_lessons = cursor.fetchall()

            if not filtered_lessons:
                st.info("Không tìm thấy bài học nào phù hợp.")
            else:
                selected_les_item = st.selectbox("Chọn Bài Học Cần Sửa:", filtered_lessons, format_func=lambda x: f"[{x['chapter_name']}] - {x['title']}")
                if st.button("🔍 Tải thông tin Bài Học này", key="btn_load_les_h"):
                    st.session_state["editing_les_id"] = selected_les_item['id']

                if st.session_state.get("editing_les_id") == selected_les_item['id']:
                    cursor.execute("SELECT * FROM lessons WHERE id = ?", (selected_les_item['id'],))
                    e_les = cursor.fetchone()

                    with st.form("form_edit_lesson_h"):
                        st.markdown(f"**Đang sửa Bài Học ID #{e_les['id']}**")
                        e_chap = st.text_input("Tên Chương:", value=e_les['chapter_name'])
                        e_title = st.text_input("Tiêu đề bài học:", value=e_les['title'])
                        e_summary = st.text_area("Tóm tắt:", value=e_les['summary'] or "")
                        e_content = st.text_area("Nội dung Lý thuyết (Markdown/LaTeX):", value=e_les['content_markdown'] or "", height=220)

                        if st.form_submit_button("💾 Cập Nhật Bài Học", use_container_width=True):
                            cursor.execute('''
                                UPDATE lessons 
                                SET chapter_name = ?, title = ?, summary = ?, content_markdown = ?
                                WHERE id = ?
                            ''', (e_chap, e_title, e_summary, e_content, e_les['id']))
                            conn.commit()
                            st.success("✅ Cập nhật bài học thành công!")
                            del st.session_state["editing_les_id"]
                            st.rerun()

        else:
            cursor.execute("SELECT id, chapter_name, title FROM lessons WHERE grade_id = ? AND subject_id = ? AND semester_id = ?", (sel_ed_g['id'], sel_ed_s['id'], sel_ed_sem['id']))
            les_for_q = cursor.fetchall()

            if not les_for_q:
                st.info("Chưa có bài học nào trong mục này.")
            else:
                target_les_for_q = st.selectbox("Chọn Bài Học để lấy câu hỏi:", les_for_q, format_func=lambda x: f"{x['chapter_name']} - {x['title']}")
                cursor.execute("SELECT id, question_text, question_format FROM questions WHERE lesson_id = ? ORDER BY id ASC", (target_les_for_q['id'],))
                all_q_in_les = cursor.fetchall()

                if not all_q_in_les:
                    st.info("Bài học này chưa có câu hỏi nào.")
                else:
                    selected_q_item = st.selectbox("Chọn câu hỏi cần sửa:", all_q_in_les, format_func=lambda x: f"ID {x['id']} [{x['question_format'].upper()}]: {x['question_text'][:70]}...")

                    if st.button("🔍 Tải chi tiết câu hỏi này", key="btn_load_q_by_les"):
                        st.session_state["editing_q_id"] = selected_q_item['id']

                    if st.session_state.get("editing_q_id") == selected_q_item['id']:
                        cursor.execute("SELECT * FROM questions WHERE id = ?", (selected_q_item['id'],))
                        e_q = cursor.fetchone()

                        with st.form("form_edit_question_h"):
                            st.markdown(f"**Đang sửa Câu Hỏi ID #{e_q['id']}**")
                            eq_text = st.text_area("Nội dung đề bài:", value=e_q['question_text'], height=100)

                            if e_q['question_format'] == 'mcq':
                                c_a, c_b = st.columns(2)
                                with c_a: eq_a = st.text_input("Đáp án A:", value=e_q['option_a'] or ""); eq_b = st.text_input("Đáp án B:", value=e_q['option_b'] or "")
                                with c_b: eq_c = st.text_input("Đáp án C:", value=e_q['option_c'] or ""); eq_d = st.text_input("Đáp án D:", value=e_q['option_d'] or "")
                                eq_correct = st.selectbox("Đáp án đúng:", ["A", "B", "C", "D"], index=["A","B","C","D"].index(e_q['correct_option']) if e_q['correct_option'] in ["A","B","C","D"] else 0)
                                eq_essay_sol = None
                            else:
                                eq_essay_sol = st.text_area("Đáp án mẫu & Thang điểm:", value=e_q['essay_solution'] or "", height=150)
                                eq_a = eq_b = eq_c = eq_d = eq_correct = None

                            eq_explain = st.text_area("Lời giải chi tiết / Gợi ý:", value=e_q['explanation'] or "")

                            if st.form_submit_button("💾 Cập Nhật Câu Hỏi", use_container_width=True):
                                cursor.execute('''
                                    UPDATE questions 
                                    SET question_text = ?, option_a = ?, option_b = ?, option_c = ?, option_d = ?,
                                        correct_option = ?, essay_solution = ?, explanation = ?
                                    WHERE id = ?
                                ''', (eq_text, eq_a, eq_b, eq_c, eq_d, eq_correct, eq_essay_sol, eq_explain, e_q['id']))
                                conn.commit()
                                st.success("✅ Cập nhật câu hỏi thành công!")
                                del st.session_state["editing_q_id"]
                                st.rerun()

    # ==========================================
    # TAB 6: QUẢN LÝ ĐỀ THI ĐỊNH KỲ
    # ==========================================
    with tab_exam_admin:
        st.subheader("Tạo & Chỉnh Sửa Đề Thi Định Kỳ")
        sub_exam_tab1, sub_exam_tab2, sub_exam_tab3 = st.tabs(["➕ Tạo Đề Thi Mới", "❓ Nhập Câu Hỏi Vào Đề Thi", "✏️ Chỉnh Sửa Đề Thi & Câu Hỏi Thi"])

        cursor.execute("SELECT id, name FROM grades"); ex_g_list = cursor.fetchall()
        cursor.execute("SELECT id, name FROM subjects"); ex_s_list = cursor.fetchall()
        cursor.execute("SELECT id, name FROM semesters"); ex_sem_list = cursor.fetchall()

        with sub_exam_tab1:
            with st.form("form_create_exam", clear_on_submit=True):
                e_title = st.text_input("Tên Đề Thi:")
                c_eg, c_es, c_esem = st.columns(3)
                with c_eg: eg = st.selectbox("Lớp:", ex_g_list, format_func=lambda x: x['name'], key="eg_c")
                with c_es: es = st.selectbox("Môn:", ex_s_list, format_func=lambda x: x['name'], key="es_c")
                with c_esem: esem = st.selectbox("Học kỳ:", ex_sem_list, format_func=lambda x: x['name'], key="esem_c")
                e_duration = st.number_input("Thời gian làm bài (Phút):", min_value=15, max_value=180, value=60, step=5)

                if st.form_submit_button("🚀 Tạo Đề Thi Mới", use_container_width=True):
                    if not e_title.strip():
                        st.warning("Vui lòng nhập tên đề thi.")
                    else:
                        cursor.execute("INSERT INTO exams (title, grade_id, subject_id, semester_id, duration_minutes) VALUES (?, ?, ?, ?, ?)",
                                       (e_title, eg['id'], es['id'], esem['id'], e_duration))
                        conn.commit()
                        st.success("🎉 Khởi tạo đề thi mới thành công!")

        with sub_exam_tab2:
            cursor.execute("SELECT id, title FROM exams ORDER BY id DESC")
            all_exams = cursor.fetchall()
            if not all_exams:
                st.info("Chưa có đề thi nào.")
            else:
                target_exam = st.selectbox("Chọn Đề thi nhập câu hỏi:", all_exams, format_func=lambda x: x['title'])
                ex_q_type = st.radio("Loại câu hỏi:", [("mcq", "Trắc nghiệm (MCQ)"), ("essay", "Tự luận (ESSAY)")], format_func=lambda x: x[1], horizontal=True)

                with st.form("form_add_exam_q", clear_on_submit=True):
                    ex_q_num = st.number_input("Câu số:", min_value=1, max_value=70, value=1)
                    ex_q_text = st.text_area("Nội dung đề bài (LaTeX $...$):", height=100)
                    ex_q_img = st.file_uploader("Hình ảnh minh họa:", type=["png", "jpg", "jpeg"], key="ex_img")
                    ex_q_score = st.number_input("Thang điểm:", min_value=0.1, max_value=10.0, value=0.25 if ex_q_type[0]=='mcq' else 1.0, step=0.25)

                    if ex_q_type[0] == 'mcq':
                        ca, cb = st.columns(2)
                        with ca: ex_opt_a = st.text_input("A:"); ex_opt_b = st.text_input("B:")
                        with cb: ex_opt_c = st.text_input("C:"); ex_opt_d = st.text_input("D:")
                        ex_correct = st.selectbox("Đáp án đúng:", ["A", "B", "C", "D"])
                        ex_essay_sol = None
                    else:
                        ex_essay_sol = st.text_area("Đáp án mẫu & Thang điểm:", height=150)
                        ex_opt_a = ex_opt_b = ex_opt_c = ex_opt_d = ex_correct = None

                    ex_explain = st.text_area("Ghi chú / Lời giải:", height=80)

                    if st.form_submit_button("➕ Lưu Câu Hỏi Vào Đề Thi", use_container_width=True):
                        if not ex_q_text.strip():
                            st.warning("Vui lòng nhập nội dung đề bài.")
                        else:
                            img_ex_path = save_uploaded_file(ex_q_img)
                            cursor.execute('''
                                INSERT INTO exam_questions (
                                    exam_id, question_type, question_num, question_text, image_path,
                                    option_a, option_b, option_c, option_d, correct_option,
                                    essay_solution, max_score, explanation
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                target_exam['id'], ex_q_type[0], ex_q_num, ex_q_text, img_ex_path,
                                ex_opt_a, ex_opt_b, ex_opt_c, ex_opt_d, ex_correct,
                                ex_essay_sol, ex_q_score, ex_explain
                            ))
                            conn.commit()
                            st.success(f"🎉 Đã thêm Câu {ex_q_num} vào đề thi!")

        with sub_exam_tab3:
            st.markdown("##### Chỉnh sửa Đề Thi & Câu Hỏi Thi")
            edit_exam_obj = st.radio("Đối tượng chỉnh sửa:", ["Thông Tin Đề Thi", "Câu Hỏi Trong Đề Thi"], horizontal=True)

            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1: f_eg = st.selectbox("Lớp:", ex_g_list, format_func=lambda x: x['name'], key="f_eg")
            with col_e2: f_es = st.selectbox("Môn:", ex_s_list, format_func=lambda x: x['name'], key="f_es")
            with col_e3: f_esem = st.selectbox("Học kỳ:", ex_sem_list, format_func=lambda x: x['name'], key="f_esem")

            cursor.execute("SELECT * FROM exams WHERE grade_id = ? AND subject_id = ? AND semester_id = ? ORDER BY title ASC", (f_eg['id'], f_es['id'], f_esem['id']))
            matched_exams = cursor.fetchall()

            if not matched_exams:
                st.info("Chưa có đề thi nào.")
            else:
                sel_edit_exam = st.selectbox("Chọn Đề Thi:", matched_exams, format_func=lambda x: x['title'], key="sel_edit_exam")

                if edit_exam_obj == "Thông Tin Đề Thi":
                    with st.form("form_edit_exam_info"):
                        st.markdown(f"**Sửa Đề thi ID #{sel_edit_exam['id']}**")
                        me_title = st.text_input("Tên đề thi:", value=sel_edit_exam['title'])
                        me_dur = st.number_input("Thời gian (Phút):", value=sel_edit_exam['duration_minutes'], min_value=15, max_value=180)
                        
                        if st.form_submit_button("💾 Cập Nhật Đề Thi", use_container_width=True):
                            cursor.execute("UPDATE exams SET title = ?, duration_minutes = ? WHERE id = ?", (me_title, me_dur, sel_edit_exam['id']))
                            conn.commit()
                            st.success("✅ Cập nhật đề thi thành công!")
                            st.rerun()

                else:
                    cursor.execute("SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_num ASC", (sel_edit_exam['id'],))
                    all_ex_q = cursor.fetchall()

                    if not all_ex_q:
                        st.info("Đề thi chưa có câu hỏi nào.")
                    else:
                        sel_ex_q_item = st.selectbox("Chọn Câu Hỏi Cần Sửa:", all_ex_q, format_func=lambda x: f"Câu {x['question_num']} [{x['question_type'].upper()}]: {x['question_text'][:60]}...")
                        
                        if st.button("🔍 Tải nội dung câu hỏi thi", key="btn_load_ex_q"):
                            st.session_state["editing_ex_q_id"] = sel_ex_q_item['id']

                        if st.session_state.get("editing_ex_q_id") == sel_ex_q_item['id']:
                            cursor.execute("SELECT * FROM exam_questions WHERE id = ?", (sel_ex_q_item['id'],))
                            eq_data = cursor.fetchone()

                            with st.form("form_edit_ex_question"):
                                st.markdown(f"**Đang sửa Câu {eq_data['question_num']}**")
                                meq_num = st.number_input("Câu số:", value=eq_data['question_num'])
                                meq_text = st.text_area("Đề bài:", value=eq_data['question_text'], height=100)
                                meq_score = st.number_input("Điểm số:", value=eq_data['max_score'], min_value=0.1, max_value=10.0, step=0.25)

                                if eq_data['question_type'] == 'mcq':
                                    c_a1, c_b1 = st.columns(2)
                                    with c_a1: meq_a = st.text_input("A:", value=eq_data['option_a'] or ""); meq_b = st.text_input("B:", value=eq_data['option_b'] or "")
                                    with c_b1: meq_c = st.text_input("C:", value=eq_data['option_c'] or ""); meq_d = st.text_input("D:", value=eq_data['option_d'] or "")
                                    meq_corr = st.selectbox("Đáp án đúng:", ["A", "B", "C", "D"], index=["A","B","C","D"].index(eq_data['correct_option']) if eq_data['correct_option'] in ["A","B","C","D"] else 0)
                                    meq_essay_sol = None
                                else:
                                    meq_essay_sol = st.text_area("Đáp án mẫu & Thang điểm:", value=eq_data['essay_solution'] or "", height=150)
                                    meq_a = meq_b = meq_c = meq_d = meq_corr = None

                                meq_explain = st.text_area("Lời giải / Gợi ý:", value=eq_data['explanation'] or "")

                                if st.form_submit_button("💾 Cập Nhật Câu Hỏi Thi", use_container_width=True):
                                    cursor.execute('''
                                        UPDATE exam_questions 
                                        SET question_num = ?, question_text = ?, max_score = ?,
                                            option_a = ?, option_b = ?, option_c = ?, option_d = ?, correct_option = ?,
                                            essay_solution = ?, explanation = ?
                                        WHERE id = ?
                                    ''', (
                                        meq_num, meq_text, meq_score,
                                        meq_a, meq_b, meq_c, meq_d, meq_corr,
                                        meq_essay_sol, meq_explain, eq_data['id']
                                    ))
                                    conn.commit()
                                    st.success("✅ Cập nhật câu hỏi thi thành công!")
                                    del st.session_state["editing_ex_q_id"]
                                    st.rerun()

    # ==========================================
    # TAB 7: THỐNG KÊ
    # ==========================================
    with tab_manage:
        st.subheader("Thống kê tổng quan")
        cursor.execute("SELECT COUNT(*) as count FROM lessons"); les_count = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM questions"); q_count = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM exams"); ex_count = cursor.fetchone()['count']

        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng số Bài học", les_count)
        col2.metric("Tổng Câu hỏi Bài học", q_count)
        col3.metric("Số Đề thi Định kỳ", ex_count)