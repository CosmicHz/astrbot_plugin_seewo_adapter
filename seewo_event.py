# -*- coding: utf-8 -*-
"""
希沃亲情留言平台事件

处理 AstrBot → 希沃方向的消息发送，支持文本、图片、语音。
"""

import asyncio
import os

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Image, Plain, Record


class SeewoEvent(AstrMessageEvent):
    """希沃亲情留言事件

    持有适配器引用，以便在 send() 时调用希沃 API 发送消息。
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
        await SeewoEvent._send_chain(
            self._adapter._stu_msg, self._adapter._account, message
        )
        await super().send(message)

    # ── 静态发送方法，供 Event.send() 和 send_by_session() 共用 ──

    @staticmethod
    async def _send_chain(stu_msg, account, message: MessageChain) -> None:
        """将 MessageChain 中的组件逐一发送到希沃

        Args:
            stu_msg: things.msg.msg 实例
            account: things.login.acc 实例
            message: AstrBot 消息链
        """
        for comp in message.chain:
            if isinstance(comp, Plain):
                await SeewoEvent._send_text(stu_msg, comp.text)
            elif isinstance(comp, Image):
                await SeewoEvent._send_image(stu_msg, account, comp)
            elif isinstance(comp, Record):
                await SeewoEvent._send_audio(stu_msg, account, comp)
            else:
                logger.debug(f"Seewo: 忽略不支持的消息组件: {type(comp).__name__}")

    @staticmethod
    async def _send_text(stu_msg, text: str) -> None:
        """发送文本消息"""
        if not text:
            return
        # 希沃限制单条消息 199 字
        if len(text) > 199:
            text = text[:196] + "..."
        await asyncio.to_thread(stu_msg.send, text, 1)

    @staticmethod
    async def _send_image(stu_msg, account, image: Image) -> None:
        """发送图片：先下载到本地 → 上传到希沃云 → 发送 URL"""
        try:
            file_path = await image.convert_to_file_path()
        except Exception as e:
            logger.warning(f"Seewo: 获取图片文件路径失败: {e}")
            return

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Seewo: 图片文件不存在: {file_path}")
            return

        url = await SeewoEvent._upload_file(account, file_path, "image/png")
        if url:
            await asyncio.to_thread(stu_msg.send, "", 2, url)
        else:
            logger.warning("Seewo: 图片上传失败")

    @staticmethod
    async def _send_audio(stu_msg, account, record: Record) -> None:
        """发送语音：先获取本地路径 → 上传到希沃云 → 发送 URL"""
        try:
            file_path = await record.convert_to_file_path()
        except Exception as e:
            logger.warning(f"Seewo: 获取语音文件路径失败: {e}")
            return

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Seewo: 语音文件不存在: {file_path}")
            return

        url = await SeewoEvent._upload_file(account, file_path, "audio/mp3")
        if url:
            # 语音时长默认 666ms
            voice_length = 666
            await asyncio.to_thread(stu_msg.send, "", 3, url, voice_length)
        else:
            logger.warning("Seewo: 语音上传失败")

    @staticmethod
    async def _upload_file(account, file_path: str, content_type: str) -> str | None:
        """上传文件到希沃云存储，返回下载 URL"""
        from .things.upload import Upload

        try:
            up = await asyncio.to_thread(Upload, account)
            await asyncio.to_thread(up.upload, file_path, content_type)
            if up.isupload:
                return up.downloadUrl
            return None
        except Exception as e:
            logger.error(f"Seewo: 文件上传异常: {e}")
            return None
