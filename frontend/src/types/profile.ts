/**
 * プロファイル出力の型定義
 * Requirements: 6.1, 6.2, 6.8 - プロファイルJSON生成
 */

/** 4軸正規化スコア (0.00〜1.00) */
export interface NormalizedScores {
  extroverted_introverted: number;
  sensing_intuition: number;
  thinking_feeling: number;
  judging_perceiving: number;
}

/** Base OS: エージェントの基本トーン＆マナー */
export interface BaseOS {
  axes: NormalizedScores;
  decision_style: string;
  do_not_list: string[];
}

/** コンテキストレイヤーマッピング */
export interface ContextLayers {
  base_os: 1;
  lexical_tags: 2;
  semantic_contexts: 3;
}

/** セマンティックコンテキストのドメインキー */
export type SemanticContextDomain =
  | 'problem_solving'
  | 'communication_style'
  | 'work_rhythm'
  | 'analog_habits'
  | 'lifestyle_preferences';

/** プロファイル出力全体 */
export interface ProfileOutput {
  profile_id: string;
  base_os: BaseOS;
  lexical_tags: string[];
  semantic_contexts: Record<SemanticContextDomain, string>;
  context_layers: ContextLayers;
}
