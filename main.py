import asyncio

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

        yield event.plain_result("正在获取登录二维码，请查看 API 服务器日志中的二维码…")

        try:
            # 触发 API 服务器的登录流程
            qr_result = await adapter._api_get("/api/login/qrcode")
            if qr_result.get("status") != "ok":
                yield event.plain_result(f"获取二维码失败: {qr_result.get('message', '')}")
                return

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
                # pending: 继续轮询

            yield event.plain_result("登录超时")
        except Exception as e:
            yield event.plain_result(f"登录异常: {e}")
