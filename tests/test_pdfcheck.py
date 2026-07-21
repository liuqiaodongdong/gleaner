# tests/test_pdfcheck.py
from pathlib import Path
from acq.pdfcheck import is_plausible_pdf_url, response_looks_pdf, is_pdf_file, write_pdf_atomic

def test_plausible_pdf_url():
    assert is_plausible_pdf_url("https://x.com/a.pdf")
    assert is_plausible_pdf_url("https://x.com/science/article/pii/123/pdfft")
    assert is_plausible_pdf_url("https://x.com/d?format=pdf")
    assert not is_plausible_pdf_url("https://x.com/journals/list")
    assert not is_plausible_pdf_url("ftp://x.com/a.pdf")

def test_response_looks_pdf():
    assert response_looks_pdf(b"%PDF-1.5 ...", "text/html")
    assert response_looks_pdf(b"<html>", "application/pdf; charset=utf-8")
    assert not response_looks_pdf(b"<html>", "text/html")

def test_is_pdf_file(tmp_path):
    good = tmp_path / "g.pdf"
    good.write_bytes(b"%PDF-1.4" + b"x" * 2000 + b"%%EOF")
    assert is_pdf_file(good)
    small = tmp_path / "s.pdf"; small.write_bytes(b"%PDF-")
    assert not is_pdf_file(small)
    nohdr = tmp_path / "n.pdf"; nohdr.write_bytes(b"<html>" + b"x" * 2000 + b"%%EOF")
    assert not is_pdf_file(nohdr)
    noeof = tmp_path / "e.pdf"; noeof.write_bytes(b"%PDF-" + b"x" * 2000)
    assert not is_pdf_file(noeof)

# --- write_pdf_atomic 三条路径 ---

def test_write_pdf_atomic_success(tmp_path):
    """成功路径：写入有效 PDF → True，目标文件存在，.part 已清理"""
    out = tmp_path / "out.pdf"
    valid_pdf = b"%PDF-1.4" + b"x" * 2000 + b"%%EOF"
    result = write_pdf_atomic([valid_pdf], out)
    assert result is True
    assert out.exists()
    assert not out.with_suffix(out.suffix + ".part").exists()

def test_write_pdf_atomic_invalid_pdf(tmp_path):
    """PDF 校验失败路径：无效内容 → False，目标文件不存在，.part 已清理"""
    out = tmp_path / "out.pdf"
    result = write_pdf_atomic([b"<html>not a pdf</html>"], out)
    assert result is False
    assert not out.exists()
    assert not out.with_suffix(out.suffix + ".part").exists()

def test_write_pdf_atomic_io_exception(tmp_path):
    """I/O 异常路径：迭代中途抛出异常 → False，.part 已清理"""
    out = tmp_path / "out.pdf"

    def bad_iter():
        yield b"%PDF-1.4"
        raise IOError("模拟磁盘错误")

    result = write_pdf_atomic(bad_iter(), out)
    assert result is False
    assert not out.exists()
    assert not out.with_suffix(out.suffix + ".part").exists()
