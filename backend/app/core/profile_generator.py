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
    - ==0.50 → _balanced

    結果をアンダースコアで結合する。
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
        # exactly 0.50 → balanced
        parts.append("balanced")

    return "_".join(parts)

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

    - 選択されたchoice labelからキーワードを抽出
    - カテゴリ由来のタグを追加
    - 小文字化、[a-z0-9\\-./]+パターンに合致するもののみ
    - 最小5件、最大50件、重複なし
    """
    tags: list[str] = []
    seen: set[str] = set()

    # 質問IDベースのルックアップを構築
    question_map: dict[str, Question] = {q.id: q for q in questions}

    # 回答に対応するchoice labelからキーワード抽出
    for answer in answers:
      question = question_map.get(answer.question_id)
      if not question:
        continue

      # choice_idがある場合、そのlabelからキーワード抽出
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

    50〜500語（日本語の場合は文字数ベースではなく単語数ベース）の
    自然言語段落を生成する。excluded_tokensに含まれるトークンは使用しない。
    """
    # 各ドメインに対応する段落生成テンプレートを使用
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

  def _gen_problem_solving(self, scores: NormalizedScores) -> str:
    """問題解決スタイルの段落を生成"""
    ei = scores.extroverted_introverted
    sn = scores.sensing_intuition
    tf = scores.thinking_feeling

    parts: list[str] = []
    parts.append("問題に直面した際、")

    if ei > 0.50:
      parts.append(
        "まず周囲の人々と対話を通じて状況を把握し、"
        "多様な視点を集めることで解決の糸口を見つけようとします。"
      )
    else:
      parts.append(
        "まず一人で深く考え、問題の本質を見極めてから"
        "解決策を練り上げていく傾向があります。"
      )

    if sn > 0.50:
      parts.append(
        "具体的な事実やデータに基づいて現状を正確に把握し、"
        "実証された方法論を適用して段階的に問題を解消していきます。"
        "観察可能な現象から論理的に推論を積み重ね、"
        "確実性の高いアプローチを選択する傾向が強いです。"
      )
    else:
      parts.append(
        "全体像やパターンを直感的に捉え、"
        "従来の枠組みにとらわれない創造的なアプローチで解決を図ります。"
        "可能性の探索を重視し、斬新な角度からの発想を活かして"
        "根本的な解決策を模索する傾向があります。"
      )

    if tf > 0.50:
      parts.append(
        "判断においては客観的な基準と論理的整合性を最重要視し、"
        "感情に左右されない合理的な結論を導き出します。"
        "効率性と正確性を重視した意思決定プロセスを好み、"
        "根拠に基づいた説明を大切にします。"
      )
    else:
      parts.append(
        "判断においては関係者への影響や人間関係の調和を考慮し、"
        "全員が納得できる解決策を見つけることを重視します。"
        "共感的な理解に基づいた意思決定を好み、"
        "チーム全体の士気と信頼関係を大切にします。"
      )

    return "".join(parts)

  def _gen_communication_style(self, scores: NormalizedScores) -> str:
    """コミュニケーションスタイルの段落を生成"""
    ei = scores.extroverted_introverted
    tf = scores.thinking_feeling
    jp = scores.judging_perceiving

    parts: list[str] = []
    parts.append("コミュニケーションにおいては、")

    if ei > 0.50:
      parts.append(
        "積極的に会話を主導し、オープンな議論を通じて"
        "アイデアを発展させることを好みます。"
        "グループでの対話からエネルギーを得て、"
        "活発な意見交換の場を自然に作り出します。"
      )
    else:
      parts.append(
        "深く考えてから発言する傾向があり、"
        "一対一やの少人数での質の高い対話を好みます。"
        "書面でのコミュニケーションに強みを発揮し、"
        "整理された形での情報共有を重視します。"
      )

    if tf > 0.50:
      parts.append(
        "明確で論理的な表現を好み、"
        "要点を簡潔に伝えることを心がけます。"
        "事実に基づいた建設的なフィードバックを重視し、"
        "曖昧な表現を避ける傾向があります。"
      )
    else:
      parts.append(
        "相手の感情や状況に配慮した表現を選び、"
        "温かみのあるコミュニケーションを心がけます。"
        "相手の立場に立った言葉遣いを重視し、"
        "励ましや肯定的なフィードバックを大切にします。"
      )

    if jp > 0.50:
      parts.append(
        "事前に議題を整理し、構造化された会話の進行を好みます。"
        "結論を明確にし、次のアクションを具体的に決めることで"
        "生産的な対話を実現します。"
      )
    else:
      parts.append(
        "柔軟な対話の流れを好み、"
        "予定外のトピックにも臨機応変に対応します。"
        "多様な視点を取り入れることを重視し、"
        "議論の展開に応じて方向性を調整していきます。"
      )

    return "".join(parts)

  def _gen_work_rhythm(self, scores: NormalizedScores) -> str:
    """業務リズムの段落を生成"""
    sn = scores.sensing_intuition
    jp = scores.judging_perceiving
    ei = scores.extroverted_introverted

    parts: list[str] = []
    parts.append("業務のリズムとしては、")

    if jp > 0.50:
      parts.append(
        "計画的に物事を進めることを好み、"
        "明確なスケジュールとマイルストーンに沿って"
        "着実に成果を積み上げていくスタイルです。"
        "期限を守ることへの強い責任感を持ち、"
        "事前準備を十分に行ってから実行に移ります。"
      )
    else:
      parts.append(
        "状況に応じて柔軟にスケジュールを調整し、"
        "変化する優先度に対応しながら進めるスタイルです。"
        "新しい情報や状況変化に素早く適応し、"
        "最適なタイミングで判断を下すことを重視します。"
      )

    if sn > 0.50:
      parts.append(
        "目の前のタスクに集中し、一つずつ確実に完了させてから"
        "次に進む堅実なアプローチを取ります。"
        "具体的で測定可能な目標を設定し、"
        "進捗を可視化しながら進めることを好みます。"
      )
    else:
      parts.append(
        "複数のタスクを並行して進めることが得意で、"
        "全体の関連性を見ながら優先度を判断します。"
        "長期的なビジョンに基づいて日々の作業を位置づけ、"
        "創造的な閃きを活かせる余白を確保します。"
      )

    if ei > 0.50:
      parts.append(
        "チームメンバーとの頻繁なやり取りの中で"
        "モチベーションを維持し、協働作業を通じて"
        "生産性を高めることを好みます。"
      )
    else:
      parts.append(
        "集中できる静かな環境での作業を好み、"
        "深い思考が必要なタスクに長時間没頭することで"
        "最高の成果を生み出します。"
      )

    return "".join(parts)

  def _gen_analog_habits(self, scores: NormalizedScores) -> str:
    """アナログ習慣の段落を生成"""
    sn = scores.sensing_intuition
    tf = scores.thinking_feeling
    jp = scores.judging_perceiving

    parts: list[str] = []
    parts.append("デジタル以外の習慣として、")

    if sn > 0.50:
      parts.append(
        "手書きのノートやメモを活用し、"
        "物理的な記録を通じて思考を整理する習慣があります。"
        "実際に手を動かすことで記憶の定着を図り、"
        "紙の質感や書く行為そのものから集中力を得ています。"
      )
    else:
      parts.append(
        "マインドマップや自由連想的なスケッチを通じて"
        "アイデアを視覚化する習慣があります。"
        "制約のない発想の場として紙やホワイトボードを活用し、"
        "デジタルでは得られない思考の広がりを大切にしています。"
      )

    if tf > 0.50:
      parts.append(
        "読書においては専門書や技術書を好み、"
        "知識の体系的な蓄積を重視します。"
        "論理的な議論や分析的な内容に惹かれ、"
        "実務に直結する情報を効率的に吸収することを目指しています。"
      )
    else:
      parts.append(
        "小説やエッセイなど人間の内面を描いた作品を好み、"
        "多様な視点や感情の機微に触れることを大切にしています。"
        "芸術作品や音楽からインスピレーションを得て、"
        "感性を磨くことが日常の一部となっています。"
      )

    if jp > 0.50:
      parts.append(
        "日課としてのルーティンを大切にし、"
        "朝の散歩やストレッチなど決まった時間に行う活動で"
        "心身のコンディションを整えています。"
        "規則正しい生活リズムが高い生産性の基盤となっています。"
      )
    else:
      parts.append(
        "その日の気分や天候に合わせて過ごし方を変え、"
        "固定されたルーティンよりも自発的な行動を好みます。"
        "予期せぬ発見や出会いを楽しむ姿勢で、"
        "日々の生活に新鮮さを取り入れることを重視しています。"
      )

    return "".join(parts)

  def _gen_lifestyle_preferences(self, scores: NormalizedScores) -> str:
    """ライフスタイル嗜好の段落を生成"""
    ei = scores.extroverted_introverted
    sn = scores.sensing_intuition
    tf = scores.thinking_feeling
    jp = scores.judging_perceiving

    parts: list[str] = []
    parts.append("ライフスタイルにおいては、")

    if ei > 0.50:
      parts.append(
        "社交的な活動や人との交流を通じてエネルギーを充電し、"
        "コミュニティへの参加や集まりへの出席を楽しみます。"
        "多くの人とつながりを持つことで視野を広げ、"
        "新しい機会やアイデアに触れることを求めています。"
      )
    else:
      parts.append(
        "静かで落ち着いた環境での個人的な時間を大切にし、"
        "内省や自分自身との対話を通じてエネルギーを回復します。"
        "少数の深い人間関係を重視し、"
        "質の高い一対一のつながりに価値を見出しています。"
      )

    if sn > 0.50:
      parts.append(
        "現実的で実用的な趣味を好み、"
        "手を動かして形あるものを作り出すことに喜びを感じます。"
        "五感で楽しめる体験を大切にし、"
        "自然の中での活動や料理などの身体性のある趣味を持つ傾向があります。"
      )
    elif sn < 0.50:
      parts.append(
        "想像力を刺激する活動や抽象的な概念の探求を好み、"
        "未知の領域への知的好奇心が旺盛です。"
        "芸術、哲学、科学など多岐にわたる分野に関心を持ち、"
        "異なる分野を横断する発想を楽しみます。"
      )

    if tf > 0.50 and jp > 0.50:
      parts.append(
        "効率的な時間の使い方を追求し、"
        "目標達成に向けた計画的な自己投資を重視します。"
        "休息も含めたスケジュールを意識的に設計し、"
        "持続可能な成長を目指す姿勢で日々を過ごしています。"
      )
    elif tf < 0.50 and jp < 0.50:
      parts.append(
        "心の赴くままに過ごす自由な時間を大切にし、"
        "予定に縛られない余白のある生活を好みます。"
        "人との温かいつながりの中で幸福感を見出し、"
        "日常の小さな喜びを味わうことを大切にしています。"
      )
    else:
      parts.append(
        "仕事とプライベートのメリハリを重視し、"
        "オンとオフの切り替えを意識的に行っています。"
        "自分のペースを大切にしながらも新しい挑戦を受け入れ、"
        "バランスの取れた充実した日々を送ることを目指しています。"
      )

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
