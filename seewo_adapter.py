# -*- coding: utf-8 -*-
"""
希沃亲情留言平台适配器

通过本地 API 服务器（seewo_robot 的 api_server.py）收发消息，
无需直接导入希沃客户端模块。适配器仅负责轮询消息与协议转换。
"""

import asyncio
import time
from collections.abc import Coroutine
from typing import Any

import aiohttp

from astrbot import logger
from astrbot.api.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
)
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.platform.register import register_platform_adapter
from astrbot.core.platform.platform import PlatformStatus


@register_platform_adapter(
    "seewo",
    "希沃亲情留言",
    default_config_tmpl={
        "api_url": "http://localhost:5001",
        "api_key": "your-secret-key",
        "poll_interval": 5,
    },
    adapter_display_name="希沃亲情留言",
    support_streaming_message=False,
)
class SeewoAdapter(Platform):
    """希沃亲情留言平台适配器

    通过轮询本地 API 服务器接收学生消息，并提交到 AstrBot 事件队列。
    发送消息时通过同一 API 服务器发送。
    """

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config, event_queue)
        self.settings = platform_settings
        self._api_url = platform_config.get("api_url", "http://localhost:5001").rstrip("/")
        self._api_key = platform_config.get("api_key", "your-secret-key")
        self._poll_interval = platform_config.get("poll_interval", 5)
        self._running = False
        self._last_msg_id: int = 0
        self._logged_in: bool = False
        self._session: aiohttp.ClientSession | None = None

        self._metadata = PlatformMetadata(
            name="seewo",
            description="希沃亲情留言",
            id="seewo",
        )

    # ── 公共只读属性 ──

    @property
    def api_url(self) -> str:
        return self._api_url

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def last_msg_id(self) -> int:
        return self._last_msg_id

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    @property
    def ready(self) -> bool:
        return self._session is not None and not self._session.closed

    def meta(self) -> PlatformMetadata:
        return self._metadata

    # ── HTTP 工具 ──

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key, "Content-Type": "application/json"}

    async def _api_get(self, path: str, **kwargs) -> dict:
        async with self._session.get(
            f"{self._api_url}{path}", headers=self._headers(), **kwargs
        ) as resp:
            return await resp.json()

    async def _api_post(self, path: str, data: dict = None, **kwargs) -> dict:
        async with self._session.post(
            f"{self._api_url}{path}", headers=self._headers(), json=data, **kwargs
        ) as resp:
            return await resp.json()

    # ── 生命周期 ──

    async def send_by_session(
        self, session: MessageSesion, message_chain: MessageChain
    ) -> None:
        """通过会话主动发送消息"""
        if not self.ready:
            logger.warning("Seewo: send_by_session 被调用但会话未就绪")
            return
        from .seewo_event import SeewoEvent

        await SeewoEvent._send_chain(self, message_chain)
        await super().send_by_session(session, message_chain)

    def run(self) -> Coroutine[Any, Any, None]:
        async def _run():
            self._running = True
            self._session = aiohttp.ClientSession()

            # 检查 API 服务器连接状态
            try:
                status = await self._api_get("/api/status")
                if status.get("need_login"):
                    self._logged_in = False
                    logger.info("Seewo: 需要登录，请使用 /seewo_login 指令触发扫码")
                else:
                    self._logged_in = True
                    student = status.get("student", {})
                    logger.info(f"Seewo: 已连接，学生: {student.get('name', 'unknown')}")
            except Exception as e:
                logger.warning(f"Seewo: 状态检查失败: {e}")

            self.status = PlatformStatus.RUNNING

            # 获取初始最新消息 ID
            try:
                data = await self._api_get("/api/messages", params={"count": "1"})
                messages = data.get("messages", [])
                if messages:
                    self._last_msg_id = messages[0].get("id", 0)
            except Exception as e:
                logger.warning(f"Seewo: 获取初始消息 ID 失败: {e}")

            # 轮询循环
            error_count = 0
            current_interval = self._poll_interval

            while self._running:
                try:
                    new_messages = await self._poll_messages()
                    for msg_data in new_messages:
                        abm = self._convert_message(msg_data)
                        event = self._create_event(abm)
                        self.commit_event(event)
                    error_count = 0
                    current_interval = self._poll_interval
                except Exception as e:
                    error_count += 1
                    logger.error(f"Seewo: 轮询出错 ({error_count}): {e}")
                    if error_count >= 5:
                        current_interval = min(current_interval * 2, 30)
                        logger.warning(f"Seewo: 退避至 {current_interval}s 轮询间隔")
                await asyncio.sleep(current_interval)

        return _run()

    async def terminate(self) -> None:
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Seewo: 适配器已停止")

    # ── 消息轮询 ──

    async def _poll_messages(self) -> list[dict]:
        """轮询新消息，仅返回学生的消息"""
        data = await self._api_get("/api/messages", params={"count": "20"})

        if data.get("need_login"):
            self._logged_in = False
            return []

        raw_messages = data.get("messages", [])
        if not raw_messages:
            return []

        # messages 按 ID 倒序（新→旧）
        newest_id = raw_messages[0].get("id", self._last_msg_id)

        new_student_msgs: list[dict] = []
        for m in raw_messages:
            msg_id = m.get("id", 0)
            if msg_id <= self._last_msg_id:
                break
            if m.get("sender") == "student":
                new_student_msgs.append(m)

        self._last_msg_id = newest_id

        # 按时间正序返回（旧→新）
        new_student_msgs.reverse()
        return new_student_msgs

    # ── 消息转换 ──

    def _convert_message(self, data: dict) -> AstrBotMessage:
        """将 API 服务器返回的消息转换为 AstrBotMessage"""
        from astrbot.api.message_components import Plain, Image, Record

        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.self_id = "seewo_parent"
        abm.session_id = data.get("senderName", "seewo_student")
        abm.message_id = str(data.get("id", ""))

        abm.sender = MessageMember(
            user_id=data.get("sender", ""),
            nickname=data.get("senderName", "未知"),
        )

        msg_type = data.get("type", 1)
        content = data.get("content", "")
        res_url = data.get("resUrl", "")

        abm.message = []
        if msg_type in (0, 1):
            abm.message.append(Plain(text=content))
            abm.message_str = content
        elif msg_type == 2:
            if content:
                abm.message.append(Plain(text=content))
            if res_url:
                abm.message.append(Image.fromURL(res_url))
            abm.message_str = content or "[图片]"
        elif msg_type == 3:
            if content:
                abm.message.append(Plain(text=content))
            if res_url:
                abm.message.append(Record(file=res_url))
            abm.message_str = content or "[语音]"
        else:
            label = {4: "[视频]", 5: "[文件]", 6: "[富文本]"}.get(
                msg_type, f"[类型{msg_type}]"
            )
            abm.message.append(Plain(text=content or label))
            abm.message_str = content or label

        abm.raw_message = data
        abm.timestamp = int(time.time())

        return abm

    def _create_event(self, message: AstrBotMessage):
        """从 AstrBotMessage 创建 SeewoEvent"""
        from .seewo_event import SeewoEvent

        return SeewoEvent(
            message_str=message.message_str,
            message_obj=message,
            platform_meta=self.meta(),
            session_id=message.session_id,
            adapter=self,
        )
