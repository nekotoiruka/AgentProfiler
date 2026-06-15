"""コンテキスト適応モード検出エンジン"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 緊急性を示すキーワード
URGENCY_KEYWORDS = [
  "緊急", "至急", "urgent", "asap", "今すぐ", "障害", "ダウン",
  "インシデント", "incident", "本番障害", "セキュリティ", "データ漏洩",
  "critical", "emergency", "immediately",
]

# 聴衆依存のキーワードとモード
AUDIENCE_KEYWORDS: dict[str, list[str]] = {
  "executive_report": ["経営", "役員", "CTO", "CEO", "取締役", "上位マネジメント", "executive"],
  "team_direction": ["チーム", "メンバー", "部下", "指示", "方針", "team"],
}

# 認知状態のキーワードとモード
MENTAL_STATE_KEYWORDS: dict[str, list[str]] = {
  "deep_review": ["設計レビュー", "アーキテクチャ", "じっくり", "網羅的に", "深く考え", "design review"],
  "quick_response": ["簡単に", "一言で", "手短に", "クイック", "quick", "briefly"],
}


class ModeDetector:
  """コンテキスト適応モード検出エンジン

  ユーザーメッセージと直近会話履歴から、
  context_adaptation の switch_triggers 条件と照合し、
  適用すべき Adaptation_Mode を判定する。
  """

  EMERGENCY_EXIT_THRESHOLD = 3

  def __init__(self, context_adaptation: dict | None = None):
    self._modes = context_adaptation.get("modes", {}) if context_adaptation else {}
    self._triggers = context_adaptation.get("switch_triggers", {}) if context_adaptation else {}
    self._emergency_counter = 0
    self._current_mode: str | None = None

  def detect_mode(self, message: str, recent_turns: list[dict] | None = None) -> str | None:
    """メッセージと直近5ターンからモードを判定する

    Priority: urgency > audience > mental_state
    Emergency mode persists until EMERGENCY_EXIT_THRESHOLD consecutive non-urgent messages.

    Returns:
      mode_name or None (該当モードなし)
    """
    if not self._modes:
      return None

    recent = (recent_turns or [])[-5:]

    # 1. 緊急性チェック（最優先）
    if self._check_urgency_triggers(message):
      self._emergency_counter = 0
      self._current_mode = "emergency"
      return "emergency"

    # 緊急モード解除チェック
    if self._current_mode == "emergency":
      self._emergency_counter += 1
      if self._emergency_counter < self.EMERGENCY_EXIT_THRESHOLD:
        return "emergency"  # まだ維持
      else:
        self._current_mode = None  # 解除

    # 2. 聴衆依存チェック
    audience_mode = self._check_audience_triggers(message)
    if audience_mode and audience_mode in self._modes:
      self._current_mode = audience_mode
      return audience_mode

    # 3. 認知状態チェック
    mental_mode = self._check_mental_state_triggers(message, recent)
    if mental_mode and mental_mode in self._modes:
      self._current_mode = mental_mode
      return mental_mode

    return self._current_mode if self._current_mode in self._modes else None

  def get_mode_config(self, mode_name: str) -> dict[str, str]:
    """モード名から設定(tone, detail, focus)を取得する"""
    return self._modes.get(mode_name, {})

  def format_mode_prompt(self, mode_name: str) -> str:
    """モード設定をシステムプロンプト追記形式に整形する"""
    config = self.get_mode_config(mode_name)
    if not config:
      return ""
    return (
      f"## Current Mode: {mode_name}\n"
      f"- Tone: {config.get('tone', '')}\n"
      f"- Detail: {config.get('detail', '')}\n"
      f"- Focus: {config.get('focus', '')}"
    )

  def _check_urgency_triggers(self, text: str) -> bool:
    """緊急性トリガーの検出"""
    text_lower = text.lower()
    # カスタムトリガーを優先チェック
    custom_triggers = self._triggers.get("urgency", [])
    for trigger in custom_triggers:
      if trigger.lower() in text_lower:
        return True
    # 組み込みキーワードチェック
    for keyword in URGENCY_KEYWORDS:
      if keyword.lower() in text_lower:
        return True
    return False

  def _check_audience_triggers(self, text: str) -> str | None:
    """聴衆依存トリガーの検出 → mode_name"""
    text_lower = text.lower()
    # カスタムトリガーチェック
    custom_triggers = self._triggers.get("audience", [])
    for trigger in custom_triggers:
      if trigger.lower() in text_lower:
        # カスタムトリガーに対応するモードを探索
        for mode, keywords in AUDIENCE_KEYWORDS.items():
          for kw in keywords:
            if kw.lower() in trigger.lower():
              return mode
    # 組み込みキーワードチェック
    for mode, keywords in AUDIENCE_KEYWORDS.items():
      for keyword in keywords:
        if keyword.lower() in text_lower:
          return mode
    return None

  def _check_mental_state_triggers(self, text: str, recent_turns: list[dict]) -> str | None:
    """認知状態トリガーの検出 → mode_name"""
    text_lower = text.lower()
    # カスタムトリガーチェック
    custom_triggers = self._triggers.get("mental_state", [])
    for trigger in custom_triggers:
      if trigger.lower() in text_lower:
        for mode, keywords in MENTAL_STATE_KEYWORDS.items():
          for kw in keywords:
            if kw.lower() in trigger.lower():
              return mode
    # 組み込みキーワードチェック
    for mode, keywords in MENTAL_STATE_KEYWORDS.items():
      for keyword in keywords:
        if keyword.lower() in text_lower:
          return mode
    # 直近ターンのコンテキストもチェック
    combined_text = " ".join(t.get("content", "") for t in recent_turns).lower()
    for mode, keywords in MENTAL_STATE_KEYWORDS.items():
      for keyword in keywords:
        if keyword.lower() in combined_text:
          return mode
    return None
