"""ModeDetector ユニットテスト"""

import pytest

from app.decision_engine.mode_detector import ModeDetector


# --- Fixtures ---


@pytest.fixture
def context_adaptation() -> dict:
  """テスト用 context_adaptation 設定"""
  return {
    "modes": {
      "emergency": {"tone": "direct", "detail": "minimal", "focus": "action"},
      "executive_report": {"tone": "formal", "detail": "minimal", "focus": "結論とインパクト"},
      "team_direction": {"tone": "supportive", "detail": "standard", "focus": "背景と期待する行動"},
      "deep_review": {"tone": "analytical", "detail": "comprehensive", "focus": "網羅的分析"},
      "quick_response": {"tone": "concise", "detail": "minimal", "focus": "要点のみ"},
    },
    "switch_triggers": {
      "urgency": ["本番障害が発生"],
      "audience": ["経営会議向け"],
      "mental_state": ["じっくり検討"],
    },
  }


@pytest.fixture
def detector(context_adaptation: dict) -> ModeDetector:
  """テスト用 ModeDetector"""
  return ModeDetector(context_adaptation)


# --- No context_adaptation ---


class TestNoContextAdaptation:
  def test_none_config_returns_none(self) -> None:
    """context_adaptation が None の場合は常に None を返す"""
    detector = ModeDetector(None)
    assert detector.detect_mode("緊急です！") is None

  def test_empty_config_returns_none(self) -> None:
    """context_adaptation が空辞書の場合は常に None を返す"""
    detector = ModeDetector({})
    assert detector.detect_mode("緊急です！") is None

  def test_no_modes_returns_none(self) -> None:
    """modes が空の場合は常に None を返す"""
    detector = ModeDetector({"modes": {}, "switch_triggers": {}})
    assert detector.detect_mode("緊急です！") is None


# --- Urgency triggers ---


class TestUrgencyTriggers:
  def test_builtin_keyword_detects_emergency(self, detector: ModeDetector) -> None:
    """組み込み緊急キーワードで emergency モードを検出する"""
    assert detector.detect_mode("緊急対応をお願いします") == "emergency"

  def test_english_urgency_keyword(self, detector: ModeDetector) -> None:
    """英語の緊急キーワードでも検出する"""
    assert detector.detect_mode("This is urgent, please help") == "emergency"

  def test_custom_trigger_detects_emergency(self, detector: ModeDetector) -> None:
    """カスタムトリガーで emergency モードを検出する"""
    assert detector.detect_mode("本番障害が発生しました") == "emergency"

  def test_case_insensitive_detection(self, detector: ModeDetector) -> None:
    """大文字小文字を区別しない"""
    assert detector.detect_mode("URGENT issue detected") == "emergency"


# --- Emergency persistence ---


class TestEmergencyPersistence:
  def test_emergency_persists_for_threshold_messages(self, detector: ModeDetector) -> None:
    """緊急モードは EMERGENCY_EXIT_THRESHOLD メッセージ分維持される"""
    # 緊急トリガー
    assert detector.detect_mode("緊急対応お願い") == "emergency"
    # 非緊急メッセージ1回目 → まだ emergency 維持
    assert detector.detect_mode("了解しました") == "emergency"
    # 非緊急メッセージ2回目 → まだ emergency 維持
    assert detector.detect_mode("確認しています") == "emergency"

  def test_emergency_exits_after_threshold(self, detector: ModeDetector) -> None:
    """EMERGENCY_EXIT_THRESHOLD 回連続の非緊急メッセージで解除される"""
    # 緊急トリガー
    assert detector.detect_mode("緊急対応お願い") == "emergency"
    # 3回連続の非緊急メッセージ
    assert detector.detect_mode("了解") == "emergency"  # counter=1
    assert detector.detect_mode("確認中") == "emergency"  # counter=2
    assert detector.detect_mode("完了") is None  # counter=3 → 解除

  def test_emergency_resets_counter_on_new_urgency(self, detector: ModeDetector) -> None:
    """緊急モード中に再度緊急トリガーが来るとカウンターリセット"""
    assert detector.detect_mode("緊急です") == "emergency"
    assert detector.detect_mode("了解") == "emergency"  # counter=1
    assert detector.detect_mode("また緊急事態です") == "emergency"  # カウンターリセット
    # 新たに3回必要
    assert detector.detect_mode("OK") == "emergency"  # counter=1
    assert detector.detect_mode("はい") == "emergency"  # counter=2


# --- Audience triggers ---


