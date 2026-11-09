"""以專案根目錄定位 .env，不受啟動目錄影響。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    session_secret: str
    https_only: bool = False

    @classmethod
    def from_env(cls):
        secret = os.getenv("SESSION_SECRET", "").strip()
        if len(secret) < 32 or secret == "請填入至少32字元的隨機金鑰":
            raise RuntimeError("SESSION_SECRET 未設定或不足 32 字元，請在 .env 設定安全隨機金鑰。")
        environment = os.getenv("APP_ENV", "development").lower()
        if environment not in {"development", "production"}:
            raise RuntimeError("APP_ENV 必須是 development 或 production。")
        secure = os.getenv("SESSION_HTTPS_ONLY", "true" if environment == "production" else "false").lower()
        if secure not in {"true", "false"}:
            raise RuntimeError("SESSION_HTTPS_ONLY 必須是 true 或 false。")
        if environment == "production" and secure != "true":
            raise RuntimeError("正式環境必須設定 SESSION_HTTPS_ONLY=true 並使用 HTTPS。")
        return cls(session_secret=secret, https_only=secure == "true")
