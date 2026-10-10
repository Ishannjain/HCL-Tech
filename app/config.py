from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / '.env'), extra='ignore')
    data_dir: Path = ROOT / 'data'
    runtime_dir: Path = ROOT / 'runtime'
    mock_llm: bool = True
    retrieval_backend: str = 'chroma'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    retrieval_top_k: int = 8
    nvidia_api_key: str = ''
    nvidia_base_url: str = 'https://integrate.api.nvidia.com/v1'
    nvidia_model: str = 'nvidia/nemotron-3-super-120b-a12b'
    llm_timeout_seconds: float = 60
    admin_api_key: str = ''
    timezone: str = 'Asia/Kolkata'

    @property
    def db_path(self):
        return self.runtime_dir / 'retail.sqlite3'

@lru_cache
def get_settings():
    return Settings()
