"""記憶検索ユーティリティ

ChatService と DiscussionEngine で共用する
search_memory ツール関連のヘルパー関数。
"""

import json
import logging
from pathlib import Path

import aiosqlite
import yaml

from app.evolution.context_layer_manager import ContextLayerManager

logger = logging.getLogger(__name__)

# sessions.db / questions.yaml のパス
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_SESSIONS_DB_PATH = str(_DATA_DIR / "sessions.db")
_QUESTIONS_PATH = _DATA_DIR / "questions.yaml"


async def get_answer_summaries(profile_id: str, query: str) -> str:
  """sessions.db からユーザーの実回答テキストを復元する。

  質問テキスト + 選んだ選択肢ラベルを組み合わせて、
  ユーザーが実際に答えた内容を人間可読な形式で返す。

  Args:
    profile_id: プロファイル ID（セッション特定用）
    query: 検索クエリ（現時点では全回答を返す）

  Returns:
    回答サマリーテキスト。取得失敗時は空文字列。
  """
  try:
    if not _QUESTIONS_PATH.exists():
      return ""
    with open(_QUESTIONS_PATH, "r") as f:
      q_data = yaml.safe_load(f)

    # question_id → {text, choices: {id: label}} のマップを構築
    q_map: dict[str, dict] = {}
    for cat in q_data.get("categories", []):
      for q in cat.get("questions", []):
        qid = q.get("id", "")
        choices = {c["id"]: c.get("label", "") for c in q.get("choices", [])}
        q_map[qid] = {"text": q.get("text", ""), "choices": choices}

    # 完了済みセッションの回答を取得
    async with aiosqlite.connect(_SESSIONS_DB_PATH) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT session_id FROM sessions WHERE status = 'complete' "
        "ORDER BY rowid DESC LIMIT 1"
      ) as cur:
        session_row = await cur.fetchone()
        if not session_row:
          return ""
        session_id = session_row["session_id"]

      async with db.execute(
        "SELECT question_id, choice_id, selected_options FROM answers "
        "WHERE session_id = ? ORDER BY submitted_at",
        (session_id,),
      ) as cur:
        answers = await cur.fetchall()

    # 回答を人間可読テキストに変換
    lines: list[str] = []
    for ans in answers:
      qid = ans["question_id"]
      if qid not in q_map:
        continue
      q_info = q_map[qid]
      q_text = q_info["text"]

      if ans["choice_id"]:
        choice_label = q_info["choices"].get(ans["choice_id"], ans["choice_id"])
        lines.append(f"Q: {q_text}")
        lines.append(f"A: {choice_label}")
        lines.append("")
      elif ans["selected_options"]:
        opts = json.loads(ans["selected_options"])
        labels = [q_info["choices"].get(o, o) for o in opts]
        lines.append(f"Q: {q_text}")
        lines.append(f"A: {', '.join(labels)}")
        lines.append("")

    return "\n".join(lines) if lines else ""

  except Exception as e:
    logger.warning("Failed to get answer summaries: %s", e)
    return ""


async def execute_search_memory(
  name: str,
  args: dict,
  profile_id: str,
  clm: ContextLayerManager,
) -> str:
  """search_memory ツールの実行ロジック（ChatService/DiscussionEngine 共用）。

  Args:
    name: ツール名（"search_memory" であること）
    args: ツール引数 {"query": "..."}
    profile_id: 対象プロファイル ID
    clm: ContextLayerManager インスタンス

  Returns:
    検索結果テキスト
  """
  if name != "search_memory":
    return f"Unknown tool: {name}"

  query = args.get("query", "")
  try:
    profile = clm.get_profile(profile_id)
  except (KeyError, AttributeError):
    return "記憶データにアクセスできません。"

  parts = []

  # 1. lexical_tags
  if profile.lexical_tags:
    parts.append("【関心事・趣味・スキル（実際の回答に基づく）】")
    parts.append(", ".join(profile.lexical_tags))

  # 2. 実回答データ
  answer_text = await get_answer_summaries(profile_id, query)
  if answer_text:
    parts.append("")
    parts.append("【アンケートで実際に答えた内容】")
    parts.append(answer_text)

  # 3. semantic_contexts（参考）
  if profile.semantic_contexts:
    parts.append("")
    parts.append("【推定された行動傾向（参考情報）】")
    domain_labels = {
      "problem_solving": "問題解決",
      "communication_style": "コミュニケーション",
      "work_rhythm": "仕事のリズム",
      "analog_habits": "アナログな習慣",
      "lifestyle_preferences": "ライフスタイル",
    }
    for domain, text in profile.semantic_contexts.items():
      label = domain_labels.get(domain, domain)
      parts.append(f"[{label}] {text}")

  if not parts:
    return "関連する記憶は見つかりませんでした。"
  return "\n".join(parts)


