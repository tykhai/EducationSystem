import os
import re
import time
from datetime import datetime
import streamlit as st
from github import Github, GithubException

# Đường dẫn chuẩn tới file secrets và database
SECRETS_PATH = ".streamlit/secrets.toml"
LOCAL_DB_PATH = "data/database.db"
BACKUP_FOLDER_IN_REPO = "backups"

# ==========================================
# BỘ HÀM ĐỌC / GHI CẤU HÌNH TRỰC TIẾP FILE SECRETS
# ==========================================
def get_backup_enabled_status() -> bool:
    """Đọc trạng thái ENABLE_GITHUB_BACKUP trực tiếp từ file .streamlit/secrets.toml"""
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r'ENABLE_GITHUB_BACKUP\s*=\s*(true|false)', content, re.IGNORECASE)
                if match:
                    return match.group(1).lower() == "true"
        except Exception:
            pass
    return False

def set_backup_enabled_status(enabled: bool):
    """Cập nhật hoặc thêm biến ENABLE_GITHUB_BACKUP vào file .streamlit/secrets.toml"""
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    
    content = ""
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            content = f.read()

    new_val_str = f"ENABLE_GITHUB_BACKUP = {str(enabled).lower()}"

    if re.search(r'ENABLE_GITHUB_BACKUP\s*=', content, re.IGNORECASE):
        # Thay thế dòng hiện có
        new_content = re.sub(
            r'ENABLE_GITHUB_BACKUP\s*=\s*(true|false)',
            new_val_str,
            content,
            flags=re.IGNORECASE
        )
    else:
        # Thêm mới vào đầu file
        new_content = new_val_str + "\n" + content

    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

def get_github_repo():
    """Khởi tạo kết nối GitHub Repo từ Secrets với báo lỗi chi tiết"""
    # Kiểm tra key có tồn tại trong st.secrets hay không
    missing_keys = []
    if "GITHUB_TOKEN" not in st.secrets:
        missing_keys.append("GITHUB_TOKEN")
    if "GITHUB_REPO" not in st.secrets:
        missing_keys.append("GITHUB_REPO")

    if missing_keys:
        st.error(f"❌ Thiếu thông tin cấu hình: {', '.join(missing_keys)} trong `.streamlit/secrets.toml`")
        # In ra danh sách key đang có để debug
        existing_keys = list(st.secrets.keys()) if hasattr(st, "secrets") else []
        st.info(f"🔍 Các key Streamlit đang đọc được: `{existing_keys}`")
        return None

    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["GITHUB_REPO"]
        g = Github(token)
        return g.get_repo(repo_name)
    except Exception as e:
        st.error(f"Lỗi khi kết nối tới Repository: {e}")
        return None

# ==========================================
# CHỨC NĂNG PULL & PUSH
# ==========================================
def pull_latest_db_from_github() -> bool:
    """Tải file database mới nhất từ thư mục backups/ trên GitHub về máy cục bộ"""
    if not get_backup_enabled_status():
        return False

    repo = get_github_repo()
    if not repo:
        return False

    try:
        contents = repo.get_contents(BACKUP_FOLDER_IN_REPO)
        db_files = [
            f for f in contents 
            if f.name.startswith("database_") and f.name.endswith(".db")
        ]
        
        if not db_files:
            st.warning("⚠️ Không tìm thấy bản backup nào trên GitHub.")
            return False

        # File có timestamp lớn nhất là file mới nhất
        db_files.sort(key=lambda x: x.name, reverse=True)
        latest_file = db_files[0]

        os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)

        with open(LOCAL_DB_PATH, "wb") as f:
            f.write(latest_file.decoded_content)

        st.toast(f"✅ Đã Kéo (Pull) bản DB mới nhất: {latest_file.name}", icon="📥")
        return True

    except Exception as e:
        st.error(f"Lỗi khi Pull database từ GitHub: {e}")
        return False

def push_db_to_github(commit_message: str = "Auto backup database") -> bool:
    """Đẩy bản sao lưu mới lên GitHub dưới dạng backups/database_YYYYMMDD_HHMMSS.db"""
    if not get_backup_enabled_status():
        return False

    if not os.path.exists(LOCAL_DB_PATH):
        st.error(f"File database cục bộ không tồn tại ở `{LOCAL_DB_PATH}`")
        return False

    repo = get_github_repo()
    if not repo:
        return False

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_file_path = f"{BACKUP_FOLDER_IN_REPO}/database_{timestamp}.db"

        with open(LOCAL_DB_PATH, "rb") as f:
            content = f.read()

        repo.create_file(
            path=repo_file_path,
            message=f"{commit_message} [{timestamp}]",
            content=content
        )

        st.toast(f"✅ Đã Đẩy (Push) bản backup lên GitHub!", icon="🚀")
        return True

    except Exception as e:
        st.error(f"Lỗi khi Push database lên GitHub: {e}")
        return False

def check_and_auto_push():
    """Kiểm tra khoảng thời gian để tự động Push (Interval Check)"""
    if not get_backup_enabled_status():
        return

    interval_hours = st.secrets.get("BACKUP_INTERVAL_HOURS", 4)
    interval_seconds = interval_hours * 3600

    if "last_github_push_time" not in st.session_state:
        st.session_state.last_github_push_time = time.time()
        return

    current_time = time.time()
    if current_time - st.session_state.last_github_push_time >= interval_seconds:
        if push_db_to_github(commit_message="Interval auto-backup"):
            st.session_state.last_github_push_time = current_time

# ==========================================
# GIAO DIỆN QUẢN TRỊ ADMIN (ADMIN VIEW UI)
# ==========================================
def render_admin_github_backup_ui():
    """Giao diện điều khiển trong màn hình Admin"""
    st.subheader("📦 Đồng Bộ & Backup Database GitHub")

    # Lấy trạng thái hiện tại từ file secrets.toml
    is_currently_enabled = get_backup_enabled_status()

    # Nút gạt Bật/Tắt trực tiếp trên Giao diện
    toggle_status = st.toggle(
        "Bật tính năng Tự động Backup lên GitHub",
        value=is_currently_enabled,
        help="Lưu trực tiếp cấu hình vào file .streamlit/secrets.toml"
    )

    # Nếu trạng thái trên UI thay đổi so với file -> Ghi đè vào file secrets.toml
    if toggle_status != is_currently_enabled:
        set_backup_enabled_status(toggle_status)
        st.toast(f"Đã {'BẬT' if toggle_status else 'TẮT'} tính năng Backup GitHub!", icon="⚙️")
        st.rerun()

    if not toggle_status:
        st.info("🔴 Tính năng Backup GitHub đang TẮT.")
        return

    st.success("🟢 Tính năng Backup GitHub đang BẬT")
    st.write(f"📂 **Đường dẫn DB Cục bộ:** `{LOCAL_DB_PATH}`")
    st.write(f"⏱️ **Tần suất tự động Push:** `{st.secrets.get('BACKUP_INTERVAL_HOURS', 4)} giờ/lần`")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 Pull bản mới nhất từ GitHub"):
            with st.spinner("Đang tải dữ liệu từ GitHub..."):
                if pull_latest_db_from_github():
                    st.success("Đã cập nhật database mới nhất!")

    with col2:
        if st.button("📤 Push bản backup ngay bây giờ"):
            with st.spinner("Đang tải dữ liệu lên GitHub..."):
                if push_db_to_github(commit_message="Manual backup from Admin Panel"):
                    st.session_state.last_github_push_time = time.time()
                    st.success("Đã sao lưu thành công!")