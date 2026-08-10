# components/math_editor.py
"""
math_editor.py
=========================================================
Bộ công cụ nhập văn bản + công thức cho Streamlit.

Có 5 chế độ:
1. latex_editor
   - MathLive editor.
   - Phù hợp khi câu trả lời chủ yếu là công thức.
   - Không phải lựa chọn tốt nhất cho câu trả lời có nhiều chữ.

2. textarea_toolbar
   - Textarea thông thường + thanh nút chèn LaTeX.
   - Phù hợp nhất cho học sinh: gõ chữ bình thường, chèn công thức khi cần.

3. textarea_preview
   - Textarea + toolbar + preview công thức.
   - Khuyến nghị cho bài tự luận.

4. equation_editor
   - MathLive nâng cao.
   - Có bàn phím toán học ảo, kéo/chọn/chỉnh sửa công thức.

5. simple_math_editor
   - Công cụ đơn giản tự xây dựng.
   - Có text + công thức cơ bản + preview.
   - Không phụ thuộc MathLive cho thao tác nhập chính.

Lưu ý về dấu backslash:
- Trong Python string: "\\\\dfrac{1}{2}"
- Trong JSON: "\\\\dfrac{1}{2}"
- Giá trị LaTeX thực tế truyền cho renderer vẫn là "\\dfrac{1}{2}".
- Hàm latex_for_json() dùng để chuẩn hóa khi xuất JSON.
"""
from __future__ import annotations
import html
import json
import re
import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# 1. CÁC HÀM CHUẨN HÓA LATEX
# ============================================================

def latex_for_json(value: str) -> str:
    """
    Chuẩn hóa chuỗi để đưa vào JSON.

    Ví dụ:
        "\\dfrac{1}{2}"
    sẽ được json.dumps() thành:
        "\\\\dfrac{1}{2}"

    Không nên tự replace thêm dấu \\ nếu sau đó còn dùng json.dumps(),
    vì sẽ dễ bị nhân đôi nhiều lần.
    """
    return "" if value is None else str(value)


def json_dumps_latex(data, ensure_ascii=False, indent=2) -> str:
    """Xuất JSON đúng chuẩn, tự escape dấu backslash."""
    return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)


def normalize_latex(value: str) -> str:
    """
    Chuẩn hóa nhẹ dữ liệu LaTeX.

    Mục tiêu:
    - giữ nguyên công thức hợp lệ;
    - tránh việc người dùng copy dữ liệu JSON rồi đưa thẳng vào renderer
      làm mất một lớp backslash.
    """
    if value is None:
        return ""

    value = str(value)

    # Nếu dữ liệu có dạng JSON escaped như "\\dfrac", Python thường đã
    # chuyển thành "\dfrac" khi json.loads(). Không cần replace tiếp.
    # Chỉ xử lý một số trường hợp người dùng nhập \\ bằng tay.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value


# ============================================================
# 2. LATEX EDITOR - MATHLIVE
# ============================================================

def latex_editor(
    key: str = "latex_editor",
    default_value: str = "",
    height: int = 210,
):
    """
    MathLive editor.

    Dùng khi học sinh chủ yếu nhập công thức.
    Trả về chuỗi LaTeX.
    """
    safe_key = html.escape(str(key), quote=True)
    safe_value = html.escape(default_value or "")

    html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">

<script src="https://unpkg.com/mathlive"></script>

<style>
html, body {{
    margin:0;
    padding:0;
    background:transparent;
    font-family:Arial,sans-serif;
}}

math-field {{
    display:block;
    width:100%;
    min-height:58px;
    box-sizing:border-box;
    padding:10px 12px;
    font-size:1.25rem;
    border:1px solid #bbb;
    border-radius:7px;
    background:white;
}}

math-field:focus-within {{
    border-color:#1976d2;
    box-shadow:0 0 0 2px rgba(25,118,210,.12);
}}
</style>
</head>

<body>
<math-field
    id="{safe_key}"
    virtual-keyboard-mode="onfocus"
