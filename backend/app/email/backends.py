"""邮件投递后端（Phase 5B）：SMTP（生产）/ Console（开发）/ Memory（测试）。"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailBackend(Protocol):
    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        """投递一封邮件；失败抛异常。"""
        ...


class MemoryBackend:
    """测试用：把发送件收集到列表。"""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, str]] = []

    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        self.sent.append((to, subject, body, from_addr))


class ConsoleBackend:
    """开发用：渲染信息打印到日志。"""

    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        logger.info("EMAIL to=%s from=%s subject=%s", to, from_addr, subject)


class SMTPBackend:
    """生产用：stdlib smtplib。"""

    def __init__(self, *, host: str, port: int, user: str, password: str, use_tls: bool) -> None:
        self._host, self._port = host, port
        self._user, self._password = user, password
        self._use_tls = use_tls

    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(msg)
