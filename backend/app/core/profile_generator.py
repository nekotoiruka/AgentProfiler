"""Profile Generator: 正規化スコアから3層構造プロファイルJSONを生成"""

from __future__ import annotations

import json
import re
import threading
from typing import TYPE_CHECKING

from app.models.profile import BaseOS, ContextLayers, ProfileOutput
from app.models.question import Question
from app.models.scores import NormalizedScores
from app.models.session import Answer

if TYPE_CHECKING:
  from app.decision_engine.models import (
    AnswerMetadataSummary,
    ContextAdaptationOutput,
    DecisionModelOutput,
    FailurePatternsOutput,
    ReasoningFlowOutput,
    RuleHierarchyOutput,
  )
  from app.decision_engine.rule_aggregator import RuleAggregator
  from app.decision_engine.scorer import DecisionScorer


# 軸名と両極のマッピング（独自用語: MBTIコードは使用しない）
_AXIS_POLES: dict[str, tuple[str, str]] = {
  "extroverted_introverted": ("extroverted", "introverted"),
  "sensing_intuition": ("sensing", "intuitive"),
  "thinking_feeling": ("thinking", "feeling"),
  "judging_perceiving": ("judging", "perceiving"),
}

# 16タイプ日本語名マッピング（独自ネーミング、MBTIコード不使用）
_TYPE_NAMES: dict[str, str] = {
  "extroverted_sensing_thinking_judging": "統率の鉄壁",
  "extroverted_sensing_thinking_perceiving": "刹那の切り拓き",
  "extroverted_sensing_feeling_judging": "絆の守護者",
  "extroverted_sensing_feeling_perceiving": "煌めきの演者",
  "extroverted_intuitive_thinking_judging": "覇道の戦略家",
  "extroverted_intuitive_thinking_perceiving": "混沌の発明家",
  "extroverted_intuitive_feeling_judging": "導きの旗手",
  "extroverted_intuitive_feeling_perceiving": "閃光の触媒",
  "introverted_sensing_thinking_judging": "鋼鉄の番人",
  "introverted_sensing_thinking_perceiving": "孤高の職人",
  "introverted_sensing_feeling_judging": "静謐の献身者",
  "introverted_sensing_feeling_perceiving": "幽玄の芸術家",
  "introverted_intuitive_thinking_judging": "深淵の設計者",
  "introverted_intuitive_thinking_perceiving": "無限の解析者",
  "introverted_intuitive_feeling_judging": "慈愛の導師",
  "introverted_intuitive_feeling_perceiving": "静寂の夢想家",
}

# balanced を含むパターンのフォールバック名
_BALANCED_TYPE_NAME = "均衡の探求者"

# do_not_listテンプレート: 各軸の偏りに対応するメッセージ
# 閾値: <0.35 (低) / >0.65 (高) で発火（中程度の偏りも拾う）
# キー: (軸名, "high" or "low")
_DO_NOT_TEMPLATES: dict[tuple[str, str], str] = {
  ("extroverted_introverted", "high"): (
    "一人で長時間の内省を強制せず、対話や協働の機会を確保してください"
  ),
  ("extroverted_introverted", "low"): (
    "大人数での即興ディスカッションや頻繁な会議を最小限にしてください"
  ),
  ("sensing_intuition", "high"): (
    "抽象的な概念だけでなく、具体例やデータを交えて説明してください"
  ),
  ("sensing_intuition", "low"): (
    "過度に詳細な手順書や細かい制約で縛らず、全体像を共有してください"
  ),
  ("thinking_feeling", "high"): (
    "感情論や曖昧な共感だけで説得せず、論理的根拠を明示してください"
  ),
  ("thinking_feeling", "low"): (
    "数値と効率だけで判断を迫らず、チームの感情や関係性にも配慮してください"
  ),
  ("judging_perceiving", "high"): (
    "直前の計画変更や曖昧な指示を避け、事前に明確な方針を共有してください"
  ),
  ("judging_perceiving", "low"): (
    "厳密すぎるスケジュールで縛らず、柔軟に対応できる余白を残してください"
  ),
}

# do_not_listの汎用テンプレート（偏りが全くない場合のフォールバック）
_GENERIC_DO_NOT = "極端な一方向への強制を避け、バランスの取れた対応をしてください"

# do_not_list の発火閾値（<0.35 or >0.65 で発火）
_DO_NOT_THRESHOLD_LOW = 0.35
_DO_NOT_THRESHOLD_HIGH = 0.65

# semantic_contextsの固定ドメインキー
_SEMANTIC_DOMAIN_KEYS = [
  "problem_solving",
  "communication_style",
  "work_rhythm",
  "analog_habits",
  "lifestyle_preferences",
]

