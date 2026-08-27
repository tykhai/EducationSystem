# modules/teacher_views.py
import streamlit as st
import pandas as pd
from datetime import datetime
from services.db_connection import get_connection

def render_teacher_grading_dashboard(teacher_id,filter_data):
    st.title("📝 Màn Hình Chấm Bài Tự Luận")
    
    if not filter_data or not filter_data.get('lesson'):
        st.info("👉 Vui lòng chọn Lớp, Môn học và Bài học từ Menu bên trái để bắt đầu.")
        return
        
    sel_lesson = filter_data.get('lesson')
    
    conn = get_connection()
    cursor = conn.cursor()

    # =========================================================
    # 1. BỘ LỌC DÀNH CHO GIÁO VIÊN / TUTOR
    # =========================================================
    # st.sidebar.header("🔍 Bộ Lọc Môn & Lớp")
    
    #Lấy danh sách khối/môn học mà giáo viên được phân quyền
    # grade = st.sidebar.selectbox("Lớp/Khối", ["Khối 10", "Khối 11", "Khối 12"])
    # subject = st.sidebar.selectbox("Môn học", ["Toán Học", "Vật Lý", "Hóa Học"])
    # exam_type = st.sidebar.selectbox("Loại bài làm", ["Bài Tập Rèn Luyện", "Đề Thi Định Kỳ"])

    # Lấy danh sách các bài đang chờ chấm (status = 'pending')
    cursor.execute("""
        SELECT s.id as submission_id, u.full_name as student_name, q.question_text, 
               q.essay_solution, q.explanation, s.student_answer, s.created_at
        FROM essay_submissions s
        JOIN users u ON s.student_id = u.id
        JOIN questions q ON s.question_id = q.id
        WHERE s.status = 'pending'
        ORDER BY s.created_at ASC
    """)
    pending_list = cursor.fetchall()

    if not pending_list:
        st.success("🎉 Tất cả bài tập tự luận đã được chấm xong!")
        conn.close()
        return

    # Danh sách chọn học sinh cần chấm
    student_options = {f"{row['student_name']} - Bài #{row['submission_id']} ({row['created_at']})": row for row in pending_list}
    selected_option = st.selectbox("📌 Chọn bài làm cần chấm:", list(student_options.keys()))
    selected_sub = student_options[selected_option]

    st.divider()

    # =========================================================
    # 2. GIAO DIỆN CHẤM BÀI 3 CỘT (LAYOUT)
    # =========================================================
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])

    # ---------------------------------------------------------
    # CỘT 1: BÀI LÀM CỦA HỌC SINH
    # ---------------------------------------------------------
    with col1:
        st.subheader("👤 Bài Làm Của Học Sinh")
        st.info(f"**Học sinh:** {selected_sub['student_name']}\n\n**Thời gian nộp:** {selected_sub['created_at']}")
        
        with st.container(border=True):
            st.markdown("**Đề bài:**")
            st.markdown(selected_sub['question_text'])
            st.divider()
            st.markdown("**Bài làm chi tiết:**")
            if selected_sub['student_answer']:
                # Hiển thị dạng Công thức / Văn bản
                st.markdown(selected_sub['student_answer'])
            else:
                st.warning("Học sinh không để lại lời giải chi tiết.")

    # ---------------------------------------------------------
    # CỘT 2: ĐÁP ÁN MẪU & HƯỚNG DẪN
    # ---------------------------------------------------------
    with col2:
        st.subheader("📖 Đáp Án Mẫu & Lời Giải")
        with st.container(border=True):
            st.markdown("**Đáp án chuẩn / Lời giải mẫu:**")
            st.markdown(selected_sub['essay_solution'] or "Chưa có đáp án mẫu.")
            
            if selected_sub['explanation']:
                st.divider()
                st.markdown("**Biểu điểm / Ghi chú cho giáo viên:**")
                st.info(selected_sub['explanation'])

    # ---------------------------------------------------------
    # CỘT 3: NHẬP ĐIỂM & NHẬN XÉT (PHẦN CỦA GIÁO VIÊN)
    # ---------------------------------------------------------
    with col3:
        st.subheader("✍️ Chấm Điểm")
        with st.form(key=f"grading_form_{selected_sub['submission_id']}"):
            score = st.number_input("Số điểm (Thang điểm 10):", min_value=0.0, max_value=10.0, value=10.0, step=0.5)
            feedback = st.text_area("Lời nhận xét / Gợi ý chi tiết:", placeholder="Ví dụ: Em làm đúng hướng nhưng tính toán sai ở bước 2...", height=150)
            
            submit_grade = st.form_submit_button("💾 Xác Nhận & Lưu Điểm")

        if submit_grade:
            # Quy đổi ra điểm Gamification (VD: Thang 10 tương ứng max 30 PTS)
            gamification_pts = int((score / 10.0) * 30)

            # 1. Cập nhật bảng essay_submissions
            cursor.execute("""
                UPDATE essay_submissions
                SET status = 'graded',
                    score = ?,
                    points_earned = ?,
                    teacher_feedback = ?,
                    graded_by = ?,
                    graded_at = ?
                WHERE id = ?
            """, (score, gamification_pts, feedback, teacher_id, datetime.now().isoformat(), selected_sub['submission_id']))

            # 2. Ghi nhật ký vào user_answer_log
            cursor.execute("""
                INSERT INTO user_answer_log (user_id, question_id, is_correct, points_earned, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (selected_sub['submission_id'], selected_sub['submission_id'], score >= 5.0, gamification_pts, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            st.balloons()
            st.success(f"✅ Đã lưu điểm cho {selected_sub['student_name']} thành công (+{gamification_pts} PTS)!")
            st.rerun()