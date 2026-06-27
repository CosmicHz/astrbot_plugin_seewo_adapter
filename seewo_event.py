# -*- coding: utf-8 -*-
"""
希沃亲情留言平台事件

通过本地 API 服务器发送消息，支持文本、图片、语音。
"""

import os

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Image, Plain, Record


class SeewoEvent(AstrMessageEvent):
    """希沃亲情留言事件

    持有适配器引用，通过 API 服务器发送消息。
    """

    def __init__(
        self,
        message_str: str,
        message_obj,
        platform_meta,
        session_id: str,
        adapter,  # SeewoAdapter 实例
    ) -> None:
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self._adapter = adapter

    async def send(self, message: MessageChain) -> None:
        """发送消息到希沃亲情留言"""
        await SeewoEvent._send_chain(self._adapter, message)
        await super().send(message)

    # ── 静态发送方法，供 Event.send() 和 send_by_session() 共用 ──

    @staticmethod
    async def _send_chain(adapter, message: MessageChain) -> None:
        """将 MessageChain 中的组件逐一发送"""
        for comp in message.chain:
            if isinstance(comp, Plain):
                await SeewoEvent._send_text(adapter, comp.text)
            elif isinstance(comp, Image):
                await SeewoEvent._send_image(adapter, comp)
            elif isinstance(comp, Record):
                await SeewoEvent._send_audio(adapter, comp)
            else:
                logger.debug(f"Seewo: 忽略不支持的消息组件: {type(comp).__name__}")

    @staticmethod
    async def _send_text(adapter, text: str) -> None:
        """发送文本消息"""
        if not text:
            return
        if len(text) > 199:
            text = text[:196] + "..."
        await adapter._api_post("/api/send", {"content": text})

    @staticmethod
    async def _send_image(adapter, image: Image) -> None:
        """发送图片：获取本地路径 → 通过 API 服务器上传发送"""
        try:
            file_path = await image.convert_to_file_path()
        except Exception as e:
            logger.warning(f"Seewo: 获取图片文件路径失败: {e}")
            return

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Seewo: 图片文件不存在: {file_path}")
            return

        # 使用 multipart 上传
        data = aiohttp.FormData()
        data.add_field(
            "file",
            open(file_path, "rb"),
            filename=os.path.basename(file_path),
            content_type="image/png",
        )
        headers = {"X-API-Key": adapter.api_key}
        try:
            async with adapter._session.post(
                f"{adapter.api_url}/api/send_image", headers=headers, data=data
            ) as resp:
                result = await resp.json()
                if result.get("status") != "ok":
                    logger.warning(f"Seewo: 图片发送失败: {result}")
        except Exception as e:
            logger.error(f"Seewo: 图片发送异常: {e}")

    @staticmethod
    async def _send_audio(adapter, record: Record) -> None:
        """发送语音：获取本地路径 → 通过 API 服务器上传发送"""
        try:
            file_path = await record.convert_to_file_path()
        except Exception as e:
            logger.warning(f"Seewo: 获取语音文件路径失败: {e}")
            return

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Seewo: 语音文件不存在: {file_path}")
            return

        # 本地服务器可以直接传文件路径
        await adapter._api_post(
            "/api/send_audio", {"file_path": file_path, "voice_length": 666}
        )
