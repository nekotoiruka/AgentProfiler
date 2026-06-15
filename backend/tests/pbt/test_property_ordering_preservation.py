"""Property 7: Ordering 回答の順序保存

任意の step choice_id 順列が DB にそのまま保存されることを検証する。

Feature: agent-decision-engine
**Validates: Requirements 5.6**
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.answer_pipeline import AnswerPipeline


STEP_IDS = ["step_gather", "step_define", "step_generate", "step_evaluate", "step_decide", "step_execute"]


@given(order=st.permutations(STEP_IDS))
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_ordering_preserved_in_db(order):
  """任意の順列が DB に保存後も同じ順序で取得できる

  **Validates: Requirements 5.6**
  """
  fd, db_path = tempfile.mkstemp(suffix=".db")
  os.close(fd)

  try:
    normalizer = MagicMock()
    normalizer.normalize = AsyncMock(return_value=None)
    pipeline = AnswerPipeline(db_path=db_path, llm_normalizer=normalizer)
    await pipeline.init_db()

    # Ordering回答をpredefinedとして保存（choice_idにJSON配列を格納）
    order_json = json.dumps(order)
    result = await pipeline.process_predefined(
      session_id="test_session",
      question_id="rf_001",
      choice_id=order_json,
      choice_label="ordering_answer",
      policy_text=f"when_problem_solving: {', '.join(order[:3])} の順で思考する",
    )

    # 保存されたrawデータのchoice_idをデコードし、順序が保存されていることを確認
    stored_order = json.loads(result["raw"]["choice_id"])
    assert stored_order == list(order), f"Order mismatch: expected {order}, got {stored_order}"
  finally:
    if os.path.exists(db_path):
      os.unlink(db_path)
