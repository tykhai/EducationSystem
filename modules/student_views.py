# modules/student_views.py

import streamlit as st
import os
import streamlit.components.v1 as components
import re
import json
from services.db_connection import get_connection
from components.math_editor import simple_math_editor
from datetime import datetime, date,timedelta
#1. Visual_math_editor
#from components.math_editor import visual_math_editor
#2. Textarea_preview
#from components.math_editor import textarea_preview
#3. Simple_math_editor
#from components.math_editor import simple_math_editor
#4. Latex_editor
#from components.math_editor import latex_editor
#5. Equation_editor
#from components.math_editor import equation_editor
#6. Textarea_toolbar
#from components.math_editor import simple_math_editor

# Định nghĩa đường dẫn lưu trữ thư mục ảnh
IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

def recalculate_user_points_from_log(user_id):
    """
    Hàm tính toán lại toàn bộ điểm của User dựa trên lịch sử làm bài trong bảng `user_answer_logs`.
    Đảm bảo tuyệt đối chính xác, không bao giờ bị lệch hay âm điểm.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    today_str = date.today().isoformat()
    
    # 1. Tính tổng điểm HÔM NAY từ user_answer_log
    cursor.execute("""
        SELECT COALESCE(SUM(points_awarded), 0) as daily_total
        FROM user_answer_logs
        WHERE user_id = ? AND DATE(answered_at) = ?
    """, (user_id, today_str))
    daily_pts = max(0, cursor.fetchone()['daily_total'])

    # 2. Tính tổng điểm TUẦN NÀY (Từ Thứ 2 đến Chủ Nhật)
    cursor.execute("""
        SELECT COALESCE(SUM(points_awarded), 0) as weekly_total
        FROM user_answer_logs
        WHERE user_id = ? AND DATE(answered_at) >= date('now', 'weekday 0', '-6 days')
    """, (user_id,))
    weekly_pts = max(0, cursor.fetchone()['weekly_total'])

    # 3. Tính tổng điểm THÁNG NÀY
    cursor.execute("""
        SELECT COALESCE(SUM(points_awarded), 0) as monthly_total
        FROM user_answer_logs
        WHERE user_id = ? AND strftime('%Y-%m', answered_at) = strftime('%Y-%m', 'now')
    """, (user_id,))
    monthly_pts = max(0, cursor.fetchone()['monthly_total'])

    # 4. Tính TỔNG ĐIỂM TẤT CẢ TỪ TRƯỚC ĐẾN NAY
    cursor.execute("""
        SELECT COALESCE(SUM(points_awarded), 0) as all_time_total
        FROM user_answer_logs
        WHERE user_id = ?
    """, (user_id,))
    total_pts = max(0, cursor.fetchone()['all_time_total'])

    # 5. Xử lý Streak
    cursor.execute("SELECT current_streak, last_active_date FROM user_gamification WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    streak = row['current_streak'] if row else 0
    last_act = row['last_active_date'] if row else None

    if last_act != today_str:
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        if last_act == yesterday_str:
            streak += 1
        else:
            streak = 1

    # 6. Cập nhật lại bản ghi Snapshot trong user_gamification
    cursor.execute("""
        UPDATE user_gamification
        SET daily_points = ?,
            weekly_points = ?,
            monthly_points = ?,
            total_points = ?,
            current_streak = ?,
            last_active_date = ?
        WHERE user_id = ?
    """, (daily_pts, weekly_pts, monthly_pts, total_pts, streak, today_str, user_id))
    
    conn.commit()
    conn.close()

    # 7. Lưu vào session_state để UI hiển thị tức thì không cần reload DB
    st.session_state['user_points'] = {
        'daily': daily_pts,
        'weekly': weekly_pts,
        'monthly': monthly_pts,
        'total': total_pts,
        'streak': streak
    }
    
    return daily_pts

def calculate_rank(points):
    """Xác định hạng Rank và Badge tương ứng dựa trên điểm số tích lũy."""
    #Nếu điểm < 0 thì đưa về 0
    points = max(0, points)
    if points >= 2000:
        return "💎 Kim Cương", "#00E5FF", "https://cdn-icons-png.flaticon.com/512/616/616490.png"
    elif points >= 1000:
        return "🏆 Bạch Kim", "#E0E0E0", "https://cdn-icons-png.flaticon.com/512/2583/2583346.png"
    elif points >= 500:
        return "🥇 Vàng", "#FFD700", "https://cdn-icons-png.flaticon.com/512/2583/2583319.png"
    elif points >= 200:
        return "🥈 Bạc", "#C0C0C0", "https://cdn-icons-png.flaticon.com/512/2583/2583350.png"
    else:
        return "🥉 Đồng", "#CD7F32", "https://cdn-icons-png.flaticon.com/512/2583/2583434.png"

def add_points_on_correct_answer(user_id, points_earned):
    """GỌI HÀM NÀY MỖI KHI HỌC SINH LÀM ĐÚNG 1 CÂU HỎI"""
    from services.db_connection import get_connection
    from datetime import date, timedelta
    
    conn = get_connection()
    cursor = conn.cursor()
    
    today_str = date.today().isoformat()
    # Lấy thông tin Gamification hiện tại của User
    cursor.execute("SELECT daily_points, weekly_points, monthly_points, semester1_points, total_points, current_streak, last_active_date FROM user_gamification WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return

    # 1. Khởi tạo / Lấy dữ liệu cũ
    last_act = row['last_active_date']
    streak = row['current_streak'] or 0
    
    daily_pts = row['daily_points'] or 0
    weekly_pts = row['weekly_points'] or 0
    monthly_pts = row['monthly_points'] or 0
    sem1_pts = row['semester1_points'] or 0
    total_pts = row['total_points'] or 0

    # 2. Xử lý Logic Chu kỳ Ngày mới (Reset daily_points nếu sang ngày mới)
    if last_act != today_str:
        daily_pts = 0  # Reset điểm ngày về 0 cho ngày mới!
        
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        if last_act == yesterday_str:
            streak += 1  # Học liên tiếp -> Cộng Streak
        else:
            streak = 1   # Bị ngắt quãng -> Reset Streak về 1

    # 3. Cộng / Trừ điểm và Chặn điểm âm (MAX với 0)
    new_daily = max(0, daily_pts + points_earned)
    new_weekly = max(0, weekly_pts + points_earned)
    new_monthly = max(0, monthly_pts + points_earned)
    new_sem1 = max(0, sem1_pts + points_earned)
    new_total = max(0, total_pts + points_earned)

    # 4. Cập nhật vào Cơ sở dữ liệu
    cursor.execute("""
        UPDATE user_gamification
        SET daily_points = ?,
            weekly_points = ?,
            monthly_points = ?,
            semester1_points = ?,
            total_points = ?,
            current_streak = ?,
            last_active_date = ?
        WHERE user_id = ?
    """, (new_daily, new_weekly, new_monthly, new_sem1, new_total, streak, today_str, user_id))
    
    conn.commit()
    conn.close()

def record_student_answer(user_id, lesson_id, question_id, subject_id, is_correct, points_correct, points_penalty):
    """
    Xử lý cộng/trừ điểm tích lũy, tính Streak ngày đăng nhập và lưu nhật ký làm bài.
    - Đúng: +points_correct (mặc định +10đ)
    - Sai: -points_penalty (mặc định -5đ)
    """
    conn = get_connection()
    #init_gamification_tables(conn)
    cursor = conn.cursor()

    # Lấy thông tin Gamification hiện tại của học sinh
    cursor.execute("SELECT * FROM user_gamification WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()

    today_str = date.today().isoformat()
    points = points_correct if is_correct else -points_penalty

    if not user_data:
        # Khởi tạo bản ghi mới
        total_p = max(0, points)
        daily_p = max(0, points)
        weekly_p = max(0, points)
        monthly_p = max(0, points)
        sem1_p = max(0, points)
        streak = 1
        tot_q = 1
        corr_q = 1 if is_correct else 0

        cursor.execute("""
            INSERT INTO user_gamification 
            (user_id, total_points, daily_points, weekly_points, monthly_points, semester1_points, current_streak, last_active_date, total_questions_answered, correct_questions_answered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, total_p, daily_p, weekly_p, monthly_p, sem1_p, streak, today_str, tot_q, corr_q))
    else:
        # Cập nhật bản ghi sẵn có
        last_date_str = user_data['last_active_date']
        streak = user_data['current_streak']

        if last_date_str:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            diff_days = (date.today() - last_date).days
            if diff_days == 1:
                streak += 1  # Học liên tục các ngày
            elif diff_days > 1:
                streak = 1   # Mất chuỗi Streak
        else:
            streak = 1

        # Cập nhật điểm (không âm)        

        new_total = max(0, user_data['total_points'] + points)
        new_daily = max(0, user_data['daily_points'] + points)
        new_weekly = max(0, user_data['weekly_points'] + points)
        new_monthly = max(0, user_data['monthly_points'] + points)
        new_sem1 = max(0, user_data['semester1_points'] + points)

        new_tot_q = user_data['total_questions_answered'] + 1
        new_corr_q = user_data['correct_questions_answered'] + (1 if is_correct else 0)

        cursor.execute("""
            UPDATE user_gamification 
            SET total_points = ?, daily_points = ?, weekly_points = ?, monthly_points = ?, semester1_points = ?,
                current_streak = ?, last_active_date = ?, total_questions_answered = ?, correct_questions_answered = ?
            WHERE user_id = ?
        """, (new_total, new_daily, new_weekly, new_monthly, new_sem1, streak, today_str, new_tot_q, new_corr_q, user_id))

    # Ghi nhật ký lịch sử làm bài
    cursor.execute("""
        INSERT INTO user_answer_logs (user_id, lesson_id, question_id, subject_id, is_correct, points_awarded)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, lesson_id, question_id, subject_id, 1 if is_correct else 0, points))

    conn.commit()
    conn.close()
    return points

# ==========================================
# RENDER LESSON & MARKDOWN HELPERS
# ==========================================

# def render_lesson(content_markdown, image_path):
    # images = {}
    # if image_path:
        # try:
            # image_list = json.loads(image_path)
            # for image in image_list:
                # images[image["id"]] = image
        # except (json.JSONDecodeError, TypeError):
            # pass

    # pattern = r"\{\{IMAGE:([^}]+)\}\}"
    # parts = re.split(pattern, content_markdown or "")

    # for i, part in enumerate(parts):
        # if i % 2 == 0:
            # if part.strip():
                # st.markdown(part)
        # else:
            # image_id = part.strip()
            # image = images.get(image_id)
            # if image:
                # st.image(image["path"], caption=image.get("alt", ""))
def save_uploaded_file(uploaded_file):
    """
    Lưu file được upload từ Streamlit vào thư mục assets/images
    và trả về đường dẫn tương đối để lưu vào DB.
    """
    if uploaded_file is not None:
        file_path = os.path.join(IMAGE_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return f"assets/images/{uploaded_file.name}"
    return None

def render_lesson(content_markdown, image_path):
    images = {}

    if image_path:
        try:
            image_list = json.loads(image_path)

            for image in image_list:
                images[image["id"]] = image

        except (json.JSONDecodeError, TypeError):
            pass

    pattern = r"\{\{IMAGE:([^}]+)\}\}"

    parts = re.split(pattern, content_markdown or "")

    for i, part in enumerate(parts):

        if i % 2 == 0:
            if part.strip():
                st.markdown(part)

        else:
            image_id = part.strip()

            image = images.get(image_id)

            if image:
                st.image(
                    image["path"],
                    caption=image.get("alt", "")
                )

def extract_youtube_id(url):
    """Hàm phụ trợ lấy YouTube ID để nhúng Video trực tiếp vào Streamlit"""
    youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None

# def render_clean_markdown(markdown_text):
    # if not markdown_text:
        # return ""
    # text = markdown_text.replace('\\n', '\n')
    # text = text.replace('\\\\', '\\')
    # text = re.sub(r'([^\n])\n(#+\s)', r'\1\n\n\2', text)
    # text = re.sub(r'([^\n])\n(---)', r'\1\n\n\2', text)
    # return text
    
# def render_markdown(text):
    # if not text:
        # return ""
    # text = text.replace("\\n", "\n")
    # text = text.replace("\\\\", "\\")
    # text = re.sub(r'(?<!\\)left', r'\\left', text)
    # text = re.sub(r'(?<!\\)right', r'\\right', text)
    # text = re.sub(r'(?<!\\)neq', r'\\neq', text)
    # return text

def render_markdown_(text):
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    text = text.replace("\\\\", "\\")
    text = text.replace("\\\neq", "\\neq")
    return text

def render_student_dashboard(filter_data):
    st.markdown("""
        <style>
        h1{ color:#1976D2; }
        h2{ color:#00897B; }
        h3{ color:#FB8C00; }
        blockquote{
            background:#f8f9fa;
            border-left:6px solid #4CAF50;
            padding:12px;
            border-radius:8px;
        }
        table{ width:100%; }
        </style>
        """, unsafe_allow_html=True)
    
    if not filter_data or not filter_data.get('lesson'):
        st.info("👉 Vui lòng chọn Lớp, Môn học và Bài học từ Menu bên trái để bắt đầu.")
        return

    sel_lesson = filter_data.get('lesson')
    user_id = st.session_state.user['id']
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lessons WHERE id = ?", (sel_lesson['id'],))
    current_lesson = cursor.fetchone()

    if not current_lesson:
        st.warning("Không tìm thấy thông tin bài học.")
        conn.close()
        return

    st.header(f"📌 {current_lesson['title']}")
    st.caption(f"Chương: {current_lesson['chapter_name']} | Lớp: {filter_data['grade']['name']} | Môn: {filter_data['subject']['name']}")

    # Lấy danh sách Tài liệu & Video bổ trợ (Resources)
    cursor.execute("SELECT * FROM resources WHERE lesson_id = ?", (current_lesson['id'],))
    resources = cursor.fetchall()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📖 Tab 1: Lý Thuyết & Tài Liệu", 
        "💡 Tab 2: Củng Cố Lý Thuyết", 
        "✍️ Tab 3: Bài Tập Rèn Luyện", 
        "⏱️ Tab 4: Đề Thi Định Kỳ"
    ])

    # ==========================================
    # TAB 1: LÝ THUYẾT & TÀI LIỆU
    # ==========================================
    with tab1:
        # user_text = simple_math_editor(key="editor1", default_value="Cho $x^2 + 1 = 0$")
        # st.write("Dữ liệu nhận được từ editor:",user_text)
        # st.code(user_text)
        
        if resources:
            sub_tab_theory, sub_tab_res = st.tabs(["📄 Bài Học Lý Thuyết", f"🎥 Tài Liệu & Video Bổ Trợ ({len(resources)})"])
            
            with sub_tab_theory:
                #if current_lesson['image_path'] and os.path.exists(current_lesson['image_path']):
                #    st.image(current_lesson['image_path'], use_column_width=True)

                content = render_markdown_(current_lesson['content_markdown'])                
                render_lesson(content,current_lesson["image_path"])
                st.markdown(content)
                                
                if current_lesson['summary']:
                    st.info(f"💡 **TÓM TẮT BÀI HỌC CỐT LÕI:**\n\n{current_lesson['summary']}")

            with sub_tab_res:
                st.subheader("📁 Danh Sách Tài Liệu & Video Bổ Trợ")
                for r in resources:
                    with st.container(border=True):
                        r_type = r['resource_type']
                        r_title = r['title']
                        r_url = r['url_or_path']
                        r_desc = r['description'] or ""

                        if r_type == 'video':
                            st.markdown(f"🎥 **[VIDEO] {r_title}**")
                            if r_desc: st.caption(r_desc)
                            yt_id = extract_youtube_id(r_url)
                            if yt_id:
                                st.video(f"https://www.youtube.com/watch?v={yt_id}")
                            else:
                                st.markdown(f"🔗 [Mở liên kết Video trong thẻ mới]({r_url})")

                        elif r_type == 'document':
                            st.markdown(f"📄 **[TÀI LIỆU PDF/DOC] {r_title}**")
                            if r_desc: st.caption(r_desc)
                            st.markdown(f"📥 [Tải về / Xem tài liệu tại đây]({r_url})")

                        else:
                            st.markdown(f"🔗 **[LIÊN KẾT NGOÀI] {r_title}**")
                            if r_desc: st.caption(r_desc)
                            st.markdown(f"👉 [Truy cập liên kết]({r_url})")
        else:
            if current_lesson['image_path'] and os.path.exists(current_lesson['image_path']):
                st.image(current_lesson['image_path'], use_column_width=True)
            st.markdown(render_markdown_(current_lesson['content_markdown']))
            if current_lesson['summary']:
                st.info(f"💡 **Tóm tắt bài học:** {current_lesson['summary']}")

    # ==========================================
    # TAB 2: CỦNG CỐ LÝ THUYẾT TRẮC NGHIỆM
    # ==========================================
    with tab2:
        st.subheader("💡 Củng Cố Lý Thuyết Trắc Nghiệm")
        cursor.execute("SELECT * FROM questions WHERE lesson_id = ? AND exam_type = 'theory'", (current_lesson['id'],))
        theory_qs = cursor.fetchall()
        
        if not theory_qs:
            st.info("Chưa có câu hỏi củng cố lý thuyết cho bài học này.")
        else:
            total_t_q = len(theory_qs)
            step_key = f"t_step_{current_lesson['id']}"
            if step_key not in st.session_state:
                st.session_state[step_key] = 0

            current_idx = st.session_state[step_key]
            
            # Thanh Tiến Trình (Progress bar)
            progress_val = (current_idx + 1) / total_t_q
            st.progress(progress_val, text=f"Câu hỏi {current_idx + 1} / {total_t_q}")

            q = theory_qs[current_idx]
            q_id = q['id']
            ans_state_key = f"ans_state_q_{q_id}"  # Khóa trạng thái đã làm của câu hỏi
            
            # Thẻ nội dung câu hỏi
            with st.container(border=True):
                if q['image_path'] and os.path.exists(f"assets/images/{q['image_path']}"):
                    width = 450
                    numbers = [int(n) for n in re.findall(r"\d+", q['image_path'])]
                    filtered_nums = [n for n in numbers if n > 50]
                    if filtered_nums:
                        width = max(filtered_nums)
                    st.image(f"assets/images/{q['image_path']}", width=width)

                question = render_markdown_(q["question_text"])
                st.markdown(f"#### **Câu {current_idx + 1}: {question}**")
                
                option_a = render_markdown_(q['option_a'])
                option_b = render_markdown_(q['option_b'])
                option_c = render_markdown_(q['option_c'])
                option_d = render_markdown_(q['option_d'])
                correct_option = render_markdown_(q['correct_option'])
                opts = [option_a, option_b, option_c, option_d]

                # NẾU CÂU HỎI ĐÃ ĐƯỢC TRẢ LỜI TRONG SESSION NÀY
                if ans_state_key in st.session_state:
                    saved_data = st.session_state[ans_state_key]
                    # Radio bị khóa (disabled), chọn sẵn đáp án đã trả lời
                    st.radio(
                        f"Chọn đáp án câu {current_idx + 1}:", 
                        opts, 
                        key=f"th_step_q_{q_id}_disabled", 
                        index=opts.index(saved_data['user_choice']) if saved_data['user_choice'] in opts else None,
                        disabled=True
                    )
                    
                    # Hiển thị lại kết quả đã đánh giá
                    if saved_data['is_correct']:
                        st.success(f"🎉 **Đã hoàn thành:** Bạn đã trả lời CHÍNH XÁC câu này (+{saved_data['pts']} điểm).")
                    else:
                        st.error(f"❌ **Đã hoàn thành:** Câu này bạn trả lời CHƯA ĐÚNG ({saved_data['pts']} điểm). Đáp án đúng là: **{q['correct_option']}**")
                    
                    if q['explanation']:
                        st.info(f"💡 **Giải thích chi tiết:** {render_markdown_(q['explanation'])}")
                        
                # NẾU CÂU HỎI CHƯA TRẢ LỜI -> CHO PHÉP LÀM BÀI
                else:
                    with st.form(key=f"form_th_q_{q_id}"):
                        user_choice = st.radio(
                            f"Chọn đáp án câu {current_idx + 1}:", 
                            opts, 
                            key=f"th_step_q_{q_id}",#key=f"th_step_q_{q['id']}", 
                            index=None
                        )
                        submitted = st.form_submit_button(f"🎯 Kiểm tra câu {current_idx + 1}")
                    
                    if submitted:
                        if user_choice is None:
                            st.warning("⚠️ Vui lòng chọn một đáp án trước khi kiểm tra!")
                        else:
                            correct_map = {'A': option_a, 'B': option_b, 'C': option_c, 'D': option_d}
                            is_correct = (user_choice == correct_map.get(correct_option))

                            # ID câu hỏi hiện tại
                            question_id = q_id #current_lesson['id']
                            # Khởi tạo trạng thái đã chấm điểm cho câu hỏi hiện tại nếu chưa có
                            if f"answered_{question_id}" not in st.session_state:
                                st.session_state[f"answered_{question_id}"] = False
                            
                            # Ghi điểm & Trừ điểm phạt
                            pts_change = record_student_answer(
                                user_id=user_id,
                                lesson_id=current_lesson['id'],
                                question_id=q['id'],
                                subject_id=filter_data['subject']['id'],
                                is_correct=is_correct,
                                points_correct=10,
                                points_penalty=5
                            )
                            # CHỈ CỘNG/TRỪ ĐIỂM NẾU CÂU HỎI NÀY CHƯA ĐƯỢC CHẤM
                            if not st.session_state[f"answered_{question_id}"]:
                                if is_correct:
                                    st.balloons()
                                    st.success(f"🎉 **Chính xác!** Bạn nhận được **+{pts_change} điểm**.")
                                    #add_points_on_correct_answer(user_id, pts_change)
                                    recalculate_user_points_from_log(user_id)

                                    # LƯU TRẠNG THÁI VÀO SESSION STATE ĐỂ KHÓA CÂU HỎI NGAY LẬP TỨC
                                    st.session_state[ans_state_key] = {
                                        'user_choice': user_choice,
                                        'is_correct': is_correct,
                                        'pts': pts_change
                                    }
                                else:
                                    st.error(f"❌ **Chưa đúng!** Bạn bị trừ **{abs(pts_change)} điểm**. Đáp án đúng là: **{q['correct_option']}**")
                                    #add_points_on_correct_answer(user_id, pts_change)
                                    recalculate_user_points_from_log(user_id)

                                    # LƯU TRẠNG THÁI VÀO SESSION STATE ĐỂ KHÓA CÂU HỎI NGAY LẬP TỨC
                                    st.session_state[ans_state_key] = {
                                        'user_choice': user_choice,
                                        'is_correct': is_correct,
                                        'pts': pts_change
                                    }
                                
                                if q['explanation']:
                                    st.info(f"💡 **Giải thích chi tiết:** {render_markdown_(q['explanation'])}")

                                # Đánh dấu câu này ĐÃ CHẤM XONG để không bị tính lại khi re-run
                                st.session_state[f"answered_{question_id}"] = True
                                # Rerun ngay lập tức để Sidebar cập nhật điểm & thanh Progress mới!
                                st.rerun()

            # Thanh Điều Hướng Next / Previous
            c_prev, c_center, c_next = st.columns([1, 2, 1])
            with c_prev:
                if current_idx > 0:
                    if st.button("⬅️ Câu Trước", key=f"prev_th_{current_lesson['id']}"):
                        st.session_state[step_key] -= 1
                        st.rerun()
            with c_center:
                if st.button("🔄 Làm lại từ câu 1", key=f"reset_th_{current_lesson['id']}"):
                    st.session_state[step_key] = 0
                    st.rerun()
            with c_next:
                if current_idx < total_t_q - 1:
                    if st.button("Câu Tiếp ➡️", key=f"next_th_{current_lesson['id']}"):
                        st.session_state[step_key] += 1
                        st.rerun()

    # ==========================================
    # TAB 3: BÀI TẬP RÈN LUYỆN (TÍCH HỢP BỘ GÕ VISUAL MATH EDITOR)
    # ==========================================
    with tab3:
        st.subheader("✍️ Bài Tập Rèn Luyện (Trắc nghiệm & Tự luận)")
        cursor.execute("SELECT * FROM questions WHERE lesson_id = ? AND exam_type = 'regular'", (current_lesson['id'],))
        practice_qs = cursor.fetchall()

        if not practice_qs:
            st.info("Chưa có bài tập rèn luyện cho bài học này.")
        else:
            total_p_q = len(practice_qs)
            step_p_key = f"p_step_{current_lesson['id']}"
            if step_p_key not in st.session_state:
                st.session_state[step_p_key] = 0

            curr_p_idx = st.session_state[step_p_key]
            st.progress((curr_p_idx + 1) / total_p_q, text=f"Bài tập {curr_p_idx + 1} / {total_p_q}")

            q = practice_qs[curr_p_idx]
            q_id = q['id']
            ans_state_key = f"ans_state_q_{q_id}"
            
            with st.container(border=True):
                question_text = render_markdown_(q["question_text"])
                st.markdown(f"#### **Câu {curr_p_idx + 1}: {question_text}**")
                
                if q['image_path'] and os.path.exists(f"assets/images/{q['image_path']}"):
                    width = 450
                    numbers = [int(n) for n in re.findall(r"\d+", q['image_path'])]
                    filtered_nums = [n for n in numbers if n > 50]
                    if filtered_nums:
                        width = max(filtered_nums)
                    st.image(f"assets/images/{q['image_path']}", width=width)

                # ------------------------------------------
                # DẠNG 1: TRẮC NGHIỆM (MCQ)
                # ------------------------------------------
                if q['question_format'] == 'mcq':
                    option_a = render_markdown_(q['option_a'])
                    option_b = render_markdown_(q['option_b'])
                    option_c = render_markdown_(q['option_c'])
                    option_d = render_markdown_(q['option_d'])
                    correct_option = render_markdown_(q['correct_option'])
                    opts = [option_a, option_b, option_c, option_d]

                    if ans_state_key in st.session_state:
                        saved_data = st.session_state[ans_state_key]
                        st.radio(
                            f"Đáp án đã chọn (Câu {curr_p_idx + 1}):", 
                            opts, 
                            key=f"pr_radio_locked_{q_id}", 
                            index=opts.index(saved_data['user_choice']) if saved_data['user_choice'] in opts else None,
                            disabled=True
                        )
                        if saved_data['is_correct']:
                            st.success(f"🎉 **Đã hoàn thành:** Bạn đã trả lời CHÍNH XÁC (+{saved_data['pts']} điểm).")
                        else:
                            st.error(f"❌ **Đã hoàn thành:** Câu này trả lời CHƯA ĐÚNG ({saved_data['pts']} điểm). Đáp án đúng: **{correct_option}**")
                        
                        if q['explanation']:
                            st.info(f"💡 **Giải thích:** {render_markdown_(q['explanation'])}")
                    else:
                        with st.form(key=f"form_pr_q_{q_id}"):
                            u_ans = st.radio(f"Chọn đáp án câu {curr_p_idx + 1}:", opts, key=f"pr_radio_active_{q_id}", index=None)
                            submitted_pr = st.form_submit_button(f"🎯 Kiểm tra câu {curr_p_idx + 1}")

                        if submitted_pr:
                            if u_ans is None:
                                st.warning("⚠️ Vui lòng chọn đáp án trước khi kiểm tra!")
                            else:
                                correct_map = {'A': option_a, 'B': option_b, 'C': option_c, 'D': option_d}
                                is_correct = (u_ans == correct_map.get(correct_option))
                                
                                pts_change = record_student_answer(
                                    user_id=user_id,
                                    lesson_id=current_lesson['id'],
                                    question_id=q_id,
                                    subject_id=filter_data['subject']['id'],
                                    is_correct=is_correct,
                                    points_correct=10,
                                    points_penalty=5
                                )
                                
                                #add_points_on_correct_answer(user_id, pts_change)
                                recalculate_user_points_from_log(user_id)
                                
                                st.session_state[ans_state_key] = {
                                    'user_choice': u_ans,
                                    'is_correct': is_correct,
                                    'pts': pts_change
                                }
                                
                                if is_correct:
                                    st.balloons()

                                st.rerun()

                # ------------------------------------------
                # DẠNG 2: TỰ LUẬN (ESSAY)
                # ------------------------------------------
                else:
                    if ans_state_key in st.session_state:
                        saved_data = st.session_state[ans_state_key]
                        st.success(f"🎉 **Đã hoàn thành nộp bài!** (+{saved_data['pts']} điểm nỗ lực)")
                        if saved_data['essay_ans']:
                            st.markdown("**Bài làm đã nộp:**")
                            st.markdown(saved_data['essay_ans'])
                            #st.latex(saved_data['essay_ans'])
                            
                        st.markdown(f"**Đáp án mẫu / Lời giải:**\n{render_markdown_(q['essay_solution'])}")
                        if q['explanation']:
                            st.info(f"💡 **Hướng dẫn chi tiết:** {render_markdown_(q['explanation'])}")
                    else:
                        st.caption("✍️ Nhập công thức / câu trả lời của bạn:")
                        essay_ans_latex = simple_math_editor(key=f"essay_step_{q_id}", height=200)
                        uploaded_file = st.file_uploader("Hoặc tải ảnh bài làm (nếu có):", type=["png", "jpg", "jpeg"])
                        
                        if st.button(f"📤 Nộp bài & Xem đáp án câu {curr_p_idx + 1}", key=f"btn_step_es_{q_id}"):
                            if not essay_ans_latex and uploaded_file is None:
                                st.warning("Vui lòng nhập nội dung bài làm hoặc tải ảnh lên.")
                            else:
                                conn = get_connection()
                                cursor = conn.cursor()
                                
                                # Lưu file ảnh nếu học sinh có upload
                                img_path = save_uploaded_file(uploaded_file) if uploaded_file else None
                                
                                # Thêm bài nộp mới vào DB
                                cursor.execute("""
                                    INSERT INTO essay_submissions (student_id, question_id, submission_type, student_answer, image_path, status)
                                    VALUES (?, ?, 'lesson', ?, ?, 'pending')
                                """, (user_id, q_id, str(essay_ans_latex), img_path))

                                conn.commit()
                                conn.close()                                
                                
                            pts_change = record_student_answer(
                                user_id=user_id,
                                lesson_id=current_lesson['id'],
                                question_id=q_id,
                                subject_id=filter_data['subject']['id'],
                                is_correct=True,
                                points_correct=15,
                                points_penalty=0
                            )
                            
                            #add_points_on_correct_answer(user_id, pts_change)
                            recalculate_user_points_from_log(user_id)
                            
                            st.session_state[ans_state_key] = {
                                'essay_ans': essay_ans_latex,
                                'pts': pts_change
                            }
                            
                            st.success("🎉 Nộp bài tự luận thành công! Vui lòng chờ giáo viên chấm điểm.")
                            st.rerun()

            # Thanh Điều Hướng Next / Previous
            cp_prev, cp_center, cp_next = st.columns([1, 2, 1])
            with cp_prev:
                if curr_p_idx > 0 and st.button("⬅️ Bài Trước", key=f"btn_prev_pr_{current_lesson['id']}_{curr_p_idx}"):
                    st.session_state[step_p_key] -= 1
                    st.rerun()
            with cp_center:
                if st.button("🔄 Làm lại từ bài 1", key=f"btn_reset_pr_{current_lesson['id']}"):
                    st.session_state[step_p_key] = 0
                    st.rerun()
            with cp_next:
                if curr_p_idx < total_p_q - 1 and st.button("Bài Tiếp ➡️", key=f"btn_next_pr_{current_lesson['id']}_{curr_p_idx}"):
                    st.session_state[step_p_key] += 1
                    st.rerun()

    # ==========================================
    # TAB 4: ĐỀ THI ĐỊNH KỲ
    # ==========================================
    with tab4:
        st.subheader("⏱️ Đề Thi Định Kỳ")
        cursor.execute("SELECT * FROM exams WHERE grade_id = ? AND subject_id = ? ORDER BY title ASC", 
                       (filter_data['grade']['id'], filter_data['subject']['id']))
        exams = cursor.fetchall()
        if not exams:
            st.info("Chưa có đề thi định kỳ cho môn học/học kỳ này.")
        else:
            sel_exam = st.selectbox("Chọn đề thi:", exams, format_func=lambda x: f"{x['title']} ({x['duration_minutes']} phút)")
            st.caption(f"⏱️ Thời gian làm bài: {sel_exam['duration_minutes']} phút")
            
            cursor.execute("SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_num ASC", (sel_exam['id'],))
            eqs = cursor.fetchall()
            
            if st.button("🚀 Bắt đầu làm bài thi", key=f"start_ex_{sel_exam['id']}"):
                st.session_state[f"exam_active_{sel_exam['id']}"] = True

            if st.session_state.get(f"exam_active_{sel_exam['id']}"):
                with st.form(f"form_exam_{sel_exam['id']}"):
                    for eq in eqs:
                        question_text_ = render_markdown_(eq["question_text"])
                        
                        if eq['image_path'] and os.path.exists(f"assets/images/{eq['image_path']}"):
                            width = 450
                            numbers = [int(n) for n in re.findall(r"\d+", eq['image_path'])]
                            filtered_nums = [n for n in numbers if n > 50]
                            if filtered_nums:
                                width = max(filtered_nums)
                            st.image(f"assets/images/{eq['image_path']}", width=width)
                        
                        st.markdown(f"**Câu {eq['question_num']} ({eq['max_score']} điểm): {question_text_}**")
                        if eq['question_type'] == 'mcq':
                            option_a = render_markdown_(eq['option_a'])
                            option_b = render_markdown_(eq['option_b'])
                            option_c = render_markdown_(eq['option_c'])
                            option_d = render_markdown_(eq['option_d'])
                            opts = [option_a, option_b, option_c, option_d]
                            st.radio(f"Đáp án câu {eq['question_num']}:", opts, key=f"ex_mcq_{eq['id']}", index=None)
                        else:                            
                            essay_ans_latex = simple_math_editor(key=f"essay_{eq['id']}",height=200)
                            uploaded_file = st.file_uploader("Hoặc tải ảnh bài làm (nếu có):", type=["png", "jpg", "jpeg"])                           
                        st.divider()
                    
                    if st.form_submit_button("Nộp Bài Thi"):                        
                        if not essay_ans_latex and uploaded_file is None:
                                st.warning("Vui lòng nhập nội dung bài làm hoặc tải ảnh lên.")
                        else:
                            conn = get_connection()
                            cursor = conn.cursor()
                            
                            # Lưu file ảnh nếu học sinh có upload
                            img_path = save_uploaded_file(uploaded_file) if uploaded_file else None
                            
                            # Thêm bài nộp mới vào DB
                            cursor.execute("""
                                INSERT INTO essay_submissions (student_id, exam_id, question_id, submission_type, student_solution, image_path, status)
                                VALUES (?, ?, ?, 'exam', ?, ?, 'pending')
                            """, (user_id, eq['exam_id'], eq['id'], essay_ans_latex, img_path))
                            conn.commit()
                            conn.close()                                
                            st.rerun()
                        st.success("🎉 Bạn đã nộp bài thi thành công! Hệ thống sẽ chấm điểm và phản hồi sau.")

    conn.close()