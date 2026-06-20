# -*- coding: utf-8 -*-
"""
全局常量与配置

定义项目级别的文件路径、网络代理、公共请求头和希沃 API URL。
"""

import time
import os

# 数据目录，默认为 things/ 目录本身
_data_dir = os.path.dirname(os.path.abspath(__file__))

# 二维码图片保存路径（登录时生成）
qrcode_file = os.path.join(_data_dir, "qrcode.png")
# 登录凭证存储路径（含 userId 和 token 等，实质上是登录时希沃服务器相应的内容）
token_file = os.path.join(_data_dir, "tokens.json")
# 上传文件记录存储路径
uploads_file = os.path.join(_data_dir, "uploads.json")
# 聊天记录存储路径
chat_log_file = os.path.join(_data_dir, "chat_history.json")


def set_data_dir(path: str):
    """设置数据目录，更新所有文件路径为绝对路径。

    必须在导入其他 things 模块之前调用。
    """
    global qrcode_file, token_file, uploads_file, chat_log_file, _data_dir
    _data_dir = path
    os.makedirs(path, exist_ok=True)
    qrcode_file = os.path.join(path, "qrcode.png")
    token_file = os.path.join(path, "tokens.json")
    uploads_file = os.path.join(path, "uploads.json")
    chat_log_file = os.path.join(path, "chat_history.json")
    if not os.path.isfile(uploads_file):
        with open(uploads_file, "wb") as f:
            f.write(b"{}")


# 初始化 uploads.json
if not os.path.isfile(uploads_file):
    with open(uploads_file, "wb") as f:
        f.write(b"{}")

# HTTP 代理配置，空字典表示不使用代理
proxies: dict[str, str] = {}  # type: ignore
# SSL 证书验证开关
verify = True

# 无 Cookie 的公共请求头，用于登录流程（获取二维码、检查扫码状态）
headers_nocookie = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Accept": "image/avif,image/webp,*/*",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://id.seewo.com/login-iframe?system=mis-admin&callbackIframeUrl=%2F%2Fcampus.seewo.com%2Fcallback-iframe&redirect_url=",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-origin",
}


class urls:
    """希沃云班 API 端点集合

    部分端点 URL 包含时间戳参数（毫秒级），每次实例化时自动生成。
    """

    def __init__(self) -> None:
        # 毫秒时间戳
        self.time = str(int(time.time()) * 1000)
        self.status = "https://campus.seewo.com/soul-bootstrap/seewo-phoenix-blood-server/mobile/user/v1/"
        self.get_last_msg = "https://campus.seewo.com/soul-bootstrap/home-school-service/mobile/kidnote/v1/note/dialogs?userUid="
        self.api = "https://m-campus.seewo.com/class/apis.json?action="
        self.login_api = "https://id.seewo.com/auth/loginApi?_time" + self.time
        self.qrcode_image = (
            "https://id.seewo.com/scan/qrcode?oriSys=mis-admin&t=" + self.time
        )
        # 二维码扫码状态轮询端点
        self.check_qrcode = (
            "https://id.seewo.com/scan/pcCheckQrcode?type=long&_=" + self.time
        )