>{safe_value}</math-field>

<script>
const mf = document.getElementById("{safe_key}");

function send(value) {{
    window.parent.postMessage(
        {{
            isStreamlitMessage:true,
            type:"streamlit:setComponentValue",
            value:value
        }},
        "*"
    );
}}

mf.addEventListener("input", () => send(mf.value));

window.addEventListener("load", () => {{
    send(mf.value);
}});
</script>
</body>
</html>
"""

    return components.html(
        html_code,
        height=height,
        scrolling=False,
        key=key,
    )


# ============================================================
# 3. TEXTAREA + TOOLBAR
# ============================================================

_SIMPLE_BUTTONS = [
    ("½", r"\frac{□}{□}"),
    ("√", r"\sqrt{□}"),
    ("x²", r"x^{□}"),
    ("x₁", r"x_{□}"),
    ("×", r"\times"),
    ("÷", r"\div"),
    ("±", r"\pm"),
    ("≤", r"\le"),
    ("≥", r"\ge"),
    ("≠", r"\ne"),
    ("→", r"\rightarrow"),
    ("π", r"\pi"),
    ("α", r"\alpha"),
    ("β", r"\beta"),
    ("°", r"^\circ"),
]

_ADVANCED_BUTTONS = [
    ("sin", r"\sin(□)"),
    ("cos", r"\cos(□)"),
    ("tan", r"\tan(□)"),
    ("log", r"\log(□)"),
    ("ln", r"\ln(□)"),
    ("∑", r"\sum_{□}^{□}"),
    ("lim", r"\lim_{□}"),
    ("∞", r"\infty"),
    ("∫", r"\int"),
    ("→", r"\rightarrow"),
    ("⇔", r"\Leftrightarrow"),
]


def _toolbar_html(buttons) -> str:
    items = []
    for label, latex in buttons:
        items.append(
            f'<button type="button" class="latex-btn" '
            f'data-latex="{html.escape(latex, quote=True)}">{html.escape(label)}</button>'
        )
    return "".join(items)


def textarea_toolbar(
    key: str = "textarea_toolbar",
    default_value: str = "",
    height: int = 260,
    advanced: bool = False,
):
    """
    Textarea + toolbar.

    Đây là lựa chọn khuyến nghị nếu câu trả lời có cả chữ và công thức.
    """
    buttons = _SIMPLE_BUTTONS + (_ADVANCED_BUTTONS if advanced else [])
    toolbar = _toolbar_html(buttons)

    safe_key = html.escape(str(key), quote=True)
    safe_value = html.escape(default_value or "")

    html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">

<style>
* {{ box-sizing:border-box; }}

html,body {{
    margin:0;
    padding:0;
    background:transparent;
    font-family:Arial,sans-serif;
}}

.wrapper {{
    width:100%;
}}

.toolbar {{
    display:flex;
    flex-wrap:wrap;
    gap:4px;
    padding:5px;
    margin-bottom:5px;
    border:1px solid #ddd;
    border-radius:6px;
    background:#f7f7f7;
}}

.latex-btn {{
    border:1px solid #ccc;
    background:white;
    border-radius:5px;
    padding:4px 8px;
    cursor:pointer;
    font-size:13px;
}}

.latex-btn:hover {{
    background:#eaf3ff;
    border-color:#6ba8e8;
}}

textarea {{
    width:100%;
    resize:vertical;
    min-height:130px;
    border:1px solid #bbb;
    border-radius:7px;
    padding:9px;
    font-size:15px;
    line-height:1.5;
    font-family:Consolas,monospace;
    background:white;
    outline:none;
}}

textarea:focus {{
    border-color:#1976d2;
}}

.note {{
    margin-top:4px;
    color:#777;
    font-size:11px;
}}
</style>
</head>

<body>
<div class="wrapper">

<div class="toolbar">
{toolbar}
</div>

<textarea id="{safe_key}" placeholder="Gõ câu trả lời bằng chữ. Khi cần, bấm nút công thức...">{safe_value}</textarea>

<div class="note">
Có thể gõ chữ bình thường và chèn LaTeX vào cùng một câu.
</div>

</div>

<script>
const ta = document.getElementById("{safe_key}");

function send() {{
    window.parent.postMessage(
        {{
            isStreamlitMessage:true,
            type:"streamlit:setComponentValue",
            value:ta.value
        }},
        "*"
    );
}}

document.querySelectorAll(".latex-btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
        const latex = btn.dataset.latex;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const selected = ta.value.substring(start, end);

        let insert = latex.replaceAll("□", selected || "");

        ta.value =
            ta.value.substring(0, start) +
            insert +
            ta.value.substring(end);

        const pos = start + insert.length;
        ta.focus();
        ta.setSelectionRange(pos, pos);

        send();
    }});
}});

ta.addEventListener("input", send);

window.addEventListener("load", send);
</script>

</body>
</html>
"""

    return components.html(
        html_code,
        height=height,
        scrolling=False,
        key=key,
    )


