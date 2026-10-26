"""识别安装模板占位值，避免将未填写的配置报告为就绪。"""
PLACEHOLDERS = {"your_elsevier_api_key_here", "your_key", "your_chaojiying_username",
                "your_chaojiying_password", "your_softid", "chaojiying_user", "chaojiying_pass"}


def configured_value(value):
    text = (value or "").strip()
    return bool(text) and text.lower() not in PLACEHOLDERS