# カテゴリベースの汎用タグ
_CATEGORY_TAGS: dict[str, list[str]] = {
  "business_os": [
    "project-management", "decision-making", "strategy",
    "leadership", "problem-solving",
  ],
  "communication": [
    "team-collaboration", "presentation", "facilitation",
    "active-listening", "conflict-resolution",
  ],
  "lifestyle": [
    "self-improvement", "work-life-balance", "creative-thinking",
    "continuous-learning", "time-management",
  ],
}

# lexical_tag抽出用のキーワードマッピング（choice labelから抽出する技術名・手法）
_KEYWORD_MAP: dict[str, list[str]] = {
  "ブレインストーミング": ["brainstorming"],
  "データ": ["data-driven"],
  "プロトタイプ": ["prototyping", "rapid-iteration"],
  "ガントチャート": ["gantt-chart", "project-planning"],
  "マイルストーン": ["milestone-based"],
  "アジェンダ": ["structured-meeting"],
  "ドキュメント": ["documentation"],
  "チャート": ["data-visualization"],
  "ガイドブック": ["research-oriented"],
  "勉強会": ["community-learning"],
  "コミュニティ": ["community-driven"],
  "レビュー": ["peer-review"],
  "クリティカルパス": ["critical-path", "risk-management"],
  "ワークフロー": ["workflow-optimization"],
  "スキルアップ": ["skill-development"],
}

# lexical_tagのバリデーション用正規表現
_TAG_PATTERN = re.compile(r"^[a-z0-9\-./]+$")


