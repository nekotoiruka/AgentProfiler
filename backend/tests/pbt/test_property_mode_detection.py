"""Property 15: モード検出と switch_trigger の一致性

switch_triggers 条件に合致するメッセージで対応モード名を返し、
非合致で None を返すことを検証する。

**Validates: Requirements 9.1**
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.decision_engine.mode_detector import (
  ModeDetector,
  URGENCY_KEYWORDS,
  AUDIENCE_KEYWORDS,
  MENTAL_STATE_KEYWORDS,
)


CONTEXT_ADAPTATION = {
  "modes": {
    "emergency": {"tone": "direct", "detail": "minimal", "focus": "action"},
    "executive_report": {"tone": "formal", "detail": "minimal", "focus": "結論"},
    "team_direction": {"tone": "supportive", "detail": "standard", "focus": "背景"},
    "deep_review": {"tone": "analytical", "detail": "comprehensive", "focus": "分析"},
    "quick_response": {"tone": "concise", "detail": "minimal", "focus": "要点"},
  },
  "switch_triggers": {
    "urgency": ["本番障害発生"],
    "audience": ["経営層向け"],
    "mental_state": ["じっくり分析"],
  },
}


@given(keyword=st.sampled_from(URGENCY_KEYWORDS))
@settings(max_examples=50)
def test_urgency_keyword_triggers_emergency(keyword):
  """緊急キーワードを含むメッセージは必ず emergency を返す"""
  detector = ModeDetector(CONTEXT_ADAPTATION)
  message = f"このタスクは{keyword}です、対応お願いします"
  result = detector.detect_mode(message)
  assert result == "emergency", f"Expected 'emergency' for keyword '{keyword}', got '{result}'"


@given(
  text=st.text(
    min_size=5, max_size=50,
    alphabet=st.characters(whitelist_categories=("L",), whitelist_characters="あいうえおかきくけこ ")
  )
)
@settings(max_examples=100)
def test_neutral_message_no_mode(text):
  """トリガーキーワードを含まないメッセージは None を返す"""
  # Ensure the generated text doesn't accidentally contain trigger keywords
  all_keywords = (
    URGENCY_KEYWORDS
    + [kw for keywords in AUDIENCE_KEYWORDS.values() for kw in keywords]
    + [kw for keywords in MENTAL_STATE_KEYWORDS.values() for kw in keywords]
    + CONTEXT_ADAPTATION["switch_triggers"]["urgency"]
    + CONTEXT_ADAPTATION["switch_triggers"]["audience"]
    + CONTEXT_ADAPTATION["switch_triggers"]["mental_state"]
  )
  text_lower = text.lower()
  assume(not any(kw.lower() in text_lower for kw in all_keywords))

  detector = ModeDetector(CONTEXT_ADAPTATION)
  result = detector.detect_mode(text)
  assert result is None, f"Expected None for neutral text '{text}', got '{result}'"
