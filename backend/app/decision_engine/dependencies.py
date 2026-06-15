"""Decision Engine DI コンテナ: FastAPI Depends 用ファクトリ関数

各コンポーネントの依存解決を行い、FastAPI の Depends パターンで
リクエストスコープまたはシングルトンのアクセスを実現する。
循環 import 回避のため、実装クラスは関数内で遅延 import する。
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING

from app.decision_engine.config import DecisionEngineSettings

if TYPE_CHECKING:
  from app.decision_engine.answer_pipeline import AnswerPipeline
  from app.decision_engine.feedback_service import FeedbackService
  from app.decision_engine.mode_detector import ModeDetector
  from app.decision_engine.normalizer_llm import LLMNormalizer
  from app.decision_engine.rule_aggregator import RuleAggregator
  from app.decision_engine.scorer import DecisionScorer


@functools.lru_cache
def get_decision_engine_settings() -> DecisionEngineSettings:
  """DecisionEngineSettings シングルトンを返す"""
  return DecisionEngineSettings()


@functools.lru_cache
def get_decision_scorer() -> "DecisionScorer":
  """DecisionScorer シングルトンを返す

  MappingDictionaryLoader を解決し、スコアリングエンジンを構築する。
  """
  from app.decision_engine.scorer import DecisionScorer
  from app.services.data_loader import MappingDictionaryLoader

  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return DecisionScorer(loader)


def get_answer_pipeline() -> "AnswerPipeline":
  """AnswerPipeline インスタンスを返す（リクエスト毎に生成）

  LLMNormalizer と DB パスを解決し、パイプラインを構築する。
  """
  from app.decision_engine.answer_pipeline import AnswerPipeline
  from app.decision_engine.normalizer_llm import LLMNormalizer
  from app.services.llm_client import LLMClient

  settings = get_decision_engine_settings()
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  db_path = str(data_dir / "decision_engine.db")
  llm_client = LLMClient()
  normalizer = LLMNormalizer(llm_client, model=settings.normalization_model)
  return AnswerPipeline(db_path, normalizer)


@functools.lru_cache
def get_rule_aggregator() -> "RuleAggregator":
  """RuleAggregator シングルトンを返す（ステートレス）"""
  from app.decision_engine.rule_aggregator import RuleAggregator

  return RuleAggregator()


def get_feedback_service() -> "FeedbackService":
  """FeedbackService インスタンスを返す

  DB パスと設定値（threshold, step）を解決する。
  """
  from app.decision_engine.feedback_service import FeedbackService

  settings = get_decision_engine_settings()
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  db_path = str(data_dir / "decision_engine.db")
  return FeedbackService(
    db_path=db_path,
    threshold=settings.feedback_threshold,
    step=settings.weight_adjustment_step,
  )


def get_mode_detector(context_adaptation: dict | None = None) -> "ModeDetector":
  """ModeDetector インスタンスを返す（リクエスト毎にプロファイルに応じて生成）

  context_adaptation データはプロファイルから取得し、
  リクエスト毎に適切なモード検出器を構築する。
  """
  from app.decision_engine.mode_detector import ModeDetector

  return ModeDetector(context_adaptation=context_adaptation)
