# modules/student_views.py
import streamlit as st
import os
import streamlit.components.v1 as components
import re
from services.db_connection import get_connection
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
from components.math_editor import simple_math_editor

def extract_youtube_id(url):
    """Hàm phụ trợ lấy YouTube ID để nhúng Video trực tiếp vào Streamlit"""
    youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None

def render_clean_markdown(markdown_text):
    if not markdown_text:
        return ""
    text = markdown_text.replace('\\n', '\n')
    text = text.replace('\\\\', '\\')
    text = re.sub(r'([^\n])\n(#+\s)', r'\1\n\n\2', text)
    text = re.sub(r'([^\n])\n(---)', r'\1\n\n\2', text)
    return text
    
def render_markdown(text):
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    text = text.replace("\\\\", "\\")
    text = re.sub(r'(?<!\\)left', r'\\left', text)
    text = re.sub(r'(?<!\\)right', r'\\right', text)
    text = re.sub(r'(?<!\\)neq', r'\\neq', text)
    return text

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
        if resources:
            sub_tab_theory, sub_tab_res = st.tabs(["📄 Bài Học Lý Thuyết", f"🎥 Tài Liệu & Video Bổ Trợ ({len(resources)})"])
            
            with sub_tab_theory:
                if current_lesson['image_path'] and os.path.exists(current_lesson['image_path']):
                    st.image(current_lesson['image_path'], use_column_width=True)
                    
                content = render_markdown(current_lesson['content_markdown'])                
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
            st.markdown(render_markdown(current_lesson['content_markdown']))
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
            for idx, q in enumerate(theory_qs, 1):
                question = render_markdown(q["question_text"])
                st.markdown(f"**Câu {idx}: {question}**")
                option_a = render_markdown_(q['option_a'])
                option_b = render_markdown_(q['option_b'])
                option_c = render_markdown_(q['option_c'])
                option_d = render_markdown_(q['option_d'])
                correct_option = render_markdown_(q['correct_option'])
                opts = [option_a, option_b, option_c, option_d]
                user_choice = st.radio(f"Chọn đáp án câu {idx}:", opts, key=f"th_q_{q['id']}", index=None)
                if st.button(f"Kiểm tra câu {idx}", key=f"btn_th_{q['id']}"):
                    correct_map = {'A': option_a, 'B': option_b, 'C': option_c, 'D': option_d}
                    if user_choice == correct_map.get(correct_option):
                        st.success("🎉 Chính xác!")
                    else:
                        st.error(f"❌ Chưa đúng! Đáp án đúng là: {q['correct_option']}")
                    if q['explanation']:
                        st.info(f"💡 Giải thích: {q['explanation']}")
                st.divider()

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
            for idx, q in enumerate(practice_qs, 1):
                question_text = render_markdown(q["question_text"])
                st.markdown(f"**Câu {idx}: {question_text}**")
                
                # Hiển thị ảnh câu hỏi nếu có
                if q.get('question_image') and os.path.exists(q['question_image']):
                    st.image(q['question_image'], width=400)

                if q['question_format'] == 'mcq':
                    option_a = render_markdown_(q['option_a'])
                    option_b = render_markdown_(q['option_b'])
                    option_c = render_markdown_(q['option_c'])
                    option_d = render_markdown_(q['option_d'])
                    correct_option = render_markdown_(q['correct_option'])
                    explanation = render_markdown_(q['explanation'])
                    opts = [option_a, option_b, option_c, option_d]
                    u_ans = st.radio(f"Chọn đáp án câu {idx}:", opts, key=f"pr_q_{q['id']}", index=None)
                    if st.button(f"Kiểm tra câu {idx}", key=f"btn_pr_{q['id']}"):
                        correct_map = {'A': option_a, 'B': option_b, 'C': option_c, 'D': option_d}
                        if u_ans == correct_map.get(correct_option):
                            st.success("🎉 Chính xác!")
                        else:
                            st.error(f"❌ Chưa đúng! Đáp án đúng là: {correct_option}")
                        if q['explanation']:
                            st.info(f"💡 Giải thích: {explanation}")
                else:
                    st.caption("✍️ Nhập công thức / câu trả lời của bạn:")
                    
                    # TÍCH HỢP BỘ GÕ CONG THỨC VISUAL MATH EDITOR
                    #essay_ans_latex = visual_math_editor(key=f"essay_{q['id']}")
                    #1. Visual_math_editor
                    #essay_ans_latex = visual_math_editor(key=f"essay_{q['id']}")
                    #2. Textarea_preview
                    #essay_ans_latex = textarea_preview(key=f"essay_{q['id']}",default_value="",height=220)
                    #st.write("Dữ liệu LaTeX:")
                    #st.code(essay_ans_latex)
                    #3. Textarea_toolbar
                    #essay_ans_latex = textarea_toolbar(key=f"essay_{q['id']}", height=200)
                    #st.write("Dữ liệu LaTeX:",essay_ans_latex)
                    #4. Simple_math_editor
                    essay_ans_latex = simple_math_editor(key=f"essay_{q['id']}",height=200)
                    #5. Latex_editor
                    #essay_ans_latex = latex_editor(key=f"formula_{q['id']}")
                    #6. Equation_editor
                    #essay_ans_latex = equation_editor(key=f"equation_{q['id']}")
                    
                    if st.button(f"Nộp bài & Xem đáp án câu {idx}", key=f"btn_es_{q['id']}"):
                        if essay_ans_latex:
                            st.markdown("**Công thức bạn vừa nhập:**")
                            st.latex(essay_ans_latex)
                        
                        essay_solution = render_markdown_(q['essay_solution'])
                        explanation = render_markdown_(q['explanation'])
                        
                        st.markdown(f"**Đáp án mẫu:**\n{essay_solution}")
                        if q['explanation']:
                            st.info(f"💡 Hướng dẫn chi tiết: {explanation}")
                        
                        # Hiển thị explanation_image mới bổ sung nếu có
                        if q.get('explanation_image') and os.path.exists(q['explanation_image']):
                            st.image(q['explanation_image'], caption="Hình minh họa lời giải", width=450)

                st.divider()

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
                        question_text_ = render_markdown(eq["question_text"])
                        
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
                            # Tích hợp Math Editor cho câu hỏi tự luận trong đề thi
                            # TÍCH HỢP BỘ GÕ CONG THỨC VISUAL MATH EDITOR
                            #essay_ans_latex = visual_math_editor(key=f"essay_{q['id']}")
                            #1. Visual_math_editor
                            #essay_ans_latex = visual_math_editor(key=f"essay_{q['id']}")
                            #2. Textarea_preview
                            #essay_ans_latex = textarea_preview(key=f"essay_{q['id']}",default_value="",height=220)
                            #3. Textarea_toolbar
                            #essay_ans_latex = textarea_toolbar(key=f"essay_{q['id']}", height=200)
                            #4. Simple_math_editor
                            essay_ans_latex = simple_math_editor(key=f"essay_{q['id']}",height=200)
                            #5. Latex_editor
                            #essay_ans_latex = latex_editor(key=f"formula_{q['id']}")
                            #6. Equation_editor
                            #essay_ans_latex = equation_editor(key=f"equation_{q['id']}")
                        st.divider()
                    
                    if st.form_submit_button("Nộp Bài Thi"):
                        st.success("🎉 Bạn đã nộp bài thi thành công! Hệ thống sẽ chấm điểm và phản hồi sau.")

    conn.close()