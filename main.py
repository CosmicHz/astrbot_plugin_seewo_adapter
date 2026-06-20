import asyncio
import time

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
        from .seewo_adapter import SeewoAdapter

        for adapter in self.context.get_platform_adapters():
            if isinstance(adapter, SeewoAdapter):
                return adapter
        return None

    @command("seewo_status")
    async def seewo_status(self, event):
        """查看希沃适配器运行状态"""
        adapter = self._get_adapter()
        if not adapter:
            await event.send_result("未找到希沃适配器实例")
            return

        lines = [f"适配器状态: {adapter.status}"]
        if adapter.logged_in:
            lines.append(f"已登录 UID: {adapter.account.uid}")
        else:
            lines.append("未登录或 Token 已过期")
        if adapter.student:
            lines.append(f"关联学生: {adapter.student.name}")
        lines.append(f"轮询间隔: {adapter.poll_interval}s")
        lines.append(f"最新消息 ID: {adapter.last_msg_id}")
        await event.send_result("\n".join(lines))

    @command("seewo_login")
    async def seewo_login(self, event):
        """重新触发希沃扫码登录"""
        adapter = self._get_adapter()
        if not adapter:
            await event.send_result("未找到希沃适配器实例")
            return

        if adapter.logged_in:
            await event.send_result("当前已登录，无需重新登录")
            return

        await event.send_result("正在触发登录流程，请查看 AstrBot 日志中的二维码…")
        await asyncio.to_thread(adapter.login)
        if adapter.logged_in:
            await event.send_result("登录成功！")
        else:
            await event.send_result("登录失败，请查看日志")

    @command("seewo_getpass")
    async def seewo_getpass(self, event, school_uid: str, sn_code: str):
        """云班离线验证通行证

        用法: /seewo_getpass <schoolUid> <snCode>
        """
        adapter = self._get_adapter()
        if not adapter or not adapter.logged_in:
            await event.send_result("希沃适配器未登录")
            return

        from .things.yunban import getpass

        try:
            result = await asyncio.to_thread(
                getpass,
                adapter.account,
                school_uid,
                sn_code,
                str(int(time.time() * 1000)),
            )
            await event.send_result(str(result))
        except Exception as e:
            await event.send_result(f"获取通行证失败: {e}")
