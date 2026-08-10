-- edu_app/data/schema.sql
PRAGMA foreign_keys = ON;

-- 1. Bảng Người Dùng
CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            role TEXT CHECK(role IN ('admin', 'student')) NOT NULL DEFAULT 'student',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng Lớp, Môn, Học kỳ
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS semesters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE
);

-- 3. Bài Học & Lý Thuyết (Có hỗ trợ Hình ảnh bài học)
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_id INTEGER REFERENCES grades(id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    semester_id INTEGER REFERENCES semesters(id) ON DELETE CASCADE,
    chapter_name TEXT NOT NULL,
    title TEXT NOT NULL,
    content_markdown TEXT,
    summary TEXT,
    image_path TEXT, -- Đường dẫn ảnh minh họa bài học (ví dụ: assets/images/toan8_bai1.png)
    order_index INTEGER DEFAULT 1
);

-- 4. Ngân Hàng Câu Hỏi & Bài Tập (Hỗ trợ cả Trắc Nghiệm 'mcq' và Tự Luận 'essay')
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    question_format TEXT CHECK(question_format IN ('mcq', 'essay')) NOT NULL DEFAULT 'mcq', -- Dạng câu hỏi: mcq hoặc essay
    exam_type TEXT CHECK(exam_type IN ('theory', 'regular', 'mid_hk1', 'final_hk1', 'mid_hk2', 'final_hk2')) DEFAULT 'regular',
    question_text TEXT NOT NULL, -- Nội dung đề bài (Hỗ trợ Markdown & LaTeX)
    image_path TEXT, -- Đường dẫn ảnh minh họa câu hỏi / hình vẽ hình học / sơ đồ
    
    -- Dùng cho Trắc Nghiệm (mcq)
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_option TEXT CHECK(correct_option IN ('A', 'B', 'C', 'D')),
    
    -- Dùng cho Tự Luận (essay) & Lời giải chi tiết
    essay_solution TEXT, -- Đáp án mẫu & Thang điểm chi tiết cho học sinh tự đối chiếu
    image_explanation_path TEXT, -- Đường dẫn ảnh minh họa đáp án / hình vẽ hình học / sơ đồ
    explanation TEXT     -- Giải thích / Gợi ý chung
);

-- 5. Lưu Lời Giải & Kết Quả Tự Chấm Của Học Sinh
CREATE TABLE IF NOT EXISTS student_essay_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    student_solution TEXT NOT NULL, -- Lời giải học sinh gõ (Markdown/LaTeX)
    self_score REAL,        -- Điểm học sinh tự chấm (ví dụ: 8.5/10)
    self_eval_notes TEXT,           -- Ghi chú/Đánh giá mức độ hiểu bài của học sinh
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Lưu Kết Quả Bài Trắc Nghiệm
CREATE TABLE IF NOT EXISTS student_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    exam_type TEXT DEFAULT 'regular',
    score REAL NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7.BẢNG ĐỀ THI ĐỊNH KỲ (MỚI)
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    grade_id INTEGER,
    subject_id INTEGER,
    semester_id INTEGER,
    duration_minutes INTEGER DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grade_id) REFERENCES grades (id),
    FOREIGN KEY (subject_id) REFERENCES subjects (id),
    FOREIGN KEY (semester_id) REFERENCES semesters (id)
);


-- 8.BẢNG CÂU HỎI TRONG ĐỀ THI (MỚI - Hỗ trợ MCQ & ESSAY)
CREATE TABLE IF NOT EXISTS exam_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    question_type TEXT CHECK(question_type IN ('mcq', 'essay')),
    question_num INTEGER,
    question_text TEXT NOT NULL,
    image_path TEXT,
    option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT,
    correct_option TEXT,
    essay_solution TEXT,
    max_score REAL DEFAULT 1.0,
    explanation TEXT,
    image_explanation_path TEXT, -- Đường dẫn ảnh minh họa đáp án / hình vẽ hình học / sơ đồ
    FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
);

-- 9.Bảng lưu trữ Tài liệu đọc thêm & Video bài giảng
CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER,
        resource_type TEXT CHECK(resource_type IN ('video', 'document', 'link')),
        title TEXT NOT NULL,
        url_or_path TEXT NOT NULL,
        description TEXT,
        FOREIGN KEY (lesson_id) REFERENCES lessons(id)
);

-- 10.Bảng Phân quyền (Roles)
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role_type TEXT NOT NULL, -- 'student' hoặc 'admin'
    -- Lưu danh sách ID được phép truy cập (Ví dụ: "8,9" hoặc JSON)
    allowed_grades TEXT,     -- Ví dụ: "8" (Lớp 8)
    allowed_subjects TEXT,   -- Ví dụ: "math,physics" (Toán, Lý)
    allowed_semesters TEXT,  -- Ví dụ: "hk1"
    allowed_tabs TEXT,       -- Dành cho Admin: "tab_import_lesson,tab_import_exam,tab_manage_users"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes tối ưu truy vấn
CREATE INDEX IF NOT EXISTS idx_lessons_lookup ON lessons(grade_id, subject_id, semester_id);
CREATE INDEX IF NOT EXISTS idx_questions_lesson ON questions(lesson_id);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(exam_type, question_format);