# ============================================================
# 4. TEXTAREA + TOOLBAR + PREVIEW
# ============================================================

def textarea_preview(
    key: str = "textarea_preview",
    default_value: str = "",
    height: int = 390,
    advanced: bool = False,
):
    """
    Textarea + toolbar + preview.

    Đây là lựa chọn KHUYẾN NGHỊ cho bài tự luận:
        Theo giả thiết ta có:
        \\frac{x+1}{x-2} = 3
        Suy ra...
    """
    buttons = _SIMPLE_BUTTONS + (_ADVANCED_BUTTONS if advanced else [])
    toolbar = _toolbar_html(buttons)

    safe_key = html.escape(str(key), quote=True)
    safe_value = html.escape(default_value or "")

    html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">

<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css">

<script defer
        src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.js">
</script>

<style>
* {{ box-sizing:border-box; }}

html,body {{
    margin:0;
    padding:0;
    background:transparent;
    font-family:Arial,sans-serif;
}}

.toolbar {{
    display:flex;
    flex-wrap:wrap;
    gap:4px;
    padding:5px;
    border:1px solid #ddd;
    border-radius:6px;
    background:#f7f7f7;
}}

.latex-btn {{
    border:1px solid #ccc;
    background:white;
    border-radius:5px;
    padding:4px 8px;
    cursor:pointer;
    font-size:13px;
}}

.latex-btn:hover {{
    background:#eaf3ff;
}}

textarea {{
    width:100%;
    height:135px;
    margin-top:5px;
    resize:vertical;
    border:1px solid #bbb;
    border-radius:7px;
    padding:9px;
    font-size:15px;
    line-height:1.5;
    font-family:Consolas,monospace;
}}

.preview-title {{
    margin-top:7px;
    font-size:12px;
    color:#666;
    font-weight:bold;
}}

.preview {{
    min-height:70px;
    margin-top:4px;
    padding:10px;
    border:1px solid #ddd;
    border-radius:7px;
    background:#fff;
    white-space:pre-wrap;
    overflow:auto;
}}

.raw {{
    margin-top:4px;
    color:#888;
    font-size:11px;
}}
</style>
</head>

<body>

<div class="toolbar">
{toolbar}
</div>

<textarea id="{safe_key}" placeholder="Ví dụ: Theo giả thiết ta có: \\frac{{x+1}}{{x-2}} = 3">{safe_value}</textarea>

<div class="preview-title">Xem trước</div>
<div id="preview" class="preview"></div>

<script>
const ta = document.getElementById("{safe_key}");
const preview = document.getElementById("preview");

function send() {{
    window.parent.postMessage(
        {{
            isStreamlitMessage:true,
            type:"streamlit:setComponentValue",
            value:ta.value
        }},
        "*"
    );
}}

function escapeHtml(text) {{
    return text
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}}