class TestAudienceTriggers:
  def test_executive_report_keyword(self, detector: ModeDetector) -> None:
    """経営層キーワードで executive_report モードを検出する"""
    assert detector.detect_mode("経営層向けに報告書を作成して") == "executive_report"

  def test_team_direction_keyword(self, detector: ModeDetector) -> None:
    """チームキーワードで team_direction モードを検出する"""
    assert detector.detect_mode("チームに方針を伝えたい") == "team_direction"

  def test_cto_keyword_detects_executive(self, detector: ModeDetector) -> None:
    """CTO キーワードで executive_report を検出する"""
    assert detector.detect_mode("CTOに報告する内容をまとめて") == "executive_report"

  def test_english_team_keyword(self, detector: ModeDetector) -> None:
    """英語 team キーワードで team_direction を検出する"""
    assert detector.detect_mode("Prepare a team briefing") == "team_direction"


# --- Mental state triggers ---


class TestMentalStateTriggers:
  def test_deep_review_keyword(self, detector: ModeDetector) -> None:
    """深い思考キーワードで deep_review モードを検出する"""
    assert detector.detect_mode("アーキテクチャについて考えたい") == "deep_review"

  def test_quick_response_keyword(self, detector: ModeDetector) -> None:
    """簡潔さキーワードで quick_response モードを検出する"""
    assert detector.detect_mode("簡単に教えて") == "quick_response"

  def test_english_quick_keyword(self, detector: ModeDetector) -> None:
    """英語 quick キーワードで quick_response を検出する"""
    assert detector.detect_mode("Give me a quick answer") == "quick_response"

  def test_recent_turns_context(self, detector: ModeDetector) -> None:
    """直近ターンのコンテキストからモードを検出する"""
    recent_turns = [
      {"content": "設計レビューをしましょう"},
      {"content": "はい、始めましょう"},
    ]
    assert detector.detect_mode("次のステップは？", recent_turns) == "deep_review"

  def test_custom_mental_state_trigger(self, detector: ModeDetector) -> None:
    """カスタム mental_state トリガーで検出する"""
    assert detector.detect_mode("じっくり検討したい") == "deep_review"


# --- format_mode_prompt ---


class TestFormatModePrompt:
  def test_formats_correctly(self, detector: ModeDetector) -> None:
    """モード設定が正しいプロンプト形式に整形される"""
    result = detector.format_mode_prompt("emergency")
    assert result == (
      "## Current Mode: emergency\n"
      "- Tone: direct\n"
      "- Detail: minimal\n"
      "- Focus: action"
    )

  def test_unknown_mode_returns_empty(self, detector: ModeDetector) -> None:
    """存在しないモード名の場合は空文字列を返す"""
    assert detector.format_mode_prompt("nonexistent") == ""

  def test_executive_report_format(self, detector: ModeDetector) -> None:
    """executive_report モードのフォーマット確認"""
    result = detector.format_mode_prompt("executive_report")
    assert "## Current Mode: executive_report" in result
    assert "- Tone: formal" in result
    assert "- Detail: minimal" in result
    assert "- Focus: 結論とインパクト" in result


# --- get_mode_config ---


class TestGetModeConfig:
  def test_existing_mode(self, detector: ModeDetector) -> None:
    """存在するモードの設定を返す"""
    config = detector.get_mode_config("emergency")
    assert config == {"tone": "direct", "detail": "minimal", "focus": "action"}

  def test_nonexistent_mode(self, detector: ModeDetector) -> None:
    """存在しないモードの場合は空辞書を返す"""
    assert detector.get_mode_config("nonexistent") == {}


# --- Priority: urgency > audience > mental_state ---


class TestPriority:
  def test_urgency_overrides_audience(self, detector: ModeDetector) -> None:
    """緊急性が聴衆依存より優先される"""
    # メッセージに両方のトリガーが含まれる場合
    result = detector.detect_mode("緊急: 経営層に報告が必要です")
    assert result == "emergency"

  def test_urgency_overrides_mental_state(self, detector: ModeDetector) -> None:
    """緊急性が認知状態より優先される"""
    result = detector.detect_mode("緊急でじっくり考える必要がある")
    assert result == "emergency"

  def test_audience_overrides_mental_state(self, detector: ModeDetector) -> None:
    """聴衆依存が認知状態より優先される"""
    # 緊急でないが両方含む場合 — audience が先にチェックされる
    result = detector.detect_mode("経営層向けに簡単にまとめて")
    assert result == "executive_report"