class ProfileGenerator:
  """正規化スコアから3層構造プロファイルJSONを生成する純粋ロジッククラス

  profile_id はスレッドセーフなクラスレベルカウンターで連番管理する。
  I/O は行わず、全てのデータは引数経由で受け取る。
  """

  _counter: int = 0
  _lock: threading.Lock = threading.Lock()

  def __init__(self) -> None:
    pass

  def generate(
    self,
    normalized_scores: NormalizedScores,
    answers: list[Answer],
    questions: list[Question],
    scorer: DecisionScorer | None = None,
    aggregator: RuleAggregator | None = None,
  ) -> ProfileOutput:
    """正規化スコアと回答データから完全なプロファイルを生成する

    scorer / aggregator が提供された場合、Decision Engine セクションも生成する。
    提供されない場合は従来通りの base_os ベースプロファイルのみ生成（後方互換）。
    """
    from app.models.profile import Persona, CommunicationTone

    profile_id = self._next_profile_id()
    base_os = self._build_base_os(normalized_scores)
    lexical_tags = self._build_lexical_tags(answers, questions)
    semantic_contexts = self._build_semantic_contexts(
      normalized_scores, lexical_tags
    )
    persona = self._build_persona(answers, questions)
    tone = self._build_communication_tone(answers, questions)

    # Decision Engine sections (scorer が提供された場合のみ生成)
    decision_model = None
    failure_patterns = None
    context_adaptation = None
    reasoning_flow = None
    decision_rules = None
    rule_hierarchy = None
    answer_metadata_summary = None

    if scorer:
      decision_model = self._build_decision_model(answers, scorer)
      failure_patterns = self._build_failure_patterns(answers, scorer)
      context_adaptation = self._build_context_adaptation(answers, scorer)
      reasoning_flow = self._build_reasoning_flow(answers)
      decision_rules = self._build_decision_rules(answers, questions, scorer)
      answer_metadata_summary = self._build_answer_metadata_summary(answers)

    if aggregator and decision_rules:
      rule_hierarchy = self._build_rule_hierarchy(decision_rules, aggregator)

    return ProfileOutput(
      profile_id=profile_id,
      persona=persona,
      communication_tone=tone,
      base_os=base_os,
      lexical_tags=lexical_tags,
      semantic_contexts=semantic_contexts,
      context_layers=ContextLayers(),
      decision_model=decision_model,
      failure_patterns=failure_patterns,
      context_adaptation=context_adaptation,
      reasoning_flow=reasoning_flow,
      decision_rules=decision_rules,
      rule_hierarchy=rule_hierarchy,
      answer_metadata_summary=answer_metadata_summary,
    )

  @classmethod
  def _next_profile_id(cls) -> str:
    """スレッドセーフな連番プロファイルID生成

    フォーマット: "prof_" + 6桁ゼロパディング
    """
    with cls._lock:
      cls._counter += 1
      return f"prof_{cls._counter:06d}"

  @classmethod
  def reset_counter(cls) -> None:
    """テスト用: カウンターをリセットする"""
    with cls._lock:
      cls._counter = 0

  def _build_base_os(self, scores: NormalizedScores) -> BaseOS:
    """Base OSレイヤーを構築する"""
    axes = scores
    decision_style = self._derive_decision_style(scores)
    do_not_list = self._derive_do_not_list(scores)

    return BaseOS(
      axes=axes,
      decision_style=decision_style,
      do_not_list=do_not_list,
    )

  def _derive_decision_style(self, scores: NormalizedScores) -> str:
    """4軸スコアからdecision_styleラベルを導出する

    各軸について:
    - >0.50 → 第1極（例: extroverted）
    - <0.50 → 第2極（例: introverted）
    - ==0.50 → balanced

    結果から16タイプ日本語名を付与して返す。
    フォーマット: "日本語名（コード）"
    """
    parts: list[str] = []
    axis_values = {
      "extroverted_introverted": scores.extroverted_introverted,
      "sensing_intuition": scores.sensing_intuition,
      "thinking_feeling": scores.thinking_feeling,
      "judging_perceiving": scores.judging_perceiving,
    }

    for axis_name, value in axis_values.items():
      pole1, pole2 = _AXIS_POLES[axis_name]
      if value > 0.50:
        parts.append(pole1)
      elif value < 0.50:
        parts.append(pole2)
      else:
        parts.append("balanced")

    style_key = "_".join(parts)

    # 16タイプ名の解決（日本語名のみ、MBTIコード不使用）
    jp_name = _TYPE_NAMES.get(style_key, _BALANCED_TYPE_NAME)

    return jp_name

  def _derive_do_not_list(self, scores: NormalizedScores) -> list[str]:
    """偏り（<0.35 or >0.65）のある軸からdo_not_list項目を生成する

    閾値を緩めに設定し、中程度の偏りでもアドバイスを生成する。
    偏りがない場合は汎用メッセージ1件を返す。
    最大4項目。
    """
    items: list[str] = []
    axis_values = {
      "extroverted_introverted": scores.extroverted_introverted,
      "sensing_intuition": scores.sensing_intuition,
      "thinking_feeling": scores.thinking_feeling,
      "judging_perceiving": scores.judging_perceiving,
    }

    for axis_name, value in axis_values.items():
      if len(items) >= 4:
        break
      if value > _DO_NOT_THRESHOLD_HIGH:
        template = _DO_NOT_TEMPLATES.get((axis_name, "high"))
        if template:
          items.append(template)
      elif value < _DO_NOT_THRESHOLD_LOW:
        template = _DO_NOT_TEMPLATES.get((axis_name, "low"))
        if template:
          items.append(template)

    # 偏りがない場合は汎用メッセージ
    if not items:
      items.append(_GENERIC_DO_NOT)

    return items

  def _build_lexical_tags(
    self, answers: list[Answer], questions: list[Question]
  ) -> list[str]:
    """回答と質問データからlexical_tagsを抽出する

    - single_choice: 選択されたchoice labelからキーワードを抽出
    - multi_select: selected_options に対応するタグを直接追加
    - カテゴリ由来のタグを追加
    - 小文字化、[a-z0-9\\-./]+パターンに合致するもののみ
    - 最小5件、最大50件、重複なし
    """
    tags: list[str] = []
    seen: set[str] = set()

    # 質問IDベースのルックアップを構築
    question_map: dict[str, Question] = {q.id: q for q in questions}

    # 優先度1: multi_select回答のタグを最優先で追加
    for answer in answers:
      question = question_map.get(answer.question_id)
      if not question:
        continue
      if question.question_type == "multi_select" and answer.selected_options:
        option_map = {opt.id: opt for opt in question.options}
        for opt_id in answer.selected_options:
          option = option_map.get(opt_id)
          if option:
            for tag in option.tags:
              self._add_tag(tag, tags, seen)
        # free_texts もタグとして追加
        if answer.free_texts:
          for ft in answer.free_texts:
            normalized = ft.lower().strip()
            if normalized:
              self._add_tag(normalized, tags, seen)

    # 優先度2: single_choice回答からキーワード抽出
    for answer in answers:
      question = question_map.get(answer.question_id)
      if not question:
        continue
      if question.question_type == "multi_select":
        continue  # 既に処理済み
      if answer.choice_id:
        for choice in question.choices:
          if choice.id == answer.choice_id:
            self._extract_tags_from_label(choice.label, tags, seen)
            break

    # 優先度3: カテゴリ由来のタグ（最低限のパディング）
    for answer in answers:
      question = question_map.get(answer.question_id)
      if not question:
        continue
      category_id = question.category_id
      if category_id in _CATEGORY_TAGS:
        for tag in _CATEGORY_TAGS[category_id]:
          self._add_tag(tag, tags, seen)

    # 最小5件を保証するためのパディング
    padding_tags = [
      "analytical", "collaborative", "adaptive",
      "systematic", "creative", "pragmatic",
      "detail-oriented", "big-picture", "iterative",
      "structured",
    ]
    for tag in padding_tags:
      if len(tags) >= 5:
        break
      self._add_tag(tag, tags, seen)

    # 最大500件に制限
    return tags[:500]

  def _extract_tags_from_label(
    self, label: str, tags: list[str], seen: set[str]
  ) -> None:
    """choice labelからキーワードマッピングに基づいてタグを抽出する"""
    for keyword, mapped_tags in _KEYWORD_MAP.items():
      if keyword in label:
        for tag in mapped_tags:
          self._add_tag(tag, tags, seen)

  def _add_tag(self, tag: str, tags: list[str], seen: set[str]) -> None:
    """バリデーション済みタグをリストに追加する（重複チェック付き）"""
    normalized = tag.lower().strip()
    if not normalized:
      return
    if not _TAG_PATTERN.match(normalized):
      return
    if normalized in seen:
      return
    if len(normalized) > 64:
      return
    seen.add(normalized)
    tags.append(normalized)

  def _build_semantic_contexts(
    self, scores: NormalizedScores, lexical_tags: list[str]
  ) -> dict[str, str]:
    """semantic_contextsを生成する

    固定ドメインキーごとに50〜500語の自然言語段落を生成。
    lexical_tagsに含まれる固有名詞はテキストに含めない（データ分離保証）。
    """
    # lexical_tagsに含まれるトークンのセット（分離チェック用）
    tag_tokens = set(lexical_tags)

    contexts: dict[str, str] = {}
    for domain_key in _SEMANTIC_DOMAIN_KEYS:
      paragraph = self._generate_paragraph(domain_key, scores, tag_tokens)
      contexts[domain_key] = paragraph

    return contexts

  def _generate_paragraph(
    self,
    domain_key: str,
    scores: NormalizedScores,
    excluded_tokens: set[str],
  ) -> str:
    """ドメインキーとスコアに基づいて段落テキストを生成する

    0.25単位の4段階テンプレートで細かく分岐:
    - 0.00〜0.25: 第2極が非常に強い
    - 0.25〜0.50: 第2極がやや強い
    - 0.50〜0.75: 第1極がやや強い
    - 0.75〜1.00: 第1極が非常に強い
    """
    generators = {
      "problem_solving": self._gen_problem_solving,
      "communication_style": self._gen_communication_style,
      "work_rhythm": self._gen_work_rhythm,
      "analog_habits": self._gen_analog_habits,
      "lifestyle_preferences": self._gen_lifestyle_preferences,
    }

    generator = generators[domain_key]
    paragraph = generator(scores)

    # データ分離保証: lexical_tagsのトークンを除去
    paragraph = self._remove_excluded_tokens(paragraph, excluded_tokens)

    return paragraph

  @staticmethod
  def _score_level(value: float) -> int:
    """スコアを4段階レベルに変換する

    0: 0.00〜0.25（第2極 非常に強い）
    1: 0.25〜0.50（第2極 やや強い）
    2: 0.50〜0.75（第1極 やや強い）
    3: 0.75〜1.00（第1極 非常に強い）
    """
    if value < 0.25:
      return 0
    elif value < 0.50:
      return 1
    elif value < 0.75:
      return 2
    else:
      return 3

  def _gen_problem_solving(self, scores: NormalizedScores) -> str:
    """問題解決スタイルの段落を生成（4段階分岐）"""
    ei = self._score_level(scores.extroverted_introverted)
    sn = self._score_level(scores.sensing_intuition)
    tf = self._score_level(scores.thinking_feeling)

    parts: list[str] = ["問題に直面した際、"]

    # E/I 軸（問題解決のアプローチ）
    ei_templates = [
      "完全に一人の環境で深い内省と分析を通じて本質を追究し、十分に練り上げた解決策のみを提示します。",
      "まず一人で考えを整理してから、必要に応じて少人数に相談するスタイルです。",
      "チームとの対話を通じて多角的な視点を集めつつ、自分の考えも積極的に共有します。",
      "即座に関係者全員を巻き込み、ブレインストーミングやディスカッションを通じて集合知で突破口を見つけます。",
    ]
    parts.append(ei_templates[ei])

    # S/N 軸（情報処理スタイル）
    sn_templates = [
      "既存の枠組みに囚われず、まだ誰も試していない革新的な発想でパラダイムシフトを起こすことを好みます。未来の可能性に強く引かれ、直感を最大の武器として活用します。",
      "全体像やパターンを捉えることを重視し、創造的なアプローチで従来と異なる角度から解決策を探ります。",
      "具体的なデータと事実に基づいて現状を把握し、実績のある手法を段階的に適用していきます。",
      "徹底的にデータを収集・分析し、あらゆる具体的事実を積み上げて確実性の高い解決策を導き出します。過去の実績と定量的エビデンスを最も信頼します。",
    ]
    parts.append(sn_templates[sn])

    # T/F 軸（判断基準）
    tf_templates = [
      "人間関係の調和とチーム全体の感情的な安全性を最優先し、全員が心から納得できる道を粘り強く探ります。",
      "判断時に関係者への影響を考慮し、共感的な理解に基づいた意思決定を心がけます。",
      "客観的な基準と論理的整合性を重視し、根拠に基づいた合理的な結論を導き出します。",
      "徹底的に論理と数値で最適解を追求し、感情に左右されない鋭い分析力で判断を下します。効率と正確性が絶対的な判断軸です。",
    ]
    parts.append(tf_templates[tf])

    return "".join(parts)

  def _gen_communication_style(self, scores: NormalizedScores) -> str:
    """コミュニケーションスタイルの段落を生成（4段階分岐）"""
    ei = self._score_level(scores.extroverted_introverted)
    tf = self._score_level(scores.thinking_feeling)
    jp = self._score_level(scores.judging_perceiving)

    parts: list[str] = ["コミュニケーションにおいては、"]

    ei_templates = [
      "書面やドキュメントでの精緻な表現を最も得意とし、必要最小限の対面対話で深い意思疎通を実現します。",
      "少人数での落ち着いた対話を好み、よく考えてから発言する傾向があります。",
      "オープンな議論を好み、チームとの活発な意見交換の場を自然に作り出します。",
      "あらゆる場で会話の中心となり、大人数のディスカッションをエネルギッシュにリードします。即興的なやり取りから最高のアイデアが生まれると信じています。",
    ]
    parts.append(ei_templates[ei])

    tf_templates = [
      "相手の感情を最優先に配慮し、温かみと共感に満ちた言葉選びを大切にします。ポジティブなフィードバックで相手の力を引き出します。",
      "相手の状況に寄り添った柔らかい表現を心がけ、関係性の維持を重視します。",
      "明確で論理的な表現を好み、事実に基づいた簡潔なコミュニケーションを志向します。",
      "徹底的に無駄を省いた論理的表現で、事実と結論のみを端的に伝えます。曖昧さを排除し、正確性を最重要視します。",
    ]
    parts.append(tf_templates[tf])

    jp_templates = [
      "対話の流れに身を委ね、即興的に話題を展開させることで予想外の発見を楽しみます。",
      "柔軟に話題を広げつつ、必要に応じて方向性を調整していきます。",
      "事前にアジェンダを整理し、構造的な進行で生産的な結論を導きます。",
      "分単位で計画された進行表に沿い、全ての論点を期限内に明確な結論へ導きます。脱線を許さず、アクションアイテムを確実に定めます。",
    ]
    parts.append(jp_templates[jp])

    return "".join(parts)

  def _gen_work_rhythm(self, scores: NormalizedScores) -> str:
    """業務リズムの段落を生成（4段階分岐）"""
    sn = self._score_level(scores.sensing_intuition)
    jp = self._score_level(scores.judging_perceiving)
    ei = self._score_level(scores.extroverted_introverted)

    parts: list[str] = ["業務のリズムとしては、"]

    jp_templates = [
      "固定スケジュールを持たず、インスピレーションが湧いた瞬間に全力で集中するスタイルです。締め切りは創造性の敵だと感じます。",
      "大枠の方向性だけ決めて柔軟に進め、状況変化に素早く適応しながら最適なタイミングで判断します。",
      "計画的に進行し、マイルストーンに沿って着実に成果を積み上げていきます。",
      "分単位の詳細スケジュールを組み、全てを事前に計画してから実行に移ります。予定外の事態は許容しない徹底した管理スタイルです。",
    ]
    parts.append(jp_templates[jp])

    sn_templates = [
      "複数の可能性を並行して探索し、全体像の中でタスクの意味を位置づけることで創造的な余白を確保します。",
      "全体の関連性を見ながら優先度を判断し、長期ビジョンに基づいて日々の作業を位置づけます。",
      "目の前のタスクに集中し、具体的で測定可能な目標を設定して確実に完了させていきます。",
      "一つのタスクを完璧に仕上げてから次へ進む超堅実派です。全ての作業を定量的に追跡・管理します。",
    ]
    parts.append(sn_templates[sn])

    ei_templates = [
      "完全な静寂の中で深い集中状態に入り、単独作業で最高の成果を出します。",
      "集中時間を確保しつつ、必要な時だけ短時間で的確にコミュニケーションを取ります。",
      "チームとの定期的なやり取りの中でモチベーションを維持し、協働で生産性を高めます。",
      "常にチームメンバーとつながり、ペアワークやモブ形式で互いに刺激し合いながら進めます。",
    ]
    parts.append(ei_templates[ei])

    return "".join(parts)

  def _gen_analog_habits(self, scores: NormalizedScores) -> str:
    """アナログ習慣の段落を生成（4段階分岐）"""
    sn = self._score_level(scores.sensing_intuition)
    tf = self._score_level(scores.thinking_feeling)
    jp = self._score_level(scores.judging_perceiving)

    parts: list[str] = ["デジタル以外の習慣として、"]

    sn_templates = [
      "制約のないマインドマップや自由連想スケッチで思考を視覚化し、まだ存在しないコンセプトに形を与えることを楽しみます。",
      "抽象的なアイデアを紙に書き出し、視覚化することで思考の広がりを大切にしています。",
      "手書きノートで具体的な事実やデータを整理し、実際に手を動かすことで記憶の定着を図ります。",
      "精密なバレットジャーナルや詳細な手書きログで、あらゆる事実を正確に記録・追跡します。",
    ]
    parts.append(sn_templates[sn])

    tf_templates = [
      "小説やエッセイなど人間の内面を描いた作品に没頭し、多様な感情の機微に触れることで感性を磨いています。",
      "人間関係や共感力に関する本を好み、芸術作品からインスピレーションを得ています。",
      "専門書や技術書で知識を体系的に蓄積し、実務に直結する情報を効率的に吸収します。",
      "論文や学術書を読み込み、徹底的にロジカルな知識体系の構築に時間を費やします。",
    ]
    parts.append(tf_templates[tf])

    jp_templates = [
      "その日の気分で過ごし方を変え、予期せぬ発見や出会いを日々楽しんでいます。",
      "固定ルーティンよりも自発的な行動を好み、日常に新鮮さを取り入れています。",
      "朝の散歩やストレッチなど決まった日課で心身のコンディションを整えています。",
      "分刻みのルーティンを厳守し、規則正しい生活リズムが高いパフォーマンスの基盤です。",
    ]
    parts.append(jp_templates[jp])

    return "".join(parts)

  def _gen_lifestyle_preferences(self, scores: NormalizedScores) -> str:
    """ライフスタイル嗜好の段落を生成（4段階分岐）"""
    ei = self._score_level(scores.extroverted_introverted)
    sn = self._score_level(scores.sensing_intuition)
    tf = self._score_level(scores.thinking_feeling)

    parts: list[str] = ["ライフスタイルにおいては、"]

    ei_templates = [
      "一人の時間を何より大切にし、内省と創作の静かな空間で自分自身と向き合うことでエネルギーを回復します。",
      "少数の深い人間関係を重視し、質の高い一対一のつながりに価値を見出しています。",
      "人との交流を通じて視野を広げ、コミュニティや集まりへの参加を楽しみます。",
      "あらゆる社交の場に顔を出し、膨大な人脈ネットワークの中心で常に新しい刺激を求めています。",
    ]
    parts.append(ei_templates[ei])

    sn_templates = [
      "未知の領域への知的好奇心が旺盛で、哲学・芸術・科学を横断する抽象的な探求を楽しみます。",
      "想像力を刺激する活動を好み、新しいアイデアや概念との出会いを大切にしています。",
      "五感で楽しめる具体的な体験を大切にし、手を動かしてものを作ることに喜びを感じます。",
      "徹底的に現実世界での実践と体験を重視し、目に見える成果を着実に積み上げることに充実感を覚えます。",
    ]
    parts.append(sn_templates[sn])

    tf_templates = [
      "人との温かいつながりの中で幸福を感じ、心の赴くままに自由に過ごす時間を大切にしています。",
      "バランスの取れた生活の中で自分のペースを大切にし、新しい挑戦も受け入れます。",
      "効率的な時間活用を意識し、目標達成に向けた計画的な自己投資を重視します。",
      "全ての活動を最適化し、成果測定可能な自己研鑽に時間を集中投下します。無駄な時間は一秒も許容しません。",
    ]
    parts.append(tf_templates[tf])

    return "".join(parts)

  def _build_persona(
    self, answers: list[Answer], questions: list[Question]
  ) -> "Persona":
    """persona カテゴリの回答から Persona を構築する"""
    from app.models.profile import Persona

    question_map = {q.id: q for q in questions}
    persona_data: dict[str, str] = {}

    # persona カテゴリの質問IDマッピング
    field_map = {
      "per_001": "age_range",
      "per_002": "role",
      "per_003": "industry",
      "per_004": "experience_years",
      "per_005": "nickname",
    }

    for answer in answers:
      if answer.question_id in field_map:
        field_name = field_map[answer.question_id]
        question = question_map.get(answer.question_id)
        if answer.text:
          # Other回答: テキストをそのまま使用
          persona_data[field_name] = answer.text
        elif answer.choice_id and question:
          # 選択肢: ラベルを値として使用
          for choice in question.choices:
            if choice.id == answer.choice_id:
              persona_data[field_name] = choice.label
              break

    return Persona(**persona_data)

  def _build_communication_tone(
    self, answers: list[Answer], questions: list[Question]
  ) -> "CommunicationTone":
    """communication_tone カテゴリの回答から CommunicationTone を構築する"""
    from app.models.profile import CommunicationTone

    question_map = {q.id: q for q in questions}
    tone_data: dict[str, str] = {}

    field_map = {
      "ton_001": "pronoun",
      "ton_002": "formality",
      "ton_003": "text_style",
      "ton_004": "emotion_level",
      "ton_005": "humor",
      "ton_006": "sentence_ending",
      "ton_007": "filler_words",
    }

    for answer in answers:
      if answer.question_id in field_map:
        field_name = field_map[answer.question_id]
        question = question_map.get(answer.question_id)
        if answer.text:
          tone_data[field_name] = answer.text
        elif answer.choice_id and question:
          for choice in question.choices:
            if choice.id == answer.choice_id:
              tone_data[field_name] = choice.label
              break

    return CommunicationTone(**tone_data)

  def _build_values(
    self, answers: list[Answer], questions: list[Question]
  ) -> "Values":
    """values カテゴリの回答から Values を構築する"""
    from app.models.profile import Values

    question_map = {q.id: q for q in questions}
    values_data: dict[str, str] = {}

    field_map = {
      "val_001": "work_belief",
      "val_002": "team_stance",
      "val_003": "conflict_approach",
      "val_004": "failure_attitude",
      "val_005": "change_attitude",
    }

    for answer in answers:
      if answer.question_id in field_map:
        field_name = field_map[answer.question_id]
        question = question_map.get(answer.question_id)
        if answer.text:
          values_data[field_name] = answer.text
        elif answer.choice_id and question:
          for choice in question.choices:
            if choice.id == answer.choice_id:
              values_data[field_name] = choice.label
              break

    return Values(**values_data)

  def _remove_excluded_tokens(
    self, text: str, excluded_tokens: set[str]
  ) -> str:
    """テキストからexcluded_tokensに含まれるトークンを除去する

    データ分離保証: lexical_tagsのキーワードがsemantic_contextsに
    そのまま出現しないようにする。
    """
    for token in excluded_tokens:
      # 英数字のトークンのみ置換対象（日本語テンプレートには基本的に含まれない）
      if _TAG_PATTERN.match(token):
        text = text.replace(token, "")
    return text

  # ─── Decision Engine Builder Methods ───────────────────────────────

  def _build_decision_model(
    self, answers: list[Answer], scorer: DecisionScorer
  ) -> DecisionModelOutput | None:
    """decision_model + tradeoff_tendencies を構築する

    dm_001〜dm_010 の回答から Priority Weight を累積・正規化し、
    ts_001〜ts_008 の回答から Tradeoff Tendency スコアを収集する。
    いずれかのカテゴリが未完了の場合は None を返す。
    """
    from app.decision_engine.models import DecisionModelOutput

    # dm_ プレフィクスの回答を収集（choice_id ありのみ）
    dm_answers = [
      a for a in answers
      if a.question_id.startswith("dm_") and a.choice_id
    ]
    if len(dm_answers) < 10:
      return None  # 部分完了時は生成しない

    # Priority weight 累積
    accumulated: dict[str, int] = {}
    for answer in dm_answers:
      try:
        weights = scorer.score_decision_model(answer.question_id, answer.choice_id)
        for label, weight in weights.items():
          accumulated[label] = accumulated.get(label, 0) + weight
      except Exception:
        continue

    priority_weights = scorer.normalize_weights(accumulated)
    # 重み降順で優先順位リストを構築
    priorities = sorted(
      priority_weights.keys(),
      key=lambda k: priority_weights[k],
      reverse=True,
    )

    # Tradeoff tendencies（ts_ プレフィクス）
    ts_answers = [
      a for a in answers
      if a.question_id.startswith("ts_") and a.choice_id
    ]
    if len(ts_answers) < 8:
      return None  # トレードオフも全問必要

    tradeoff_tendencies: dict[str, float] = {}
    for answer in ts_answers:
      try:
        pair, score = scorer.score_tradeoff(answer.question_id, answer.choice_id)
        tradeoff_tendencies[pair] = score
      except Exception:
        continue

    # Escalation rules: dm_007 由来（簡略化: マッピングから取得する設計だが現時点は空）
    escalation_rules: list[str] = []

    # Auto approve scope: dm_008 由来（同上）
    auto_approve_scope: list[str] = []

    return DecisionModelOutput(
      priorities=priorities[:10],
      priority_weights=priority_weights,
      escalation_rules=escalation_rules,
      auto_approve_scope=auto_approve_scope,
      tradeoff_tendencies=tradeoff_tendencies,
    )

  def _build_failure_patterns(
    self, answers: list[Answer], scorer: DecisionScorer
  ) -> FailurePatternsOutput | None:
    """failure_patterns を構築する

    fp_001〜fp_007 の回答を4サブカテゴリに分類する。
    7問未満の場合は None を返す。
    """
    from app.decision_engine.models import FailurePatternsOutput

    fp_answers = [
      a for a in answers
      if a.question_id.startswith("fp_") and a.choice_id
    ]
    if len(fp_answers) < 7:
      return None

    result: dict[str, list[str]] = {
      "degradation_triggers": [],
      "procrastination_patterns": [],
      "overconfidence_conditions": [],
      "recurring_mistakes": [],
    }

    for answer in fp_answers:
      try:
        subcategory, label = scorer.score_failure_pattern(
          answer.question_id, answer.choice_id
        )
        if subcategory in result:
          result[subcategory].append(label)
      except Exception:
        continue

    return FailurePatternsOutput(**result)

  def _build_context_adaptation(
    self, answers: list[Answer], scorer: DecisionScorer
  ) -> ContextAdaptationOutput | None:
    """context_adaptation を構築する

    ca_001〜ca_005 の回答からモード設定と切替トリガーを導出する。
    5問未満の場合は None を返す。
    """
    from app.decision_engine.models import ContextAdaptationOutput

    ca_answers = [
      a for a in answers
      if a.question_id.startswith("ca_") and a.choice_id
    ]
    if len(ca_answers) < 5:
      return None

    modes: dict[str, dict[str, str]] = {}
    switch_triggers: dict[str, list[str]] = {
      "audience": [],
      "urgency": [],
      "mental_state": [],
    }

    for answer in ca_answers:
      try:
        mode_result = scorer.score_context_adaptation(
          answer.question_id, answer.choice_id
        )
        for mode_name, config in mode_result.items():
          modes[mode_name] = config
      except Exception:
        continue

    return ContextAdaptationOutput(
      modes=modes,
      switch_triggers=switch_triggers,
    )

  def _build_reasoning_flow(
    self, answers: list[Answer]
  ) -> ReasoningFlowOutput | None:
    """reasoning_flow を構築する

    rf_001〜rf_005 の回答からデフォルト思考ステップ・検証方法・学習スタイルを導出する。
    5問未満の場合は None を返す。
    """
    from app.decision_engine.models import ReasoningFlowOutput

    rf_answers = [
      a for a in answers
      if a.question_id.startswith("rf_")
    ]
    if len(rf_answers) < 5:
      return None

    # ordering 回答（rf_001, rf_002）から default_steps を抽出
    default_steps: list[str] = []
    for answer in rf_answers:
      if answer.question_id in ("rf_001", "rf_002"):
        if answer.choice_id:
          try:
            steps = json.loads(answer.choice_id)
            if isinstance(steps, list) and len(steps) >= 4:
              default_steps = steps
              break
          except (json.JSONDecodeError, TypeError):
            pass

    # フォールバック: 最低4ステップ必要
    if not default_steps or len(default_steps) < 4:
      default_steps = ["情報収集", "問題定義", "解決案生成", "評価・実行"]

    # verification_method (rf_003 由来)
    verification_method = "レビューと検証"
    for answer in rf_answers:
      if answer.question_id == "rf_003" and answer.text:
        verification_method = answer.text[:100]
        break

    # learning_style (rf_004 由来)
    learning_style = "実践的学習"
    for answer in rf_answers:
      if answer.question_id == "rf_004" and answer.text:
        learning_style = answer.text[:100]
        break

    return ReasoningFlowOutput(
      default_steps=default_steps[:6],
      verification_method=verification_method,
      learning_style=learning_style,
    )

  def _build_decision_rules(
    self,
    answers: list[Answer],
    questions: list[Question],
    scorer: DecisionScorer,
  ) -> list[dict] | None:
    """全質問のポリシールールを収集する

    各回答から Mapping Dictionary の policy_text を取得し、
    ルールリストとして返す。ルールが1件もない場合は None。
    """
    question_map = {q.id: q for q in questions}
    rules: list[dict] = []

    for answer in answers:
      if not answer.choice_id:
        continue
      question = question_map.get(answer.question_id)
      if not question:
        continue

      # Mapping Dictionary からポリシー情報を取得
      try:
        entry = scorer._get_entry(answer.question_id, answer.choice_id)
        if entry.policy_text:
          rules.append({
            "question_id": answer.question_id,
            "rule": entry.policy_text,
            "confidence": 0.6,  # デフォルト確信度
            "is_core": False,
            "permanence": "permanent",
            "normalization_tags": [],
          })
      except Exception:
        continue

    return rules if rules else None

  def _build_rule_hierarchy(
    self, decision_rules: list[dict], aggregator: RuleAggregator
  ) -> RuleHierarchyOutput | None:
    """RuleAggregator 経由で全ルールを4層ヒエラルキーに集約する"""
    from app.decision_engine.models import RuleHierarchyOutput

    if not decision_rules:
      return None

    hierarchy = aggregator.aggregate(decision_rules)
    return RuleHierarchyOutput(
      core_invariants=hierarchy.core_invariants,
      context_rules=hierarchy.context_rules,
      exceptions=hierarchy.exceptions,
      preferences=hierarchy.preferences,
    )

  def _build_answer_metadata_summary(
    self, answers: list[Answer]
  ) -> AnswerMetadataSummary | None:
    """回答メタデータの統計サマリを構築する

    回答数・コアルール数・コンテキスト依存数・平均確信度・高曖昧度数を集計する。
    回答が0件の場合は None を返す。
    """
    from app.decision_engine.models import AnswerMetadataSummary

    if not answers:
      return None

    total = len(answers)
    # 現時点ではメタデータは Answer モデルに含まれないためデフォルト値で集計
    # 将来的に AnswerPipeline と統合時に実データを参照する
    return AnswerMetadataSummary(
      total_answers=total,
      core_rule_count=0,
      contextual_count=0,
      average_confidence=0.6,
      high_ambiguity_count=0,
    )
