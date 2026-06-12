# 心理測定ソースドキュメント

本ドキュメントは、Agent Profiler の「4軸思考特性診断」質問設計に使用する心理測定データソースのカタログです。各ソースの構造、ライセンス、本システムへの適用可能性を整理し、実装時の情報選択を支援します。

---

## 1. ソース一覧サマリー

| ソース名 | URL | ライセンス | 項目数 | 軸/因子構造 | 適用可能性 |
|---------|-----|-----------|--------|------------|-----------|
| OEJTS (Open Extended Jungian Type Scales) | https://openpsychometrics.org/tests/OEJTS/ | CC BY-NC-SA 4.0 | 32項目 (各二分法8項目) | 4二分法 (E/I, S/N, T/F, J/P) | **High** — Four_Axis と直接対応し、構造的親和性が最も高い |
| IPIP-NEO-120 | https://ipip.ori.org/30FacetNEO-PI-RItems.htm | パブリックドメイン | 120項目 | 5因子 (OCEAN) × 30ファセット | **Medium** — Extraversion, Openness 等が部分的にマッピング可能だが、直接対応しない因子もある |
| IPIP 一般リポジトリ | https://ipip.ori.org/ | パブリックドメイン | 3,000+ 項目 | 多数のスケール構成体 | **Medium** — 豊富な項目プールから選択的に利用可能だが、Four_Axis との対応は個別精査が必要 |

---

## 2. OEJTS (Open Extended Jungian Type Scales)

### 2.1 概要

OEJTS は、ユング型類型論に基づく4つの二分法を測定するオープンソース心理測定尺度です。Eric Jorgenson により開発され、Open Psychometrics プロジェクトで公開されています。

### 2.2 構造

- **二分法**: 4つ (Extraversion/Introversion, Sensing/iNtuition, Thinking/Feeling, Judging/Perceiving)
- **項目形式**: 各二分法に8項目、合計32項目
- **回答形式**: 双極5段階スケール（対立する2つの記述の間で程度を選択）
- **例**: "The life of the party" ←→ "Prefer being alone" (5段階)

### 2.3 スコアリング方法

- 各項目の回答を1〜5の数値に変換
- 各二分法ごとに8項目の平均値を算出
- 平均値の差分 (mean level difference) により極性を判定
- しきい値を超える場合に当該極性の型として分類

### 2.4 ライセンス

- **Creative Commons BY-NC-SA 4.0**
- 帰属表示が必要
- 非営利目的での使用に限定
- 改変物は同一ライセンスで共有が必要
- **制約**: 商用利用不可のため、項目文言のそのままの使用は避け、構造と測定原理を設計参考とする

### 2.5 Four_Axis マッピング

| OEJTS 因子 | Four_Axis 対象軸 | マッピング型 | 根拠 |
|-----------|-----------------|------------|------|
| Extraversion / Introversion | `extroverted_introverted` | **direct** | 同一構成概念を測定しており、極性の方向も一致する |
| Sensing / iNtuition | `sensing_intuition` | **direct** | 情報収集スタイルの同一二分法であり、概念的に完全対応する |
| Thinking / Feeling | `thinking_feeling` | **direct** | 意思決定基準の同一二分法であり、論理vs価値判断の対立を共有する |
| Judging / Perceiving | `judging_perceiving` | **direct** | 外界への態度（構造化vs柔軟性）の同一二分法である |

### 2.6 項目分類

| 分類 | 該当状況 | 理由 |
|------|---------|------|
| **design reference only** | 全32項目 | CC BY-NC-SA 4.0 の非営利制約により項目文言の直接使用は不適切。ただし4二分法の構造設計、双極スケール形式、スコアリング原理は設計の基礎参照として活用する |

### 2.7 活用ポイント

- 4軸構造の理論的基盤として最も重要なソース
- 双極スケール形式のアイデアを4択ビジネスシナリオに変換する際の設計指針
- スコアリング方法論（平均値差分）を累積加算方式に適応

---

## 3. IPIP-NEO-120

### 3.1 概要

IPIP-NEO-120 は、Big Five パーソナリティモデルの5因子×各6ファセット（計30ファセット）を120項目で測定するパブリックドメインの心理測定尺度です。Costa & McCrae の NEO-PI-R の構造を IPIP 項目で再現したものです。

### 3.2 構造

