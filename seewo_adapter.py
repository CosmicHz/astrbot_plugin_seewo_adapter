# -*- coding: utf-8 -*-
"""
希沃亲情留言平台适配器

直接复用 things/ 下的登录、消息收发等模块，
以轮询方式接收学生消息，无需额外启动 HTTP 服务器。
"""

import asyncio
import json
import os
import time
from collections.abc import Coroutine
from typing import Any

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
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# ── 在导入 things 子模块之前，先设置数据目录 ──
from .things import init as _things_init

_SEEWO_DATA_DIR = os.path.join(get_astrbot_data_path(), "seewo")
_things_init.set_data_dir(_SEEWO_DATA_DIR)

from .things.login import acc, download_qrcode, check_qrcode
from .things.stu import stu
from .things.msg import msg
from .things.upload import Upload
from .things.funcs import write_file
from .things.qrcode import qrcode_to_text


@register_platform_adapter(
    "seewo",
    "希沃亲情留言",
    default_config_tmpl={
        "poll_interval": 5,
    },
    adapter_display_name="希沃亲情留言",
    support_streaming_message=False,
)
class SeewoAdapter(Platform):
    """希沃亲情留言平台适配器

    通过轮询希沃云班 API 接收学生消息，并提交到 AstrBot 事件队列。
    发送消息时通过希沃云班 API 直接发送，无需额外 HTTP 服务器。
    """

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config, event_queue)
        self.settings = platform_settings
        self._poll_interval = platform_config.get("poll_interval", 5)
        self._running = False

        # 希沃会话对象
        self._account: acc | None = None
        self._student: stu | None = None
        self._stu_msg: msg | None = None
        self._last_msg_id: int = 0

        self._metadata = PlatformMetadata(
            name="seewo",
            description="希沃亲情留言",
            id="seewo",
        )

    def meta(self) -> PlatformMetadata:
        return self._metadata

    async def send_by_session(
        self, session: MessageSesion, message_chain: MessageChain
    ) -> None:
        """通过会话主动发送消息（插件主动推送场景）"""
        if self._stu_msg is None or self._account is None:
            logger.warning("Seewo: send_by_session 被调用但会话未初始化")
            return
        from .seewo_event import SeewoEvent

        await SeewoEvent._send_chain(self._stu_msg, self._account, message_chain)
        await super().send_by_session(session, message_chain)

    # ── 生命周期 ──

    def run(self) -> Coroutine[Any, Any, None]:
        async def _run():
            self._running = True

            # 1. 初始化会话
            await asyncio.to_thread(self._init_session)

            # 2. 如果 Token 过期则走扫码登录
            if self._account is None or self._account.token_expired:
                logger.info("Seewo: Token 无效或不存在，开始扫码登录流程…")
                await asyncio.to_thread(self._login)

            if self._account is None or self._account.token_expired:
                logger.error("Seewo: 登录失败，适配器无法启动")
                self.record_error("登录失败")
                return

            self.status = PlatformStatus.RUNNING
            logger.info(
                f"Seewo: 适配器已启动，关联学生: {self._student.name}"
            )

            # 3. 获取当前最新消息 ID，避免重复处理历史消息
            try:
                result = await asyncio.to_thread(self._stu_msg.get, 1)
                messages = result.get("result", [])
                if messages:
                    self._last_msg_id = messages[0].get("id", 0)
            except Exception as e:
                logger.warning(f"Seewo: 获取初始消息 ID 失败: {e}")

            # 4. 轮询循环
            error_count = 0
            current_interval = self._poll_interval

            while self._running:
                try:
                    new_messages = await asyncio.to_thread(self._poll_messages)
                    for msg_data in new_messages:
                        abm = self._convert_message(msg_data)
                        event = self._create_event(abm)
                        self.commit_event(event)
                    error_count = 0
                    current_interval = self._poll_interval
                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"Seewo: 轮询出错 ({error_count}): {e}"
                    )
                    if error_count >= 5:
                        current_interval = min(current_interval * 2, 30)
                        logger.warning(
                            f"Seewo: 退避至 {current_interval}s 轮询间隔"
                        )
                await asyncio.sleep(current_interval)

        return _run()

    async def terminate(self) -> None:
        self._running = False
        logger.info("Seewo: 适配器已停止")

    # ── 会话管理 ──

    def _init_session(self) -> None:
        """初始化希沃会话（在线程中执行）"""
        try:
            self._account = acc(auto_login=False)
            if not self._account.token_expired:
                self._student = stu(self._account)
                self._stu_msg = msg(self._account, self._student)
                logger.info(f"Seewo: 会话初始化成功，学生: {self._student.name}")
        except Exception as e:
            logger.error(f"Seewo: 会话初始化失败: {e}")
            self._account = None

    def _login(self) -> None:
        """微信扫码登录（在线程中执行）"""
        try:
            cookies = download_qrcode()
            qr_text = qrcode_to_text(_things_init.qrcode_file)
            logger.info("Seewo: 请使用微信扫描以下二维码登录希沃账号：")
            for line in qr_text.splitlines():
                logger.info(line)

            # 轮询扫码状态，最长 5 分钟
            status = 200
            data = None
            for _ in range(150):
                data = check_qrcode(cookies)["data"]
                status = data["statusCode"]
                if status not in (200, 201):
                    break
                time.sleep(2)

            if status == 202 and data:
                write_file(
                    os.path.join(_SEEWO_DATA_DIR, "tokens.json"),
                    json.dumps(data).encode(),
                )
                self._account = acc(auto_login=False)
                if not self._account.token_expired:
                    self._student = stu(self._account)
                    self._stu_msg = msg(self._account, self._student)
                    logger.info(
                        f"Seewo: 登录成功，学生: {self._student.name}"
                    )
                else:
                    logger.error("Seewo: 登录后 Token 仍无效")
            else:
                logger.error("Seewo: 扫码登录失败或超时")
        except Exception as e:
            logger.error(f"Seewo: 登录异常: {e}")

    # ── 消息轮询 ──

    def _poll_messages(self) -> list[dict]:
        """轮询新消息，仅返回学生的消息（在线程中执行）"""
        if self._stu_msg is None:
            return []

        result = self._stu_msg.get(20)
        raw_messages = result.get("result", [])
        if not raw_messages:
            return []

        # 记录最新消息 ID（不论发送者）
        newest_id = raw_messages[0].get("id", self._last_msg_id)

        # 筛选：ID > last_msg_id 且来自学生
        new_student_msgs: list[dict] = []
        for m in raw_messages:
            msg_id = m.get("id", 0)
            if msg_id <= self._last_msg_id:
                break  # 结果按时间倒序，遇到旧消息即可停止
            sender_uid = m.get("senderUid", "")
            if self._student and sender_uid == self._student.userUid:
                new_student_msgs.append(m)

        self._last_msg_id = newest_id

        # 按时间正序返回（旧→新）
        new_student_msgs.reverse()
        return new_student_msgs

    # ── 消息转换 ──

    def _convert_message(self, data: dict) -> AstrBotMessage:
        """将希沃消息转换为 AstrBotMessage"""
        from astrbot.api.message_components import Plain, Image, Record

        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.self_id = self._account.uid if self._account else ""
        abm.session_id = self._student.userUid if self._student else ""
        abm.message_id = str(data.get("id", ""))

        # 发送者
        sender_uid = data.get("senderUid", "")
        if self._student and sender_uid == self._student.userUid:
            abm.sender = MessageMember(
                user_id=sender_uid, nickname=self._student.name
            )
        else:
            abm.sender = MessageMember(
                user_id=sender_uid,
                nickname=data.get("senderName", "未知"),
            )

        # 消息内容
        msg_type = data.get("type", 1)
        content = data.get("content", "")
        res_url = data.get("resUrl", "")

        abm.message = []
        if msg_type in (0, 1):  # 文本
            abm.message.append(Plain(text=content))
            abm.message_str = content
        elif msg_type == 2:  # 图片
            if content:
                abm.message.append(Plain(text=content))
            if res_url:
                abm.message.append(Image.fromURL(res_url))
            abm.message_str = content or "[图片]"
        elif msg_type == 3:  # 语音
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
        create_time = data.get("createTime", 0)
        abm.timestamp = create_time // 1000 if create_time else int(time.time())

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
