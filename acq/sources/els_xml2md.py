# acq/sources/els_xml2md.py —— Elsevier 全文 XML -> 结构化 Markdown（纯逻辑）
# 输出：# 标题 / ## Abstract / 正文章节(段落,含 MathML→LaTeX 公式) / ## Tables(markdown表,保留数值) / ## Figures(图题)
# 关键：MathML 公式转 LaTeX(行内 $...$ / 独立式 $$...$$)，表格数值保留 —— 都是经济学综述防幻觉的要害。
import re
from lxml import etree

DC = "{http://purl.org/dc/elements/1.1/}"
CE = "{http://www.elsevier.com/xml/common/dtd}"

# Unicode 数学符号/希腊字母 → LaTeX
_SYM = {
    "∞": "\\infty", "∑": "\\sum", "∫": "\\int", "∬": "\\iint", "∏": "\\prod",
    "∂": "\\partial", "∇": "\\nabla", "±": "\\pm", "∓": "\\mp", "×": "\\times",
    "÷": "\\div", "⋅": "\\cdot", "·": "\\cdot", "∘": "\\circ", "∗": "*",
    "≤": "\\leq", "≥": "\\geq", "≠": "\\neq", "≈": "\\approx", "≅": "\\cong",
    "≡": "\\equiv", "∼": "\\sim", "≃": "\\simeq", "≪": "\\ll", "≫": "\\gg",
    "→": "\\to", "←": "\\leftarrow", "↦": "\\mapsto", "⇒": "\\Rightarrow",
    "⇔": "\\Leftrightarrow", "∈": "\\in", "∉": "\\notin", "∋": "\\ni",
    "⊂": "\\subset", "⊆": "\\subseteq", "⊃": "\\supset", "⊇": "\\supseteq",
    "∪": "\\cup", "∩": "\\cap", "∀": "\\forall", "∃": "\\exists", "∄": "\\nexists",
    "∅": "\\emptyset", "…": "\\dots", "⋯": "\\cdots", "⋮": "\\vdots", "⋱": "\\ddots",
    "′": "'", "″": "''", "∝": "\\propto", "∧": "\\wedge", "∨": "\\vee", "¬": "\\neg",
    "°": "^{\\circ}", "⊥": "\\perp", "∥": "\\parallel", "∠": "\\angle", "√": "\\surd",
    "ℝ": "\\mathbb{R}", "ℕ": "\\mathbb{N}", "ℤ": "\\mathbb{Z}", "ℚ": "\\mathbb{Q}",
    "ℂ": "\\mathbb{C}", "𝔼": "\\mathbb{E}", "ⁿ": "^{n}", "⁻": "-", "−": "-",
    "α": "\\alpha", "β": "\\beta", "γ": "\\gamma", "δ": "\\delta", "ε": "\\epsilon",
    "ϵ": "\\epsilon", "ζ": "\\zeta", "η": "\\eta", "θ": "\\theta", "ϑ": "\\vartheta",
    "ι": "\\iota", "κ": "\\kappa", "λ": "\\lambda", "μ": "\\mu", "ν": "\\nu",
    "ξ": "\\xi", "ο": "o", "π": "\\pi", "ϖ": "\\varpi", "ρ": "\\rho", "ϱ": "\\varrho",
    "ς": "\\varsigma", "σ": "\\sigma", "τ": "\\tau", "υ": "\\upsilon", "φ": "\\phi",
    "ϕ": "\\phi", "χ": "\\chi", "ψ": "\\psi", "ω": "\\omega",
    "Γ": "\\Gamma", "Δ": "\\Delta", "Θ": "\\Theta", "Λ": "\\Lambda", "Ξ": "\\Xi",
    "Π": "\\Pi", "Σ": "\\Sigma", "Υ": "\\Upsilon", "Φ": "\\Phi", "Ψ": "\\Psi", "Ω": "\\Omega",
    "∣": "|", "｜": "|", "⁎": "*", "∙": "\\cdot", "⊗": "\\otimes", "⊕": "\\oplus",
    "⩽": "\\leqslant", "⩾": "\\geqslant", "≜": "\\triangleq", "⟵": "\\longleftarrow",
    "⟶": "\\longrightarrow", "↑": "\\uparrow", "↓": "\\downarrow", "∖": "\\setminus",
}
# mover/munder 上的重音符 → LaTeX accent
_ACCENT = {"^": "\\hat", "ˆ": "\\hat", "¯": "\\bar", "‾": "\\bar", "~": "\\tilde",
           "˜": "\\tilde", "→": "\\vec", "⃗": "\\vec", "˙": "\\dot", "¨": "\\ddot",
           ".": "\\dot", "ˉ": "\\bar"}
