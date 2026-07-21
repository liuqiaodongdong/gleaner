from pathlib import Path
from acq.sources.els_xml2md import xml_to_md

SAMPLE = (Path(__file__).parent / "fixtures" / "els_sample.xml").read_bytes()


def test_title_is_h1():
    md = xml_to_md(SAMPLE)
    assert md.splitlines()[0] == "# A Test Article on Digital Economy"


def test_abstract_section():
    md = xml_to_md(SAMPLE)
    assert "## Abstract" in md
    assert "This abstract explains the test." in md


def test_section_headings_and_body():
    md = xml_to_md(SAMPLE)
    assert "## Introduction" in md
    assert "First body paragraph about innovation" in md
    assert "## Methods" in md
    assert "### Data" in md          # 嵌套子节降一级
    assert "Firm-level panel data." in md


def test_accepts_str_and_bytes():
    assert xml_to_md(SAMPLE.decode("utf-8")).startswith("# ")


def test_tables_rendered_with_values():
    md = xml_to_md(SAMPLE)
    assert "## Tables" in md
    assert "Table 1" in md and "Summary statistics." in md
    assert "| Variable | Mean |" in md          # 表头
    assert "| GDP growth | 3.14 |" in md         # 数值保留(防幻觉的关键)


def test_figure_caption_kept():
    md = xml_to_md(SAMPLE)
    assert "## Figures" in md
    assert "Fig. 1" in md and "Trend of demand over time." in md


def test_fences_and_function_names():
    # \left{ 在 LaTeX 非法 → 须 \left\{；max/min 等算符名须直立 \max
    xml = ('<?xml version="1.0"?><full-text-retrieval-response '
           'xmlns="http://www.elsevier.com/xml/svapi/article/dtd" '
           'xmlns:dc="http://purl.org/dc/elements/1.1/" '
           'xmlns:ce="http://www.elsevier.com/xml/common/dtd" '
           'xmlns:mml="http://www.w3.org/1998/Math/MathML">'
           '<coredata><dc:title>T</dc:title></coredata><originalText><ce:sections>'
           '<ce:section><ce:section-title>S</ce:section-title><ce:para>val '
           '<mml:math><mml:mrow><mml:mo>max</mml:mo>'
           '<mml:mfenced open="{" close="}"><mml:mi>x</mml:mi><mml:mi>y</mml:mi></mml:mfenced>'
           '</mml:mrow></mml:math> end.</ce:para></ce:section></ce:sections></originalText>'
           '</full-text-retrieval-response>')
    md = xml_to_md(xml)
    assert "\\max" in md
    assert "\\left\\{" in md and "\\right\\}" in md


def test_dollar_amounts_escaped():
    # 正文里的美元金额必须转义为 \$，否则与公式 $...$ 定界符冲突
    md = xml_to_md(SAMPLE)
    assert "\\$10,000" in md and "\\$20,000" in md


def test_inline_formula_to_latex():
    md = xml_to_md(SAMPLE)
    # 行内 MathML msub c_0 → $ {c}_{0} $
    assert "{c}_{0}" in md
    assert "$" in md


def test_display_formula_to_latex_with_tag():
    md = xml_to_md(SAMPLE)
    assert "$$" in md
    assert "\\frac{dy}{dx}" in md          # mfrac
    assert "\\sum_{i=1}^{n}" in md          # munderover + ∑
    assert "{x}^{2}" in md                  # msup
    assert "\\beta" in md                   # 希腊字母 Unicode→LaTeX
    assert "\\tag{1}" in md                 # 式号
