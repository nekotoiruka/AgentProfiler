"""Profile Generator: 正規化スコアから3層構造プロファイルJSONを生成"""

import re
import threading

from app.models.profile import BaseOS, ContextLayers, ProfileOutput
from app.models.question import Question
from app.models.scores import NormalizedScores
from app.models.session import Answer


# 軸名と両極のマッピング
_AXIS_POLES: dict[str, tuple[str, str]] = {
  "extroverted_introverted": ("extroverted", "introverted"),
  "sensing_intuition": ("sensing", "intuitive"),
  "thinking_feeling": ("thinking", "feeling"),
  "judging_perceiving": ("judging", "perceiving"),
}

# 16タイプ日本語名マッピング（厨二病風）
# キー: (E/I極, S/N極, T/F極, J/P極) の組み合わせ
_TYPE_NAMES: dict[str, tuple[str, str]] = {
  "extroverted_sensing_thinking_judging": ("統率の鉄壁", "ESTJ"),
  "extroverted_sensing_thinking_perceiving": ("刹那の切り拓き", "ESTP"),
  "extroverted_sensing_feeling_judging": ("絆の守護者", "ESFJ"),
  "extroverted_sensing_feeling_perceiving": ("煌めきの演者", "ESFP"),
  "extroverted_intuitive_thinking_judging": ("覇道の戦略家", "ENTJ"),
  "extroverted_intuitive_thinking_perceiving": ("混沌の発明家", "ENTP"),
  "extroverted_intuitive_feeling_judging": ("導きの旗手", "ENFJ"),
  "extroverted_intuitive_feeling_perceiving": ("閃光の触媒", "ENFP"),
  "introverted_sensing_thinking_judging": ("鋼鉄の番人", "ISTJ"),
  "introverted_sensing_thinking_perceiving": ("孤高の職人", "ISTP"),
  "introverted_sensing_feeling_judging": ("静謐の献身者", "ISFJ"),
  "introverted_sensing_feeling_perceiving": ("幽玄の芸術家", "ISFP"),
  "introverted_intuitive_thinking_judging": ("深淵の設計者", "INTJ"),
  "introverted_intuitive_thinking_perceiving": ("無限の解析者", "INTP"),
  "introverted_intuitive_feeling_judging": ("慈愛の導師", "INFJ"),
  "introverted_intuitive_feeling_perceiving": ("静寂の夢想家", "INFP"),
}

# balanced を含むパターンのフォールバック名
_BALANCED_TYPE_NAME = ("均衡の探求者", "XXXX")

# do_not_listテンプレート: 各軸の強い偏りに対応するメッセージ
# キー: (軸名, "high" or "low")
_DO_NOT_TEMPLATES: dict[tuple[str, str], str] = {
  ("extroverted_introverted", "high"): (
    "一人で長時間考える時間を強制しないでください（外向優位）"
  ),
  ("extroverted_introverted", "low"): (
    "大人数での即興ディスカッションを強要しないでください（内向優位）"
  ),
  ("sensing_intuition", "high"): (
    "抽象的な概念だけで説明せず、具体例を交えてください（感覚優位）"
  ),
  ("sensing_intuition", "low"): (
    "過度に詳細な手順指示を与えないでください（直観優位）"
  ),
  ("thinking_feeling", "high"): (
    "感情的な説得や共感アピールを主軸にしないでください（論理優位）"
  ),
  ("thinking_feeling", "low"): (
    "冷徹な数値だけで判断を迫らないでください（感情優位）"
  ),
  ("judging_perceiving", "high"): (
    "直前の計画変更や曖昧な指示を出さないでください（計画優位）"
  ),
  ("judging_perceiving", "low"): (
    "厳密すぎるスケジュールで縛らないでください（柔軟優位）"
  ),
}

# do_not_listの汎用テンプレート（強い偏りがない場合のフォールバック）
_GENERIC_DO_NOT = "極端な一方向への強制を避け、バランスの取れた対応をしてください"

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
  ) -> ProfileOutput:
    """正規化スコアと回答データから完全なプロファイルを生成する"""
    profile_id = self._next_profile_id()
    base_os = self._build_base_os(normalized_scores)
    lexical_tags = self._build_lexical_tags(answers, questions)
    semantic_contexts = self._build_semantic_contexts(
      normalized_scores, lexical_tags
    )

    return ProfileOutput(
      profile_id=profile_id,
      base_os=base_os,
      lexical_tags=lexical_tags,
      semantic_contexts=semantic_contexts,
      context_layers=ContextLayers(),
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

    # 16タイプ名の解決
    type_info = _TYPE_NAMES.get(style_key, _BALANCED_TYPE_NAME)
    jp_name, code = type_info

    return f"{jp_name}（{code}）"

  def _derive_do_not_list(self, scores: NormalizedScores) -> list[str]:
    """強い偏り（<0.30 or >0.70）のある軸からdo_not_list項目を生成する

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
      if value > 0.70:
        template = _DO_NOT_TEMPLATES.get((axis_name, "high"))
        if template:
          items.append(template)
      elif value < 0.30:
        template = _DO_NOT_TEMPLATES.get((axis_name, "low"))
        if template:
          items.append(template)

    # 強い偏りがない場合は汎用メッセージ
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

    # 回答を処理
    for answer in answers:
      question = question_map.get(answer.question_id)
      if not question:
        continue

      # multi_select型: selected_optionsのタグを直接追加
      if question.question_type == "multi_select" and answer.selected_options:
        option_map = {opt.id: opt for opt in question.options}
        for opt_id in answer.selected_options:
          option = option_map.get(opt_id)
          if option:
            for tag in option.tags:
              self._add_tag(tag, tags, seen)
        continue

      # single_choice型: choice_idがある場合、そのlabelからキーワード抽出
      if answer.choice_id:
        for choice in question.choices:
          if choice.id == answer.choice_id:
            self._extract_tags_from_label(choice.label, tags, seen)
            break

      # カテゴリ由来のタグ追加
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

    # 最大50件に制限
    return tags[:50]

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