_BIGOP = {"\\sum", "\\int", "\\prod", "\\iint", "\\lim", "\\max", "\\min", "\\bigcup", "\\bigcap"}
# 算符名(渲染为直立体)
_FUNCS = {"max", "min", "log", "ln", "exp", "sin", "cos", "tan", "cot", "sec",
          "csc", "lim", "sup", "inf", "det", "gcd", "arg", "Pr", "mod"}
# 定界符 → LaTeX(\left/\right 后必须是合法定界符；花括号要转义)
_FENCE = {"": ".", "{": "\\{", "}": "\\}", "|": "|", "‖": "\\|",
          "⟨": "\\langle", "⟩": "\\rangle", "⌊": "\\lfloor", "⌋": "\\rfloor",
          "⌈": "\\lceil", "⌉": "\\rceil"}


def _fence(ch: str) -> str:
    return _FENCE.get(ch, ch if ch else ".")


def _ln(el) -> str:
    """元素 localname（忽略命名空间；正文 ce: 与表格 cals: / 公式 mml: 混用）。"""
    return etree.QName(el).localname


def _txt(el) -> str:
    return " ".join(el.xpath("string()").split())


def _sym(s: str) -> str:
    return "".join(_SYM.get(ch, ch) for ch in (s or ""))


def _esc(s: str) -> str:
    """转义正文里的字面 $（如美元金额 $10,000），避免与公式 $...$ 定界符冲突。"""
    return (s or "").replace("$", "\\$")


def _elems(el):
    return [c for c in el if isinstance(c.tag, str)]


def _ml(el) -> str:
    """MathML presentation 元素 → LaTeX（递归）。"""
    tag = _ln(el)
    ch = _elems(el)
    if tag in ("math", "mrow", "mstyle", "mpadded", "merror", "semantics"):
        return "".join(_ml(c) for c in ch)
    if tag in ("mi", "mn", "mo", "mtext"):
        raw = (el.text or "").strip()
        if tag in ("mi", "mo") and raw in _FUNCS:
            return "\\" + raw + " "
        if tag == "mo" and raw in ("{", "}"):   # 裸花括号定界符需转义
            return "\\" + raw
        t = _sym(raw)
        if tag == "mtext" and t:
            return "\\text{" + t + "}"
        return t
    if tag == "msup" and len(ch) >= 2:
        return "{" + _ml(ch[0]) + "}^{" + _ml(ch[1]) + "}"
    if tag == "msub" and len(ch) >= 2:
        return "{" + _ml(ch[0]) + "}_{" + _ml(ch[1]) + "}"
    if tag == "msubsup" and len(ch) >= 3:
        return "{" + _ml(ch[0]) + "}_{" + _ml(ch[1]) + "}^{" + _ml(ch[2]) + "}"
    if tag == "mfrac" and len(ch) >= 2:
        return "\\frac{" + _ml(ch[0]) + "}{" + _ml(ch[1]) + "}"
    if tag == "msqrt":
        return "\\sqrt{" + "".join(_ml(c) for c in ch) + "}"
    if tag == "mroot" and len(ch) >= 2:
        return "\\sqrt[" + _ml(ch[1]) + "]{" + _ml(ch[0]) + "}"
    if tag == "mover" and len(ch) >= 2:
        base, over = _ml(ch[0]), _ml(ch[1]).strip()
        acc = _ACCENT.get(over)
        return (acc + "{" + base + "}") if acc else ("\\overset{" + over + "}{" + base + "}")
    if tag == "munder" and len(ch) >= 2:
        base, under = _ml(ch[0]), _ml(ch[1])
        return (base + "_{" + under + "}") if base in _BIGOP else ("\\underset{" + under + "}{" + base + "}")
    if tag == "munderover" and len(ch) >= 3:
        return _ml(ch[0]) + "_{" + _ml(ch[1]) + "}^{" + _ml(ch[2]) + "}"
    if tag == "mfenced":
        opn, cls = _fence(el.get("open", "(")), _fence(el.get("close", ")"))
        sep = el.get("separators", ",")
        inner = (sep[0] if sep else ",").join(_ml(c) for c in ch)
        return "\\left" + opn + inner + "\\right" + cls
    if tag in ("mtable",):
        rows = []
        for tr in ch:
            if _ln(tr) == "mtr":
                rows.append(" & ".join(_ml(td) for td in tr if _ln(td) == "mtd"))
        return "\\begin{matrix} " + " \\\\ ".join(rows) + " \\end{matrix}"
    if tag in ("mspace",):
        return " "
    if tag in ("mphantom",):
        return ""
    # 兜底：拼接子节点或自身文本
    return "".join(_ml(c) for c in ch) if ch else _sym((el.text or "").strip())


