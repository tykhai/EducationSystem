import streamlit as st
import re
import hashlib
from services.db_connection import get_connection
from datetime import datetime, date, timedelta
from modules.student_views import recalculate_user_points_from_log

def hash_password(password: str) -> str:
    """Hàm hash mật khẩu SHA-256 (Thay đổi nếu dự án dùng bcrypt)."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def calculate_rank_and_next_goal(points):
    """Tính hạng hiện tại và mốc điểm năng lượng để thăng hạng tiếp theo."""
    ranks = [
        ("🥉 Đồng", 0, 200, "#CD7F32"),
        ("🥈 Bạc", 200, 500, "#C0C0C0"),
        ("🥇 Vàng", 500, 1000, "#FFD700"),
        ("🏆 Bạch Kim", 1000, 2000, "#E0E0E0"),
        ("💎 Kim Cương", 2000, 5000, "#00E5FF")
    ]
    
    for name, low, high, color in ranks:
        if low <= points < high:
            needed = high - points
            progress = (points - low) / (high - low)
            return name, color, high, needed, min(progress, 1.0)
            
    # Hạng cao nhất Kim Cương
    return "💎 Kim Cương", "#00E5FF", 5000, 0, 1.0

def ensure_user_gamification(user_id):
    """Khởi tạo bản ghi Gamification cho học sinh nếu chưa tồn tại trong Database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_gamification WHERE user_id = ?", (user_id,))
    g_data = cursor.fetchone()
    
    if not g_data:
        # Thêm mới record khởi tạo điểm 0 cho học sinh
        cursor.execute("""
            INSERT INTO user_gamification 
            (user_id, daily_points, weekly_points, monthly_points, semester1_points, total_points, current_streak, last_active_date)
            VALUES (?, 0, 0, 0, 0, 0, 0, NULL)
        """, (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM user_gamification WHERE user_id = ?", (user_id,))
        g_data = cursor.fetchone()
        
    conn.close()
    return g_data

# ==========================================
# DIALOG POPUP: HỒ SƠ & CÀI ĐẶT CHI TIẾT
# ==========================================

@st.dialog("👤 Hồ Sơ Học Sinh & Cài Đặt Chi Tiết", width="large")
def show_user_profile_dialog(user_id):
    """Popup chứa thông tin chi tiết, Đổi mật khẩu, Lịch streak và Thống kê học đều môn."""
    conn = get_connection()
    cursor = conn.cursor()
    
    current_role = st.session_state.user.get('role', '').lower()
    
    # Nếu là admin hoặc teacher thì chỉ hiện Tab Đổi Mật Khẩu
    if current_role in ['admin', 'teacher']:
        st.markdown(f"**Họ và tên:** {st.session_state.user['full_name']}")
        st.markdown(f"**Tài khoản:** {st.session_state.user['username']}")
        st.markdown(f"**Vai trò:** `{st.session_state.user['role'].upper()}`")
        st.divider()
        
        st.subheader("Đổi Mật Khẩu")
        with st.form("dialog_form_change_pass"):
            old_pass = st.text_input("Mật khẩu hiện tại", type="password")
            new_pass = st.text_input("Mật khẩu mới", type="password")
            confirm_pass = st.text_input("Xác nhận mật khẩu mới", type="password")
            
            if st.form_submit_button("Lưu Mật Khẩu Mới", use_container_width=True):
                if not old_pass or not new_pass:
                    st.warning("Vui lòng điền đầy đủ các trường.")
                elif new_pass != confirm_pass:
                    st.error("Mật khẩu mới không trùng khớp.")
                else:
                    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                    u = cursor.fetchone()
                    
                    hashed_old = hash_password(old_pass)
                    if u and (u['password_hash'] == old_pass or u['password_hash'] == hashed_old):
                        hashed_new = hash_password(new_pass)
                        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_new, user_id))
                        conn.commit()
                        st.success("🎉 Đổi mật khẩu thành công!")
                    else:
                        st.error("❌ Mật khẩu hiện tại không chính xác.")
        conn.close()
        return

    # Đối với Học Sinh: Hiển thị đủ 3 Tabs
    tab1, tab2, tab3 = st.tabs(["🔑 Tài khoản & Đổi MK", "📅 Lịch Chuỗi Học (Heatmap)", "🎯 Chỉ Số Học Đều Môn"])
    
    # --- TAB 1: ĐỔI MẬT KHẨU ---
    with tab1:
        st.markdown(f"**Họ và tên:** {st.session_state.user['full_name']}")
        st.markdown(f"**Tài khoản:** {st.session_state.user['username']}")
        st.markdown(f"**Vai trò:** `{st.session_state.user['role'].upper()}`")
        st.divider()
        
        st.subheader("Đổi Mật Khẩu")
        with st.form("dialog_form_change_pass"):
            old_pass = st.text_input("Mật khẩu hiện tại", type="password")
            new_pass = st.text_input("Mật khẩu mới", type="password")
            confirm_pass = st.text_input("Xác nhận mật khẩu mới", type="password")
            
            if st.form_submit_button("Lưu Mật Khẩu Mới", use_container_width=True):
                if not old_pass or not new_pass:
                    st.warning("Vui lòng điền đầy đủ các trường.")
                elif new_pass != confirm_pass:
                    st.error("Mật khẩu mới không trùng khớp.")
                else:
                    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                    u = cursor.fetchone()
                    
                    hashed_old = hash_password(old_pass)
                    if u and (u['password_hash'] == old_pass or u['password_hash'] == hashed_old):
                        hashed_new = hash_password(new_pass)
                        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_new, user_id))
                        conn.commit()
                        st.success("🎉 Đổi mật khẩu thành công!")
                    else:
                        st.error("❌ Mật khẩu hiện tại không chính xác.")

    # --- TAB 2: LỊCH CHUỖI NGÀY HỌC ---
    with tab2:
        st.subheader("📅 Chi Tiết Chuỗi Ngày Học Trong Tuần")
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday()) # Thứ 2
        
        cursor.execute("""
            SELECT DISTINCT DATE(answered_at) as act_date 
            FROM user_answer_logs 
            WHERE user_id = ? AND DATE(answered_at) >= ?
        """, (user_id, start_of_week.isoformat()))
        active_days = [row['act_date'] for row in cursor.fetchall()]

        days_name = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
        cols = st.columns(7)
        
        for idx, col in enumerate(cols):
            day_date = start_of_week + timedelta(days=idx)
            day_str = day_date.isoformat()
            
            is_past = day_date < today
            is_today = day_date == today
            has_learned = day_str in active_days
            
            if has_learned:
                status_icon = "🔥"
                status_text = "Đã học"
                bg_color = "#E8F5E9"
                border = "1px solid #4CAF50"
            elif is_today:
                status_icon = "⏳"
                status_text = "Hôm nay"
                bg_color = "#FFFDE7"
                border = "2px solid #FFC107"
            elif is_past:
                status_icon = "❌"
                status_text = "Bỏ lỡ"
                bg_color = "#FFEBEE"
                border = "1px solid #FF5252"
            else:
                status_icon = "⚪"
                status_text = "Chưa đến"
                bg_color = "#F5F5F5"
                border = "1px solid #E0E0E0"
                
            col.markdown(f"""
                <div style="text-align:center; background:{bg_color}; border:{border}; border-radius:8px; padding:8px 2px;">
                    <b>{days_name[idx]}</b><br>
                    <span style="font-size:18px;">{status_icon}</span><br>
                    <small>{status_text}</small>
                </div>
            """, unsafe_allow_html=True)

    # --- TAB 3: CHỈ SỐ HỌC ĐỀU MÔN ---
    with tab3:
        st.subheader("🎯 Đánh Giá Học Đều Các Môn")
        role = get_user_role(user_id)
        if role:
            allowed_subj_ids = parse_allowed_ids(role['allowed_subjects'])
            cursor.execute("SELECT id, name FROM subjects")
            all_subjs = cursor.fetchall()
            
            if "*" in allowed_subj_ids:
                assigned_subjects = all_subjs
            else:
                assigned_subjects = [s for s in all_subjs if str(s['id']) in allowed_subj_ids or s.get('code') in allowed_subj_ids]
            
            if assigned_subjects:
                cursor.execute("""
                    SELECT subject_id, COUNT(*) as cnt 
                    FROM user_answer_logs 
                    WHERE user_id = ? 
                    GROUP BY subject_id
                """, (user_id,))
                user_logs = {row['subject_id']: row['cnt'] for row in cursor.fetchall()}
                
                for s in assigned_subjects:
                    cnt = user_logs.get(s['id'], 0)
                    st.write(f"- **Môn {s['name']}:** {cnt} bài tập đã làm.")
            else:
                st.info("Chưa có môn học được gán.")

    conn.close()

