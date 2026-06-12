/**
 * REST API レスポンス型
 * Requirements: 11.1〜11.6 - REST API設計
 */

import type { Category } from './question';
import type { ProfileOutput } from './profile';

/** POST /api/sessions レスポンス */
export interface CreateSessionResponse {
  session_id: string;
}

/** POST /api/sessions/{id}/answers レスポンス */
export interface SubmitAnswerResponse {
  status: string;
}

/** GET /api/sessions/{id}/status レスポンス */
export interface SessionStatusResponse {
  answered: number;
  total: number;
  category: string;
}

/** GET /api/questions レスポンス */
export interface QuestionsResponse {
  categories: Category[];
}

/** POST /api/sessions/{id}/calculate レスポンス */
export interface CalculateResponse {
  profile_id: string;
}

/** GET /api/sessions/{id}/profile レスポンス */
export type ProfileResponse = ProfileOutput;

/** APIエラーレスポンス */
export interface ApiErrorResponse {
  error: string;
  message: string;
  details?: Array<{
    field: string;
    message: string;
  }>;
}