def _inline_md(el) -> str:
    """段落混合内容 → 文本，内嵌 MathML 转行内 $...$；其余子元素递归取文字。"""
    parts = []
    if el.text:
        parts.append(_esc(el.text))
    for c in el:
        if not isinstance(c.tag, str):
            continue
        ln = _ln(c)
        if ln == "math":
            tex = _ml(c).strip()
            if tex:
                parts.append(" $" + tex + "$ ")
        elif ln == "formula":                    # 段内独立式 → 块
            b = _formula_block(c)
            if b:
                parts.append("\n\n" + b.strip() + "\n\n")
        elif ln == "display":
            for f in c.iter():
                if _ln(f) == "formula":
                    b = _formula_block(f)
                    if b:
                        parts.append("\n\n" + b.strip() + "\n\n")
        else:
            parts.append(_inline_md(c))
        if c.tail:
            parts.append(_esc(c.tail))
    text = "".join(parts)
    text = re.sub(r"[ \t]+", " ", text)      # 折叠空格，保留换行(独立式独占行)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _label_caption(el):
    label, caption = "", ""
    for c in el:
        ln = _ln(c)
        if ln == "label":
            label = (c.text or "").strip()
        elif ln == "caption":
            caption = _txt(c)
    return label, caption


def _formula_block(formula_el) -> str:
    """ce:formula → 独立式 $$...$$（带式号 \\tag）。"""
    label, _ = _label_caption(formula_el)
    maths = [m for m in formula_el.iter() if _ln(m) == "math"]
    tex = " ".join(_ml(m).strip() for m in maths if _ml(m).strip())
    if not tex:
        return ""
    if label:
        tex += " \\tag{" + label.strip("()") + "}"
    return "\n$$ " + tex + " $$"


def _render_table(tbl) -> str:
    label, caption = _label_caption(tbl)
    head = ("**" + (label or "Table") + "**") + ((" " + _esc(caption)) if caption else "")
    grid = []
    for r in [r for r in tbl.iter() if _ln(r) == "row"]:
        cells = [_txt(e) for e in r if _ln(e) == "entry"]
        if cells:
            grid.append(cells)
    lines = ["\n" + head]
    if grid:
        ncol = max(len(r) for r in grid)
        grid = [r + [""] * (ncol - len(r)) for r in grid]
        def fmt(row):
            return "| " + " | ".join(_esc(c).replace("|", "\\|") for c in row) + " |"
        lines.append(fmt(grid[0]))
        lines.append("| " + " | ".join(["---"] * ncol) + " |")
        for r in grid[1:]:
            lines.append(fmt(r))
    return "\n".join(lines)


def _render_figure(fig) -> str:
    label, caption = _label_caption(fig)
    head = ("**" + (label or "Figure") + "**") + ((" " + _esc(caption)) if caption else "")
    return "\n" + head + "  *(图见原文 PDF)*"


def xml_to_md(xml) -> str:
    """Elsevier full-text-retrieval-response -> Markdown（标题/摘要/正文+LaTeX公式/表格/图题）。"""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)
    out = []
    title = root.findtext(f".//{DC}title")
    out.append("# " + _esc((title or "").strip()))
    desc = root.findtext(f".//{DC}description")
    if desc and desc.strip():
        out.append("\n## Abstract\n" + _esc(" ".join(desc.split())))

    def walk(sec, depth):
        st = sec.find(f"{CE}section-title")
        if st is not None and (st.text or "").strip():
            out.append("\n" + "#" * min(depth + 1, 6) + " " + st.text.strip())
        for child in sec:
            if not isinstance(child.tag, str):
                continue
            ln = _ln(child)
            if ln == "para":
                t = _inline_md(child)
                if t:
                    out.append(t)
            elif ln == "section":
                walk(child, depth + 1)
            elif ln == "display":          # 独立公式块（ce:display 内含 ce:formula）
                for f in child.iter():
                    if _ln(f) == "formula":
                        b = _formula_block(f)
                        if b:
                            out.append(b)
            elif ln == "formula":
                b = _formula_block(child)
                if b:
                    out.append(b)

    for sec in root.findall(f".//{CE}sections/{CE}section"):
        walk(sec, 1)

    tables = [e for e in root.iter() if _ln(e) == "table"]
    if tables:
        out.append("\n## Tables")
        for t in tables:
            out.append(_render_table(t))
    figs = [e for e in root.iter() if _ln(e) == "figure"]
    if figs:
        out.append("\n## Figures")
        for f in figs:
            out.append(_render_figure(f))
    return "\n".join(out)