# ==========================================
# SIDEBAR GAMIFICATION & USER MANAGEMENT
# ==========================================

def render_student_sidebar_gamification(user_id):
    """Hiển thị bảng năng lượng, đổi mật khẩu và điểm số học đều môn ngay dưới Sidebar."""
    
    user_role = st.session_state.user.get('role', '').lower()
    
    # 1. ĐỔI MẬT KHẨU
    conn = get_connection()
    cursor = conn.cursor()
    with st.sidebar.expander("🔑 Đổi Mật Khẩu", expanded=False):
        with st.form("form_change_pass"):
            old_pass = st.text_input("Mật khẩu hiện tại", type="password")
            new_pass = st.text_input("Mật khẩu mới", type="password")
            confirm_pass = st.text_input("Xác nhận mật khẩu mới", type="password")
            if st.form_submit_button("Lưu Mật Khẩu"):
                if not old_pass or not new_pass:
                    st.warning("Vui lòng nhập đầy đủ thông tin.")
                elif new_pass != confirm_pass:
                    st.error("Mật khẩu mới không khớp.")
                else:
                    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                    u = cursor.fetchone()
                    if u and u['password_hash'] == old_pass:
                        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_pass, user_id))
                        conn.commit()
                        st.success("🎉 Đổi mật khẩu thành công!")
                    else:
                        st.error("❌ Mật khẩu hiện tại không đúng.")
                        
    # ẨN GAMIFICATION VÀ THANH NĂNG LƯỢNG CHO ADMIN VÀ TEACHER
    if user_role in ['admin', 'teacher']:
        conn.close()
        return

    # 2. GAMIFICATION SUMMARY & THANH NĂNG LƯỢNG (CHỈ DÀNH CHO HỌC SINH)
    g_data = ensure_user_gamification(user_id)  
    
    if not g_data:
        st.sidebar.info("Làm câu hỏi đầu tiên để kích hoạt Gamification!")
        conn.close()
        return

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Năng Lượng & Thăng Hạng")

    period = st.sidebar.selectbox("Chu kỳ tích điểm:", ["Tháng này", "Tuần này", "Hôm nay", "Học kỳ 1"], index=0)
    
    pts = g_data['monthly_points']
    if period == "Tuần này": pts = g_data['weekly_points']
    elif period == "Hôm nay": pts = g_data['daily_points']
    elif period == "Học kỳ 1": pts = g_data['semester1_points']

    rank_name, rank_color, next_goal, needed_pts, energy_progress = calculate_rank_and_next_goal(pts)

    st.sidebar.markdown(f"**Danh hiệu:** <span style='color:{rank_color}; font-weight:bold;'>{rank_name}</span>", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Điểm năng lượng ({period}):** `{pts} / {next_goal} PTS`")
    
    st.sidebar.progress(energy_progress, text=f"Còn {needed_pts}đ để thăng cấp 🚀")

    # 3. LỊCH CHUỖI NGÀY HỌC TRONG TUẦN (WEEKLY HEATMAP)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Lịch Chuỗi Học Trong Tuần")
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    cursor.execute("""
        SELECT DISTINCT DATE(answered_at) as act_date 
        FROM user_answer_logs 
        WHERE user_id = ? AND DATE(answered_at) >= ?
    """, (user_id, start_of_week.isoformat()))
    active_days = [row['act_date'] for row in cursor.fetchall()]

    days_name = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    cols = st.sidebar.columns(7)
    
    for idx, col in enumerate(cols):
        day_date = start_of_week + timedelta(days=idx)
        day_str = day_date.isoformat()
        
        is_past = day_date <= today
        is_today = day_date == today
        has_learned = day_str in active_days
        
        if has_learned:
            status_icon = "🔥"
            bg_color = "#E8F5E9"
            border = "1px solid #4CAF50"
        elif is_past:
            status_icon = "❌"
            bg_color = "#FFEBEE"
            border = "1px solid #FF5252"
        elif is_today:
            status_icon = "⏳"
            bg_color = "#FFFDE7"
            border = "1px solid #FFC107"
        else:
            status_icon = "⚪"
            bg_color = "#F5F5F5"
            border = "1px solid #E0E0E0"
            
        col.markdown(f"""
            <div style="text-align:center; background:{bg_color}; border-radius:6px; padding:4px 0; font-size:11px;">
                <b>{days_name[idx]}</b><br>{status_icon}
            </div>
        """, unsafe_allow_html=True)

    # 4. CHỈ SỐ HỌC ĐỀU MÔN
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Chỉ Số Học Đều Môn")
    
    role = get_user_role(user_id)
    if role:
        allowed_subj_ids = parse_allowed_ids(role['allowed_subjects'])
        
        if "*" in allowed_subj_ids:
            cursor.execute("SELECT id, name FROM subjects")
            assigned_subjects = cursor.fetchall()
        else:
            cursor.execute("SELECT id, name FROM subjects")
            all_subjs = cursor.fetchall()
            assigned_subjects = [s for s in all_subjs if str(s['id']) in allowed_subj_ids or s.get('code') in allowed_subj_ids]
        
        if assigned_subjects:
            total_assigned = len(assigned_subjects)
            
            cursor.execute("""
                SELECT subject_id, COUNT(*) as cnt 
                FROM user_answer_logs 
                WHERE user_id = ? 
                GROUP BY subject_id
            """, (user_id,))
            user_logs = {row['subject_id']: row['cnt'] for row in cursor.fetchall()}
            
            learned_subj_count = sum(1 for s in assigned_subjects if user_logs.get(s['id'], 0) > 0)
            
            st.sidebar.caption(f"Đã hoàn thành bài tập ở **{learned_subj_count}/{total_assigned}** môn được phân công.")
            
            if learned_subj_count == total_assigned and total_assigned > 0:
                counts = [user_logs.get(s['id'], 0) for s in assigned_subjects]
                min_c, max_c = min(counts), max(counts)
                
                if max_c > 0 and min_c >= (max_c * 0.7):
                    st.sidebar.success("🌟 **Cân bằng xuất sắc!** Bạn học rất đều tất cả các môn (+50đ thưởng).")
                else:
                    st.sidebar.warning("⚖️ **Cảnh báo học lệch:** Hãy làm thêm bài tập ở các môn có lượng bài còn ít.")
            else:
                st.sidebar.info("💡 **Gợi ý:** Hãy hoàn thành ít nhất 1 bài tập ở tất cả các môn để đạt danh hiệu **Học Đều Môn**!")

    conn.close()

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
    user_role = st.session_state.user.get('role', '').lower()

    # 1. Bấm vào Tên -> Mở Pop-up Hồ sơ
    col_name, col_logout = st.sidebar.columns([3, 1])
    with col_name:
        if st.button(f"👤 **{st.session_state.user['full_name']}** ⚙️", use_container_width=True, help="Bấm để xem hồ sơ & đổi mật khẩu"):
            show_user_profile_dialog(user_id)
    with col_logout:
        if st.button("🚪", help="Đăng xuất"):
            st.session_state.user = None
            st.rerun()

    st.sidebar.markdown("---")

    # 2. GAMIFICATION COMPACT (Chỉ hiển thị đối với Học Sinh - Không phải Admin & Teacher)
    if user_role not in ['admin', 'teacher']:
        if 'user_points' not in st.session_state:
            recalculate_user_points_from_log(user_id)
        g_data = ensure_user_gamification(user_id)
        
        period = st.sidebar.selectbox("Chu kỳ tích điểm:", ["Hôm nay", "Tuần này", "Tháng này", "Học kỳ 1"], index=0)
        
        pts = g_data['daily_points']
        if period == "Tuần này": pts = g_data['weekly_points']
        elif period == "Tháng này": pts = g_data['monthly_points']
        elif period == "Học kỳ 1": pts = g_data['semester1_points']

        rank_name, rank_color, next_goal, needed_pts, energy_progress = calculate_rank_and_next_goal(pts)

        st.sidebar.markdown(f"Danh hiệu: <span style='color:{rank_color}; font-weight:bold;'>{rank_name}</span> | 🔥 **{g_data['current_streak']} ngày**", unsafe_allow_html=True)
        st.sidebar.markdown(f"Điểm ({period}): **{pts} / {next_goal} PTS**")
        
        st.sidebar.progress(energy_progress, text=f"Còn {needed_pts}đ để thăng cấp 🚀" if needed_pts > 0 else "Đã đạt đỉnh Kim Cương! 👑")

        st.sidebar.markdown("---")

    # 3. DANH MỤC HỌC TẬP (Lọc Lớp -> Môn -> Học kỳ -> Bài học)
    st.sidebar.subheader("📚 Danh Mục Học Tập")
    
    role = get_user_role(user_id)
    if not role:
        st.sidebar.error("⚠️ Tài khoản chưa được cấp quyền học tập.")
        return None

    allowed_grades = parse_allowed_ids(role['allowed_grades'])
    allowed_subjects = parse_allowed_ids(role['allowed_subjects'])
    allowed_semesters = parse_allowed_ids(role['allowed_semesters'])

    conn = get_connection()
    cursor = conn.cursor()

    # Lớp
    cursor.execute("SELECT * FROM grades")
    all_grades = cursor.fetchall()
    filtered_grades = all_grades if "*" in allowed_grades else [g for g in all_grades if str(g['id']) in allowed_grades or g.get('code') in allowed_grades]
    if not filtered_grades:
        st.sidebar.warning("🔒 Chưa được gán Lớp.")
        conn.close()
        return None
    sel_grade = st.sidebar.selectbox("Lớp:", filtered_grades, format_func=lambda x: x['name'])

    # Môn
    cursor.execute("SELECT * FROM subjects")
    all_subjects = cursor.fetchall()
    filtered_subjects = all_subjects if "*" in allowed_subjects else [s for s in all_subjects if str(s['id']) in allowed_subjects or s.get('code') in allowed_subjects]
    if not filtered_subjects:
        st.sidebar.warning("🔒 Chưa được gán Môn.")
        conn.close()
        return None
    sel_subject = st.sidebar.selectbox("Môn:", filtered_subjects, format_func=lambda x: x['name'])

    # Học kỳ
    cursor.execute("SELECT id, name FROM semesters")
    all_semesters = cursor.fetchall()
    filtered_semesters = all_semesters if "*" in allowed_semesters else [se for se in all_semesters if str(se['id']) in allowed_semesters or se.get('code') in allowed_semesters]
    if not filtered_semesters:
        st.sidebar.warning("🔒 Chưa được gán Học Kỳ.")
        conn.close()
        return None
    sel_semester = st.sidebar.selectbox("Học kỳ:", filtered_semesters, format_func=lambda x: x['name'])

    # Bài học
    cursor.execute("""
        SELECT * FROM lessons 
        WHERE grade_id = ? AND subject_id = ? AND semester_id = ?
    """, (sel_grade['id'], sel_subject['id'], sel_semester['id']))
    lessons = cursor.fetchall()
    
    sel_lesson = None
    if lessons:
        sel_lesson = st.sidebar.selectbox("Bài học:", lessons, format_func=lambda x: f"{x['chapter_name']} - {x['title']}")
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