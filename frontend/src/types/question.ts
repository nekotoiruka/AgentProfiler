/**
 * 質問データの型定義
 * Requirements: 9.1 - 質問データ管理
 */

/** 選択肢（single_choice型） */
export interface Choice {
  id: string;
  label: string;
}

/** チェックボックス選択肢（multi_select型） */
export interface MultiSelectOption {
  id: string;
  label: string;
  tags: string[];
}

/** 質問タイプ */
export type QuestionType = 'single_choice' | 'multi_select';

/** 質問 */
export interface Question {
  id: string;
  text: string;
  category_id: string;
  question_type: QuestionType;
  source_reference: string;
  /** single_choice型の選択肢 */
  choices: Choice[];
  /** multi_select型の選択肢 */
  options: MultiSelectOption[];
  /** multi_select: 最低選択数 (0=制限なし) */
  min_select: number;
  /** multi_select: 最大選択数 (0=制限なし) */
  max_select: number;
}

/** カテゴリ */
export interface Category {
  id: string;
  name: string;
  order: number;
  questions: Question[];
}