- **因子**: 5つ (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)
- **ファセット**: 各因子に6ファセット、計30ファセット
- **項目数**: 120項目（各ファセット4項目）
- **回答形式**: 5段階リッカートスケール (Very Inaccurate → Very Accurate)

### 3.3 5因子とファセット一覧

| 因子 | ファセット |
|------|----------|
| Openness to Experience | Imagination, Artistic Interests, Emotionality, Adventurousness, Intellect, Liberalism |
| Conscientiousness | Self-Efficacy, Orderliness, Dutifulness, Achievement-Striving, Self-Discipline, Cautiousness |
| Extraversion | Friendliness, Gregariousness, Assertiveness, Activity Level, Excitement-Seeking, Cheerfulness |
| Agreeableness | Trust, Morality, Altruism, Cooperation, Modesty, Sympathy |
| Neuroticism | Anxiety, Anger, Depression, Self-Consciousness, Immoderation, Vulnerability |

### 3.4 スコアリング方法

- 各項目を1〜5でスコアリング（逆転項目は反転）
- ファセットスコア: 4項目の合計 (4〜20)
- 因子スコア: 6ファセットの合計 (24〜120)
- パーセンタイル変換またはT得点化で解釈

### 3.5 ライセンス

- **パブリックドメイン**
- 商用利用を含むあらゆる目的で自由に使用可能
- 帰属表示は推奨されるが必須ではない
- 改変・再配布に制限なし

### 3.6 Four_Axis マッピング

| IPIP-NEO-120 因子 | Four_Axis 対象軸 | マッピング型 | 根拠 |
|------------------|-----------------|------------|------|
| Extraversion | `extroverted_introverted` | **partial** | 社交性・活動性は共通するが、IPIP-NEO の Extraversion には Excitement-Seeking 等ユング型 E/I に含まれない側面がある |
| Openness to Experience | `sensing_intuition` | **partial** | Imagination, Intellect ファセットは直観(N)と関連するが、Artistic Interests 等は S/N 二分法に直接対応しない |
| Agreeableness | `thinking_feeling` | **partial** | Cooperation, Sympathy は Feeling 極と相関するが、Agreeableness は対人調和であり意思決定基準とは異なる構成概念 |
| Conscientiousness | `judging_perceiving` | **partial** | Orderliness, Self-Discipline は Judging 極と相関するが、Achievement-Striving 等は J/P とは独立した側面 |
| Neuroticism | — | **none** | Four_Axis のいずれの軸にも直接対応しない。情緒安定性は4軸思考特性モデルの範囲外 |

### 3.7 項目分類

| 分類 | 該当項目例 | 理由 |
|------|-----------|------|
| **require adaptation** | Extraversion ファセット項目（Friendliness, Gregariousness, Assertiveness） | E/I 軸に関連する構成概念を測定するが、文言を「プロジェクトミーティングでの行動」等のビジネスシナリオに変換が必要 |
| **require adaptation** | Openness の Imagination, Intellect ファセット項目 | S/N 軸に部分対応する構成概念だが、抽象的表現をビジネス場面（問題解決アプローチ等）に翻訳が必要 |
| **require adaptation** | Conscientiousness の Orderliness, Self-Discipline ファセット項目 | J/P 軸に相関するが、自己評価形式をシナリオ選択形式に変換が必要 |
| **design reference only** | Neuroticism 全項目、Agreeableness の Modesty/Morality 項目 | Four_Axis のいずれの軸にも十分に対応しない、または測定構成概念が異なりすぎる |

### 3.8 活用ポイント

- パブリックドメインのため、項目の構造・文言を自由に改変して利用可能
- 30ファセットの粒度がビジネスシナリオ設計のヒントとなる
- 逆転項目の手法をバランスのとれた質問設計に応用

---

## 4. IPIP 一般リポジトリ

### 4.1 概要

IPIP (International Personality Item Pool) は、Lewis Goldberg らが構築したパブリックドメインのパーソナリティ測定項目プールです。3,000以上の項目が含まれ、多数の既存心理測定尺度の IPIP 版が提供されています。

### 4.2 構造

- **項目数**: 3,000+ 項目
- **利用可能スケール**: 250以上のスケール構成体（Big Five, 6因子 HEXACO, Dark Triad, Values in Action 等）
- **回答形式**: 多くが5段階リッカートスケール
- **項目形式**: 短文自己記述 ("I am the life of the party", "I make plans and stick to them" 等)

### 4.3 ライセンス

