from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("seewo_adapter", "CosmicHz", "希沃亲情留言平台适配器", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 导入适配器模块，触发 @register_platform_adapter 装饰器注册
        from .seewo_adapter import SeewoAdapter  # noqa: F401

    async def initialize(self):
        """插件初始化"""

    async def terminate(self):
        """插件销毁"""
