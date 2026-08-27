import streamlit as st
import streamlit.components.v1 as components
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from services.db_connection import init_db
from auth.auth_service import login_user, register_user
from modules.sidebar import render_student_sidebar
from modules.admin_views import render_admin_dashboard
from modules.student_views import render_student_dashboard
from modules.teacher_views import render_teacher_grading_dashboard

st.set_page_config(page_title="Hệ Thống Học Tập THCS & THPT", page_icon="🎓", layout="wide")

if "db_inited" not in st.session_state:
    init_db()
    st.session_state.db_inited = True

if "user" not in st.session_state:
    st.session_state.user = None

# ==========================================
# 1. GIAO DIỆN ĐĂNG NHẬP / ĐĂNG KÝ
# ==========================================
if not st.session_state.user:
    st.title("🎓 Hệ Thống Học Tập Bổ Trợ THCS & THPT")
    tab_login, tab_reg = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký tài khoản"])
    
    with tab_login:
        with st.form("login_form"):
            u_input = st.text_input("Tên đăng nhập", key="login_user")
            p_input = st.text_input("Mật khẩu", type="password", key="login_pwd")
            btn_login = st.form_submit_button("Đăng nhập", use_container_width=True)
            
            if btn_login:
                u, msg = login_user(u_input, p_input)
                if u:
                    st.session_state.user = u
                    st.rerun()
                else:
                    st.error(msg)

        components.html(
            """
            <script>
                const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                if (inputs.length > 0) { inputs[0].focus(); }
            </script>
            """,
            height=0
        )            

    with tab_reg:
        with st.form("reg_form"):
            r_u = st.text_input("Tên đăng nhập mới", key="reg_user")
            r_p = st.text_input("Mật khẩu", type="password", key="reg_pwd")
            r_name = st.text_input("Họ và tên", key="reg_name")
            r_email = st.text_input("Email (không bắt buộc)", key="reg_email")
            btn_reg = st.form_submit_button("Tạo tài khoản", use_container_width=True)

            if btn_reg:
                ok, msg = register_user(r_u, r_p, r_name, r_email)
                if ok: st.success(msg)
                else: st.error(msg)

# ==========================================
# 2. ĐÃ ĐĂNG NHẬP (DIEU HƯỚNG THEO ROLE)
# ==========================================
else:
    user_id = st.session_state.user['id']
    filters = render_student_sidebar(user_id)

    if st.session_state.user['role'] == 'admin':
        render_admin_dashboard()
    elif st.session_state.user['role'] == 'teacher':
    # Render giao diện chấm điểm & quản lý dành cho Giáo viên
        render_teacher_grading_dashboard(user_id,filters)
    else:
        #user_id = st.session_state.user['id']
        #filter_data = render_student_sidebar(user_id)
        render_student_dashboard(filters)