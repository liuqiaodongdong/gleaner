from pathlib import Path
import os as _os

# Project paths
BASE_DIR = Path(__file__).parent
COOKIES_FILE = BASE_DIR / "cookies.json"
PAPERS_DIR = BASE_DIR / "output" / "papers"

# Scraping parameters
DELAY_PAGE = (2, 5)       # seconds, random range between page actions
DELAY_DETAIL = (3, 8)     # seconds, random range after detail page
MAX_RETRIES = 3           # network retry count

# CNKI URLs
CNKI_SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"
CNKI_ADVANCED_URL = "https://kns.cnki.net/kns8s/AdvSearch?type=expert"  # 专业检索页（直接进入）

# 超级鹰打码（验证码求解）—— 仅从环境变量读取，勿在仓库写入账号密码
# 设置：CJY_USER / CJY_PASS / CJY_SOFTID（可写在 MCP env 或系统环境变量）
CHAOJIYING_USER = _os.environ.get("CJY_USER", "")
CHAOJIYING_PASS = _os.environ.get("CJY_PASS", "")
CHAOJIYING_SOFTID = _os.environ.get("CJY_SOFTID", "")