function renderPreview() {{
    let text = ta.value || "";

    /*
      Công thức được nhận diện trong:
          $...$
          $$...$$
          \\(...\\)
          \\[...\\]

      Nếu người dùng gõ \\frac{{1}}{{2}} mà không có $,
      preview vẫn cố gắng nhận diện các command cơ bản.
    */

    let escaped = escapeHtml(text);

    // Block math: $$...$$
    escaped = escaped.replace(
        /\\$\\$(.+?)\\$\\$/gs,
        function(_, expr) {{
            try {{
                return katex.renderToString(expr, {{
                    displayMode:true,
                    throwOnError:false
                }});
            }} catch(e) {{
                return "<span>" + escapeHtml(expr) + "</span>";
            }}
        }}
    );

    // Inline math: $...$
    escaped = escaped.replace(
        /\\$(.+?)\\$/gs,
        function(_, expr) {{
            try {{
                return katex.renderToString(expr, {{
                    displayMode:false,
                    throwOnError:false
                }});
            }} catch(e) {{
                return "<span>" + escapeHtml(expr) + "</span>";
            }}
        }}
    );

    // \\(...\\)
    escaped = escaped.replace(
        /\\\\\\((.+?)\\\\\\)/gs,
        function(_, expr) {{
            try {{
                return katex.renderToString(expr, {{
                    displayMode:false,
                    throwOnError:false
                }});
            }} catch(e) {{
                return "<span>" + escapeHtml(expr) + "</span>";
            }}
        }}
    );

    // Các command cơ bản không có $:
    // \\frac, \\sqrt, \\times, \\div, \\le, \\ge, \\ne, \\rightarrow,
    // sin/cos/tan và power/subscript.
    escaped = escaped.replace(
        /\\\\(frac|dfrac|sqrt)\\{{([^{{}}]*)\\}}(?:\\{{([^{{}}]*)\\}})?/g,
        function(full, cmd, a, b) {{
            let expr = "\\" + cmd + "{{" + a + "}}";
            if (b !== undefined) expr += "{{" + b + "}}";

            try {{
                return katex.renderToString(expr, {{
                    displayMode:false,
                    throwOnError:false
                }});
            }} catch(e) {{
                return full;
            }}
        }}
    );

    preview.innerHTML = escaped.replace(/\\n/g, "<br>");
}}

document.querySelectorAll(".latex-btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
        const latex = btn.dataset.latex;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const selected = ta.value.substring(start, end);

        const insert = latex.replaceAll("□", selected || "");

        ta.value =
            ta.value.substring(0, start) +
            insert +
            ta.value.substring(end);

        const pos = start + insert.length;
        ta.focus();
        ta.setSelectionRange(pos, pos);

        renderPreview();
        send();
    }});
}});

ta.addEventListener("input", () => {{
    renderPreview();
    send();
}});

window.addEventListener("load", () => {{
    renderPreview();
    send();
}});
</script>

