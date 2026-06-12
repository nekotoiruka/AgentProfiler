"""APIの依存性注入: サービスインスタンスの初期化とDI提供

FastAPIのDependsパターンでリクエストスコープのアクセスを実現する。
起動時に初期化し、モジュールレベルでキャッシュする。
"""

import logging
from pathlib import Path

from app.core.normalizer import Normalizer
from app.core.profile_generator import ProfileGenerator
from app.core.scoring import ScoringEngine
from app.services.data_loader import MappingDictionaryLoader, QuestionDataLoader
from app.services.llm_client import LLMClient
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

# データファイルのパス（プロジェクトルートからの相対）
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_DATA_DIR = _BASE_DIR / "data"
_MAPPING_PATH = _DATA_DIR / "mapping_dictionary.json"
_QUESTIONS_PATH = _DATA_DIR / "questions.yaml"
_DB_PATH = _DATA_DIR / "sessions.db"

# サービスインスタンス（起動時に初期化）
_mapping_loader: MappingDictionaryLoader | None = None
_question_loader: QuestionDataLoader | None = None
_session_manager: SessionManager | None = None
_scoring_engine: ScoringEngine | None = None
_normalizer: Normalizer | None = None
_profile_generator: ProfileGenerator | None = None
_llm_client: LLMClient | None = None


async def init_services() -> None:
  """全サービスを初期化する（アプリ起動時に呼び出す）"""
  global _mapping_loader, _question_loader, _session_manager
  global _scoring_engine, _normalizer, _profile_generator, _llm_client

  # Mapping Dictionary のロード
  _mapping_loader = MappingDictionaryLoader(_MAPPING_PATH)
  mapping_dict = _mapping_loader.load()

  # Question Data のロード
  _question_loader = QuestionDataLoader(_QUESTIONS_PATH, _mapping_loader)
  categories = _question_loader.load()

  # 全質問数を計算
  total_questions = sum(len(cat.questions) for cat in categories)

  # Session Manager の初期化
  _session_manager = SessionManager(_DB_PATH, total_questions)
  await _session_manager.init_db()

  # Scoring Engine の初期化
  _scoring_engine = ScoringEngine(mapping_dict)

  # Normalizer の初期化（理論的境界値を使用）
  _normalizer = Normalizer(mapping_dict.metadata.theoretical_bounds)

  # Profile Generator の初期化
  _profile_generator = ProfileGenerator()

  # LLM Client の初期化（API Key が未設定でも起動可能）
  _llm_client = LLMClient()

  logger.info(
    "Services initialized: %d categories, %d questions, LLM=%s",
    len(categories),
    total_questions,
    "enabled" if _llm_client.enabled else "disabled",
  )


def get_mapping_loader() -> MappingDictionaryLoader:
  """MappingDictionaryLoaderインスタンスを返す"""
  assert _mapping_loader is not None, "Services not initialized"
  return _mapping_loader


def get_question_loader() -> QuestionDataLoader:
  """QuestionDataLoaderインスタンスを返す"""
  assert _question_loader is not None, "Services not initialized"
  return _question_loader


def get_session_manager() -> SessionManager:
  """SessionManagerインスタンスを返す"""
  assert _session_manager is not None, "Services not initialized"
  return _session_manager


def get_scoring_engine() -> ScoringEngine:
  """ScoringEngineインスタンスを返す"""
  assert _scoring_engine is not None, "Services not initialized"
  return _scoring_engine


def get_normalizer() -> Normalizer:
  """Normalizerインスタンスを返す"""
  assert _normalizer is not None, "Services not initialized"
  return _normalizer


def get_profile_generator() -> ProfileGenerator:
  """ProfileGeneratorインスタンスを返す"""
  assert _profile_generator is not None, "Services not initialized"
  return _profile_generator


def get_llm_client() -> LLMClient | None:
  """LLMClientインスタンスを返す（未設定時はNone）"""
  return _llm_client