- **パブリックドメイン**
- 全項目が自由に使用・改変・再配布可能
- 商用利用に制限なし
- 個々の項目を抽出して独自スケールの構築が可能

### 4.4 Four_Axis マッピング

| IPIP スケール/構成体 | Four_Axis 対象軸 | マッピング型 | 根拠 |
|-------------------|-----------------|------------|------|
| IPIP版 Jungian Type Scales | 全4軸 | **direct** | ユング型類型論の4二分法を直接測定する IPIP 項目群が存在する |
| Extraversion スケール群 | `extroverted_introverted` | **partial** | 複数の Extraversion 構成体が存在するが、各スケールの範囲は完全一致ではない |
| Openness / Intellect スケール群 | `sensing_intuition` | **partial** | 抽象思考・想像力を測定する項目は S/N と相関するが、全項目が対応するわけではない |
| Conscientiousness / Organization スケール群 | `judging_perceiving` | **partial** | 計画性・秩序性に関する項目は J/P と相関する |
| Agreeableness vs Tough-mindedness | `thinking_feeling` | **partial** | 共感性・協調性を測定する項目は T/F に部分的に対応するが構成概念は異なる |

### 4.5 項目分類

| 分類 | 該当領域 | 理由 |
|------|---------|------|
| **require adaptation** | IPIP版 Jungian Type Scale 項目 | 4軸に直接対応する測定項目だが、自己記述形式からビジネスシナリオ形式への変換が必要 |
| **require adaptation** | Extraversion, Openness, Conscientiousness 関連スケール項目 | 部分的に軸対応する項目が多数存在し、シナリオ化により活用可能 |
| **design reference only** | Dark Triad, Values in Action, 興味・動機系スケール | Four_Axis と測定構成概念が大きく異なり、構造参考に留まる |

### 4.6 活用ポイント

- 3,000+項目のプールから、Four_Axis に最も相関の高い項目を選択的に参照可能
- IPIP版 Jungian Type Scale の存在により、ユング型二分法の測定に直接利用可能な項目がある
- 多様な表現パターンが質問文言のバリエーション設計に有用

---

## 5. Four_Axis マッピング総括

### 5.1 軸別ソース対応表

| Four_Axis 軸 | 最適ソース | マッピング型 | 補助ソース |
|--------------|----------|------------|----------|
| `extroverted_introverted` | OEJTS E/I | direct | IPIP-NEO Extraversion (partial), IPIP Extraversion scales (partial) |
| `sensing_intuition` | OEJTS S/N | direct | IPIP-NEO Openness (partial), IPIP Intellect scales (partial) |
| `thinking_feeling` | OEJTS T/F | direct | IPIP-NEO Agreeableness (partial), IPIP Tough-mindedness (partial) |
| `judging_perceiving` | OEJTS J/P | direct | IPIP-NEO Conscientiousness (partial), IPIP Organization scales (partial) |

### 5.2 設計上の意思決定

1. **構造的基盤**: OEJTS の4二分法構造を Four_Axis モデルの理論的基礎とする
2. **項目設計参照**: IPIP-NEO-120 の30ファセット粒度を活用し、各軸の多面的な行動パターンを網羅する
3. **文言バリエーション**: IPIP 一般リポジトリの豊富な表現パターンを参照し、ビジネスシナリオの多様性を確保する

---

## 6. 適応戦略

### 6.1 変換原則

心理測定の抽象的な特性記述を、具体的なビジネス・ライフスタイルシナリオに変換します。以下の原則に従います。

1. **構成概念の保存**: 元の項目が測定する心理的構成概念（例: 外向性）の核心を維持する
2. **文脈の具体化**: 抽象的な自己記述を、仕事・プロジェクト・日常の具体的場面に置き換える
3. **行動の可観測化**: 内的状態の記述を、観察可能な行動選択として表現する
4. **多軸活性化**: 1つの質問で2軸以上のスコアが変動するよう、シナリオに複合的要素を含める
5. **文化的中立性**: 特定の文化・業界に偏らない普遍的なビジネス場面を選択する

### 6.2 変換例: OEJTS → ビジネスシナリオ

**Before（OEJTS原型）**:
> 双極スケール: "The life of the party" ←→ "Prefer to stay in the background"
> 測定軸: E/I