</body>
</html>
"""

    return components.html(
        html_code,
        height=height,
        scrolling=False,
        key=key,
    )


# ============================================================
# 5. EQUATION EDITOR PHỨC TẠP - MATHLIVE
# ============================================================

def equation_editor(
    key: str = "equation_editor",
    default_value: str = "",
    height: int = 260,
):
    """
    MathLive nâng cao.

    Phù hợp cho:
    - phân số
    - căn
    - mũ
    - chỉ số
    - sin/cos/tan
    - ma trận
    - ký hiệu toán
    - bàn phím ảo MathLive

    Không khuyến nghị dùng cho đoạn văn dài.
    """
    safe_key = html.escape(str(key), quote=True)
    safe_value = html.escape(default_value or "")

    html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">

<script src="https://unpkg.com/mathlive"></script>

<style>
html,body {{
    margin:0;
    padding:0;
    background:transparent;
    font-family:Arial,sans-serif;
}}

math-field {{
    display:block;
    width:100%;
    min-height:70px;
    padding:12px;
    border:1px solid #aaa;
    border-radius:8px;
    background:white;
    font-size:1.3rem;
}}

.controls {{
    margin-top:6px;
    display:flex;
    gap:5px;
}}

button {{
    border:1px solid #ccc;
    background:#f5f5f5;
    border-radius:5px;
    padding:5px 9px;
    cursor:pointer;
}}

button:hover {{
    background:#e8f2ff;
}}
</style>
</head>

<body>

<math-field
    id="{safe_key}"
    virtual-keyboard-mode="manual"
>{safe_value}</math-field>

<div class="controls">
    <button id="kb">⌨ Bàn phím</button>
    <button id="clear">Xóa</button>
</div>

<script>
const mf = document.getElementById("{safe_key}");

function send() {{
    window.parent.postMessage(
        {{
            isStreamlitMessage:true,
            type:"streamlit:setComponentValue",
            value:mf.value
        }},
        "*"
    );
}}

mf.addEventListener("input", send);

document.getElementById("kb").addEventListener("click", () => {{
    mf.focus();

    if (window.mathVirtualKeyboard) {{
        window.mathVirtualKeyboard.toggle();
    }}
}});

document.getElementById("clear").addEventListener("click", () => {{
    mf.setValue("");
    mf.focus();
    send();
}});

window.addEventListener("load", send);
</script>

</body>
</html>
"""

    return components.html(
        html_code,
        height=height,
        scrolling=False,
        key=key,
    )


# ============================================================
# 6. SIMPLE MATH EDITOR - TỰ XÂY DỰNG
# ============================================================

def simple_math_editor(
    key: str = "simple_math_editor",
    default_value: str = "",
    height: int = 330,
):
    """
    Editor đơn giản tự xây dựng.

    Khuyến nghị khi muốn:
    - học sinh gõ chữ;
    - bấm nút công thức;
    - xem công thức ngay;
    - không cần MathLive phức tạp.

    Toolbar ngắn, phù hợp khi có 20 câu trên một trang.
    """
    buttons = _SIMPLE_BUTTONS[:10]
    toolbar = _toolbar_html(buttons)

    safe_key = html.escape(str(key), quote=True)
    safe_value = html.escape(default_value or "")

    html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">

<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css">

<script defer
        src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.js">
</script>

<style>
* {{ box-sizing:border-box; }}

html,body {{
    margin:0;
    padding:0;
    background:transparent;
    font-family:Arial,sans-serif;
}}

.toolbar {{
    display:flex;
    flex-wrap:wrap;
    gap:3px;
    margin-bottom:4px;
}}

.latex-btn {{
    border:1px solid #ccc;
    background:#fff;
    border-radius:4px;
    padding:3px 7px;
    cursor:pointer;
    font-size:12px;
}}

textarea {{
    width:100%;
    min-height:120px;
    resize:vertical;
    border:1px solid #bbb;
    border-radius:6px;
    padding:8px;
    font-size:14px;
    line-height:1.45;
    font-family:Consolas,monospace;
}}

.preview {{
    margin-top:5px;
    padding:7px;
    min-height:45px;
    border:1px dashed #ccc;
    border-radius:6px;
    background:#fff;
    overflow:auto;
}}
</style>
</head>

<body>

<div class="toolbar">
{toolbar}
</div>

<textarea id="{safe_key}">{safe_value}</textarea>

<div id="preview" class="preview"></div>

<script>
const ta = document.getElementById("{safe_key}");
const preview = document.getElementById("preview");

function send() {{
    window.parent.postMessage(
        {{
            isStreamlitMessage:true,
            type:"streamlit:setComponentValue",
            value:ta.value
        }},
        "*"
    );
}}

