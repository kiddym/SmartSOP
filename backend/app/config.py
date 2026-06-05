"""应用配置（Phase 1）。

用 pydantic-settings 从环境变量 / `.env` 读取配置。所有运行期可调项集中于此，
禁止散落在各模块里 `os.getenv`。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置单例。字段名小写，环境变量大小写不敏感。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 运行环境
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # 数据库
    database_url: str = "mysql+pymysql://root:root@localhost:3306/smart_sop"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # CORS（逗号分隔）
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # 上传
    upload_max_size_mb: int = 50

    # 存储根目录（Q342）：永久 asset = {storage_dir}/asset/...；临时上传 = {storage_dir}/tmp/uploads
    storage_dir: str = "var/storage"

    # Word 解析（Q345）
    parse_timeout_seconds: int = 30

    # 后台清理（§53.2 / Q332）
    cleanup_hour: int = 3  # 每日附件 + asset GC 执行时刻（服务器时区）
    temp_upload_ttl_hours: int = 24  # 临时上传过期时长（Q141）
    notify_due_soon_days: int = 3  # 工单到期提醒提前天数（Phase 5A）
    asset_gc_grace_hours: int = 24  # asset ref_count=0 宽限（Q333）
    attachment_retention_days: int = 30  # 软删附件物理清理宽限（Q115/Q371）

    # 邮件通知（Phase 5B）
    email_backend: str = "console"  # console | smtp | memory(测试)
    email_from: str = "no-reply@smart-cmms.local"
    email_max_attempts: int = 5  # outbox 投递重试上限
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # --- Stripe 计费（Phase 6，test-mode） ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    billing_checkout_success_url: str = "http://localhost:5173/billing/settings?checkout=success"
    billing_checkout_cancel_url: str = "http://localhost:5173/billing/plans?checkout=cancel"
    billing_portal_return_url: str = "http://localhost:5173/billing/settings"
    # 文件存储后端（Phase 5B）
    storage_backend: str = "local"  # local | s3
    s3_bucket: str = ""
    s3_endpoint_url: str = ""  # 空=AWS 默认 endpoint；填写以兼容 MinIO 等
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # PDF 字体目录
    pdf_font_dir: str = "app/assets/fonts"

    # 审计 IP 解析（Q324）：可信代理列表，命中才采信 X-Forwarded-For 链尾客户端 IP
    trusted_proxies: list[str] = Field(default_factory=list)

    # 品牌
    app_name: str = "Smart CMMS"

    # 认证 / JWT
    secret_key: str = "dev-insecure-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # i18n
    default_locale: str = "zh-CN"
    supported_locales: list[str] = Field(default_factory=lambda: ["zh-CN"])

    @field_validator("cors_origins", "trusted_proxies", "supported_locales", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """允许用逗号分隔的字符串配置列表型字段。"""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """缓存的配置单例。测试中可用 `get_settings.cache_clear()` 重置。"""
    return Settings()


settings = get_settings()
