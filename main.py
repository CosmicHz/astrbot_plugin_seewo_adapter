import asyncio
import base64
import os
import tempfile

from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event.filter import command


@register("seewo_adapter", "CosmicHz", "希沃亲情留言平台适配器", "1.0.0")
class SeewoAdapterPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 导入适配器模块，触发 @register_platform_adapter 装饰器注册
        from .seewo_adapter import SeewoAdapter  # noqa: F401

    async def initialize(self):
        """插件初始化"""

    async def terminate(self):
        """插件销毁"""

    def _get_adapter(self):
        """获取希沃适配器实例"""
        return self.context.get_platform("seewo")

    @command("seewo_status")
    async def seewo_status(self, event):
        """查看希沃适配器运行状态"""
        adapter = self._get_adapter()
        if not adapter:
            yield event.plain_result("未找到希沃适配器实例")
            return

        lines = [f"适配器状态: {adapter.status}"]
        lines.append(f"API 服务器: {adapter.api_url}")
        lines.append(f"已登录: {adapter.logged_in}")
        lines.append(f"轮询间隔: {adapter.poll_interval}s")
        lines.append(f"最新消息 ID: {adapter.last_msg_id}")

        # 尝试从 API 获取详细状态
        if adapter.ready:
            try:
                status = await adapter._api_get("/api/status")
                student = status.get("student", {})
                if student:
                    lines.append(f"关联学生: {student.get('name', 'unknown')}")
            except Exception:
                pass

        yield event.plain_result("\n".join(lines))

    @command("seewo_login")
    async def seewo_login(self, event):
        """触发扫码登录（通过 API 服务器）"""
        adapter = self._get_adapter()
        if not adapter or not adapter.ready:
            yield event.plain_result("希沃适配器未就绪")
            return

        if adapter.logged_in:
            yield event.plain_result("当前已登录，无需重新登录")
            return

        try:
            # 触发 API 服务器的登录流程，获取二维码 base64
            qr_result = await adapter._api_get("/api/login/qrcode")
            if qr_result.get("status") != "ok":
                yield event.plain_result(f"获取二维码失败: {qr_result.get('message', '')}")
                return

            # 将 base64 二维码图片保存为临时文件并发送
            qr_b64 = qr_result.get("qrcode", "")
            if qr_b64:
                qr_bytes = base64.b64decode(qr_b64)
                tmp_path = os.path.join(tempfile.gettempdir(), "seewo_qrcode.png")
                with open(tmp_path, "wb") as f:
                    f.write(qr_bytes)

                # 尝试在日志中输出 ASCII 二维码
                try:
                    from .qrcode_util import qrcode_to_text
                    qr_text = qrcode_to_text(tmp_path)
                    logger.info("Seewo: 请使用微信扫描以下二维码登录：")
                    for line in qr_text.splitlines():
                        logger.info(line)
                except ImportError:
                    logger.info("Seewo: 二维码已生成，请扫描聊天中的图片（安装 Pillow 可在日志中显示 ASCII 二维码）")

                yield event.plain_result("请使用微信扫描以下二维码登录：")
                yield event.image_result(tmp_path)
            else:
                yield event.plain_result("正在登录，请查看 API 服务器日志中的二维码…")

            # 轮询登录状态
            for _ in range(150):  # 最多 5 分钟
                await asyncio.sleep(2)
                login_status = await adapter._api_get("/api/login/status")
                status = login_status.get("status")
                if status == "ok":
                    adapter._logged_in = True
                    yield event.plain_result("登录成功！")
                    return
                elif status == "error":
                    yield event.plain_result(f"登录失败: {login_status.get('message', '')}")
                    return
                # pending/idle: 继续轮询

            yield event.plain_result("登录超时")
        except Exception as e:
            yield event.plain_result(f"登录异常: {e}")
