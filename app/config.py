from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_ALLOWED_EXT = (
    ".doc,.docx,.xls,.xlsx,.csv,.txt,.log,.cfg,.conf,.ini,"
    ".json,.xml,.yml,.md,.pdf,.ppt,.pptx,.pkt,.pka,.zip,.png,.jpg"
)


class Settings(BaseSettings):
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_ENV: str = "production"

    SESSION_COOKIE_NAME: str = "catatan_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "strict"
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30

    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_LOCKOUT_MINUTES: int = 15

    DATABASE_PATH: str = "data/app.db"
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = DEFAULT_ALLOWED_EXT

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_ext_set(self) -> set[str]:
        ext_list = self.ALLOWED_EXTENSIONS.split(",")
        return {ext.strip().lower() for ext in ext_list if ext.strip()}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def abs_database_path(self) -> Path:
        p = Path(self.DATABASE_PATH)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def abs_upload_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        return p if p.is_absolute() else BASE_DIR / p


settings = Settings()

# 5 Kategori Tetap (slug aman URL, tanpa karakter '+')
CATEGORIES = [
    {
        "slug": "word",
        "name": "Word",
        "description": "Dokumen teks, format Word, dan panduan kerja",
        "icon": "file-text",
    },
    {
        "slug": "excel",
        "name": "Excel",
        "description": "Spreadsheet, kalkulasi data, dan tabel kerja",
        "icon": "table-2",
    },
    {
        "slug": "notepadpp",
        "name": "Notepad++",
        "description": "Script, snippet kode, konfigurasi, dan teks polos",
        "icon": "code-2",
    },
    {
        "slug": "cisco",
        "name": "Cisco",
        "description": (
            "Topologi Packet Tracer (.pkt/.pka) dan config perangkat"
        ),
        "icon": "network",
    },
    {
        "slug": "kuliah",
        "name": "Kuliah",
        "description": (
            "Catatan perkuliahan, modul akademik, dan referensi tugas"
        ),
        "icon": "graduation-cap",
    },
]

CATEGORY_MAP = {c["slug"]: c for c in CATEGORIES}
