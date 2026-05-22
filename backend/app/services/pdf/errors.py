"""PDF 错误助手（pdf-rendering §13 / §59.4·Q362）。"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.errors import app_error


def pdf_timeout() -> HTTPException:
    return app_error(
        status.HTTP_504_GATEWAY_TIMEOUT, "PDF_TIMEOUT", "PDF 生成超时（> 60 秒），请简化内容后重试"
    )


def pdf_failed() -> HTTPException:
    return app_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "PDF_GENERATION_FAILED", "PDF 生成失败，请稍后重试"
    )