def build_rich_system_prompt(
  profile,
  agent_display_name: str,
  theme: str | None = None,
  other_participants: list[str] | None = None,
) -> str:
  """ProfileOutput 全体を使ったリッチなシステムプロンプトを構築する。

  ChatService と DiscussionEngine で共用可能。
  議論用の場合は theme と other_participants を指定する。

  Args:
    profile: ProfileOutput インスタンス
    agent_display_name: このエージェントの表示名
    theme: 議論テーマ（議論モード時のみ指定）
    other_participants: 他の参加者名リスト（議論モード時のみ指定）

  Returns:
    システムプロンプト文字列
  """
  parts: list[str] = []

  # ペルソナ基本情報
  parts.append("# あなたの人格設定")
  parts.append("")
  if hasattr(profile, "persona") and profile.persona:
    p = profile.persona
    nickname = p.nickname or agent_display_name
    parts.append(f"あなたは「{nickname}」という名前の人格です。")
    details = []
    if p.age_range:
      details.append(f"年齢層: {p.age_range}")
    if p.role:
      details.append(f"役割: {p.role}")
    if p.industry:
      details.append(f"業界: {p.industry}")
    if p.experience_years:
      details.append(f"経験: {p.experience_years}")
    if details:
      parts.append("、".join(details))
    parts.append("")

  # コミュニケーションスタイル
  if hasattr(profile, "communication_tone") and profile.communication_tone:
    ct = profile.communication_tone
    parts.append("## 話し方のルール（必ず守ること）")
    parts.append("")
    if ct.pronoun:
      parts.append(f"- 一人称: 「{ct.pronoun}」を使う")
    if ct.formality:
      parts.append(f"- 敬語/カジュアル: {ct.formality}")
    if ct.text_style:
      parts.append(f"- テキストの特徴: {ct.text_style}")
    if ct.emotion_level:
      parts.append(f"- 感情表現: {ct.emotion_level}")
    if ct.humor:
      parts.append(f"- ユーモア: {ct.humor}")
    if hasattr(ct, "sentence_ending") and ct.sentence_ending:
      parts.append(f"- 文末表現の癖: {ct.sentence_ending}")
    if hasattr(ct, "filler_words") and ct.filler_words:
      parts.append(f"- よく使うフィラー/つなぎ言葉: {ct.filler_words}")
    parts.append("")

  # 思考パターン
  if profile.semantic_contexts:
    parts.append("## あなたの思考パターン・価値観")
    parts.append("")
    domain_labels = {
      "problem_solving": "問題解決の仕方",
      "communication_style": "コミュニケーションの傾向",
      "work_rhythm": "仕事のリズム",
      "analog_habits": "アナログな習慣",
      "lifestyle_preferences": "ライフスタイルの好み",
    }
    for domain, description in profile.semantic_contexts.items():
      label = domain_labels.get(domain, domain)
      parts.append(f"### {label}")
      parts.append(description)
      parts.append("")

  # 意思決定スタイル
  base_os = profile.base_os
  parts.append("## 意思決定スタイル")
  parts.append(f"あなたの意思決定の型: 「{base_os.decision_style}」")
  parts.append("")

  # 関心事・趣味・スキル（lexical_tags をプロンプトに直接埋め込む）
  if hasattr(profile, "lexical_tags") and profile.lexical_tags:
    parts.append("## あなたの関心事・趣味・スキル")
    parts.append("")
    parts.append(", ".join(profile.lexical_tags))
    parts.append("")

  # ガードレール
  if base_os.do_not_list:
    parts.append("## 絶対にやってはいけないこと")
    for item in base_os.do_not_list:
      parts.append(f"- {item}")
    parts.append("")

  # 議論モード固有の指示
  if theme:
    parts.append("## 議論の設定")
    parts.append(f"テーマ: {theme}")
    if other_participants:
      parts.append(f"他の参加者: {', '.join(other_participants)}")
    parts.append("")
    parts.append("## 重要な指示")
    parts.append(
      "上記の人格設定に基づいて議論に参加してください。"
      "あなたは AI ではなく、この人格を持つ人間として発言します。"
      "自分の経験・価値観・好みに基づいて意見を述べてください。"
      "他の参加者の発言に対して、賛同・反論・補足を自然に行ってください。"
      "簡潔に、1〜3文で発言してください。"
    )
    parts.append("")
    parts.append("## 絶対に守るべきルール")
    parts.append(
      "- プロファイルに記載されていない趣味・経験・エピソードを捏造しないでください。"
      "知らないことは「わからない」「経験がない」と正直に言ってください。"
    )
    parts.append(
      "- 「関心事・趣味・スキル」セクションに記載されているキーワードのみが"
      "あなたの実際の経験です。それ以外の趣味や体験を作り話しないでください。"
    )
  else:
    parts.append("## 重要な指示")
    parts.append(
      "上記の人格設定に基づいて一貫した受け答えをしてください。"
      "あなたは AI ではなく、この人格を持つ人間として振る舞います。"
      "質問されたら、この人格の経験・価値観・好みに基づいて答えてください。"
      "「AIなので趣味はありません」のような返答は絶対にしないでください。"
    )
    parts.append("")
    parts.append("## 絶対に守るべきルール")
    parts.append(
      "- プロファイルに記載されていない趣味・経験・エピソードを捏造しないでください。"
      "知らないことは「わからない」「やったことない」と正直に言ってください。"
    )
    parts.append(
      "- 「関心事・趣味・スキル」セクションに記載されているキーワードのみが"
      "あなたの実際の経験です。それ以外の趣味や体験を作り話しないでください。"
    )

  return "\n".join(parts)