function render() {{
    let value = ta.value || "";

    /*
      Quy ước đơn giản:
        $...$       -> inline
        $$...$$     -> display

      Text bên ngoài công thức vẫn giữ nguyên.
    */

    let out = "";
    let pos = 0;

    const regex = /\\$\\$(.+?)\\$\\$|\\$(.+?)\\$/gs;
    let match;

    while ((match = regex.exec(value)) !== null) {{
        out += escapeHtml(value.substring(pos, match.index));

        const expr = match[1] !== undefined ? match[1] : match[2];
        const display = match[1] !== undefined;

        try {{
            out += katex.renderToString(expr, {{
                displayMode:display,
                throwOnError:false
            }});
        }} catch(e) {{
            out += escapeHtml(expr);
        }}

        pos = regex.lastIndex;
    }}

    out += escapeHtml(value.substring(pos));
    preview.innerHTML = out.replace(/\\n/g, "<br>");
}}

function escapeHtml(s) {{
    return s
        .replaceAll("&","&amp;")
        .replaceAll("<","&lt;")
        .replaceAll(">","&gt;");
}}

document.querySelectorAll(".latex-btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
        const latex = btn.dataset.latex;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const selected = ta.value.substring(start, end);

        let insert = latex.replaceAll("□", selected || "");

        /*
          Nếu công thức chưa có $ thì tự bọc $...$.
          Ví dụ nút phân số:
              \\frac{{□}}{{□}}
          thành:
              $\\frac{{}}{{}}$
        */
        insert = "$" + insert + "$";

        ta.value =
            ta.value.substring(0,start) +
            insert +
            ta.value.substring(end);

        const pos = start + insert.length;
        ta.focus();
        ta.setSelectionRange(pos,pos);

        render();
        send();
    }});
}});

ta.addEventListener("input", () => {{
    render();
    send();
}});

window.addEventListener("load", () => {{
    render();
    send();
}});
</script>

</body>
</html>
"""

    return components.html(
        html_code,
        height=height,
        scrolling=False,
        key=key,
    )


# ============================================================
# 7. HÀM CHUYỂN DỮ LIỆU THÀNH MARKDOWN
# ============================================================

def latex_to_markdown(value: str) -> str:
    """
    Dùng khi muốn lưu câu trả lời vào Markdown.

    Không tự thêm backslash thứ hai.
    Markdown/LaTeX thực tế dùng:
        $\\frac{1}{2}$
    """
    if value is None:
        return ""
    return str(value)


# ============================================================
# 8. GỢI Ý SỬ DỤNG
# ============================================================

EDITOR_TYPES = {
    "latex": latex_editor,
    "toolbar": textarea_toolbar,
    "preview": textarea_preview,
    "equation": equation_editor,
    "simple": simple_math_editor,
}
    """
    Tạo bộ gõ công thức Visual Math Editor (MathLive)
    Trả về chuỗi LaTeX khi học sinh gõ.
    """
    math_editor_html = """
    <!-- Nạp thư viện MathLive từ CDN -->
    <script src="https://unpkg.com/mathlive"></script>
    <link rel="stylesheet" href="https://unpkg.com/mathlive/dist/mathlive-static.css" />
    
    <div style="font-family: sans-serif; margin-bottom: 5px;">
        <label style="font-size: 14px; font-weight: bold; color: #333;">
            ✍️ Nhập công thức / Lời giải toán học:
        </label>
    </div>
    
    <!-- Khung gõ Visual Math -->
    <math-field id="formula-input" style="
        font-size: 1.2rem;
        padding: 8px;
        border: 2px solid #0066cc;
        border-radius: 6px;
        width: 100%;
        background: #ffffff;
        min-height: 50px;
    ">
    </math-field>

    <script>
        const mf = document.getElementById('formula-input');
        
        // Lắng nghe sự kiện gõ công thức và gửi dữ liệu về Streamlit
        mf.addEventListener('input', (evt) => {
            const latexValue = mf.value;
            // Gửi dữ liệu LaTeX về Python qua Streamlit Component API
            window.parent.postMessage({
                type: "streamlit:setComponentValue",
                value: latexValue
            }, "*");
        });
    </script>
    """
    
    # Nhúng giao diện vào Streamlit
    latex_output = components.html(math_editor_html, height=130)
    return latex_output