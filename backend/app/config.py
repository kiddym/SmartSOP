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
    asset_gc_grace_hours: int = 24  # asset ref_count=0 宽限（Q333）
    attachment_retention_days: int = 30  # 软删附件物理清理宽限（Q115/Q371）

    # PDF 字体目录
    pdf_font_dir: str = "app/assets/fonts"

    # 审计 IP 解析（Q324）：可信代理列表，命中才采信 X-Forwarded-For 链尾客户端 IP
    trusted_proxies: list[str] = Field(default_factory=list)

    @field_validator("cors_origins", "trusted_proxies", mode="before")
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
