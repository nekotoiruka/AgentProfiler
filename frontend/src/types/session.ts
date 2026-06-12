/**
 * セッション関連の型定義
 * Requirements: 10.4 - セッション管理, 11.2 - 回答送信API
 */

/** セッションのステータス */
export type SessionStatus = 'active' | 'complete' | 'expired';

/**
 * 回答送信データ
 * single_choice: question_id + choice_id (または text)
 * multi_select: question_id + selected_options
 */
export interface AnswerSubmission {
  question_id: string;
  choice_id?: string;
  text?: string;
  selected_options?: string[];
}

/** セッション */
export interface Session {
  session_id: string;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  answered_count: number;
  total_count: number;
  current_category: string;
}