**After（ビジネスシナリオ）**:
> プロジェクトが危機的状況に陥った時、最初に取る行動は？
> - a) チーム全員を集めて即座にブレインストーミングを開始する [E+, J+]
> - b) 一人で状況を整理し、解決策を練ってから共有する [I+, T+]
> - c) データを集めて根本原因を特定してから対策を立てる [S+, T+]
> - d) 過去の類似事例を参照し、実績ある手法を適用する [S+, J+]

**構成概念の保存**: E/I（集団vs個人での問題対処）を保持しつつ、S/N（データ収集 vs 直観）、T/F（論理 vs 価値）、J/P（計画 vs 即興）の副次的スコアを各選択肢に付与。

### 6.3 変換例: IPIP-NEO-120 → ビジネスシナリオ

**Before（IPIP-NEO-120原型）**:
> "I prefer variety to routine." (Openness - Adventurousness)
> 回答: 5段階リッカート

**After（ビジネスシナリオ）**:
> 新しいプロジェクトのアサインについて、あなたの好みに最も近いものは？
> - a) 未経験の技術領域に挑戦する案件を選ぶ [N+, P+]
> - b) これまでの専門性を深掘りできる案件を選ぶ [S+, J+]
> - c) チームメンバーとの相性を重視して選ぶ [E+, F+]
> - d) 成果が明確に測定できる案件を選ぶ [T+, J+]

**構成概念の保存**: Openness の Adventurousness（新奇性選好）を S/N 軸の直観(N)極として再解釈し、他の選択肢で残り3軸もカバー。

### 6.4 変換例: IPIP 一般リポジトリ → ビジネスシナリオ

**Before（IPIP原型）**:
> "I make plans and stick to them." (Conscientiousness / Organization)
> 回答: 5段階リッカート

**After（ビジネスシナリオ）**:
> 1ヶ月後の大型リリースに向けたスケジュール管理で、あなたのスタイルは？
> - a) 詳細なガントチャートを作り、毎日進捗を追跡する [J+, S+]
> - b) マイルストーンだけ設定し、日々の進め方は柔軟に変える [P+, N+]
> - c) チームの状況を見ながら都度優先度を調整する [E+, F+]
> - d) 技術的リスクを洗い出し、クリティカルパスを重点管理する [T+, J+]

**構成概念の保存**: Conscientiousness の Organization（計画遵守）を J/P 軸の Judging 極として再解釈し、対立選択肢で Perceiving 極、他の選択肢で E/I、T/F 軸も活性化。

### 6.5 構成概念妥当性の保持基準

適応後の質問が元の構成概念を正しく測定していることを確認するための基準:

1. **面妥当性**: 質問文が元の心理的構成概念を直感的に反映している
2. **弁別妥当性**: 各選択肢が異なる極性パターンを明確に示している
3. **内容カバレッジ**: 1カテゴリ内で同一軸が複数項目から測定される（信頼性確保）
4. **応答バイアス回避**: 社会的望ましさによる偏りが生じない等価的選択肢設計

---

## 7. ライセンスコンプライアンス

| ソース | ライセンス | 項目の直接使用 | 構造の参照 | 適応項目の作成 |
|--------|-----------|--------------|-----------|--------------|
| OEJTS | CC BY-NC-SA 4.0 | ❌ 非営利制約あり | ✅ 帰属表示付き | ⚠️ 構造参照のみ、文言は独自作成 |
| IPIP-NEO-120 | パブリックドメイン | ✅ 制限なし | ✅ 制限なし | ✅ 自由に改変可能 |
| IPIP 一般リポジトリ | パブリックドメイン | ✅ 制限なし | ✅ 制限なし | ✅ 自由に改変可能 |

### 7.1 帰属表示

本プロジェクトで心理測定ソースを参照する場合、以下の帰属を記載します:

- OEJTS: "Based on the structural framework of Open Extended Jungian Type Scales (CC BY-NC-SA 4.0)"
- IPIP: "Items adapted from the International Personality Item Pool (public domain, ipip.ori.org)"

---

## 8. 参考文献

- Goldberg, L. R., et al. (2006). The International Personality Item Pool and the future of public-domain personality measures. *Journal of Research in Personality*, 40, 84-96.
- Costa, P. T., & McCrae, R. R. (1992). *NEO PI-R Professional Manual*. Psychological Assessment Resources.
- Johnson, J. A. (2014). Measuring thirty facets of the Five Factor Model with a 120-item public domain inventory. *Journal of Research in Personality*, 51, 78-89.
- Open Psychometrics Project. Open Extended Jungian Type Scales. https://openpsychometrics.org/tests/OEJTS/
