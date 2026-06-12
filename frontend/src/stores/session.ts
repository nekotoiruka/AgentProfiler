/**
 * セッション管理 Pinia ストア
 * Requirements: 10.1, 10.2, 11.1, 11.2 - セッションID管理、回答送信、ステータス取得
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiFetch } from '@/composables/useApi';
import type {
  SessionStatus,
  AnswerSubmission,
  ProfileOutput,
  CreateSessionResponse,
  SubmitAnswerResponse,
  SessionStatusResponse,
  CalculateResponse,
  ProfileResponse,
} from '@/types';

export const useSessionStore = defineStore('session', () => {
  // --- State ---
  const sessionId = ref<string | null>(null);
  const status = ref<SessionStatus>('active');
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  // --- Getters ---
  const isActive = computed(() => status.value === 'active');
  const isComplete = computed(() => status.value === 'complete');

  // --- Actions ---

  /** エラーを安全に文字列化 */
  function extractErrorMessage(e: unknown): string {
    if (e instanceof Error) return e.message;
    return String(e);
  }

  /** 新規セッション作成: POST /sessions */
  async function createSession(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      const data = await apiFetch<CreateSessionResponse>('/sessions', {
        method: 'POST',
      });
      sessionId.value = data.session_id;
      status.value = 'active';
    } catch (e) {
      error.value = extractErrorMessage(e);
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /** 回答送信: POST /sessions/{id}/answers */
  async function submitAnswer(submission: AnswerSubmission): Promise<void> {
    if (!sessionId.value) {
      throw new Error('セッションが開始されていません');
    }
    isLoading.value = true;
    error.value = null;
    try {
      await apiFetch<SubmitAnswerResponse>(
        `/sessions/${sessionId.value}/answers`,
        {
          method: 'POST',
          body: JSON.stringify(submission),
        },
      );
    } catch (e) {
      error.value = extractErrorMessage(e);
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /** ステータス取得: GET /sessions/{id}/status */
  async function fetchStatus(): Promise<SessionStatusResponse> {
    if (!sessionId.value) {
      throw new Error('セッションが開始されていません');
    }
    isLoading.value = true;
    error.value = null;
    try {
      const data = await apiFetch<SessionStatusResponse>(
        `/sessions/${sessionId.value}/status`,
      );
      return data;
    } catch (e) {
      error.value = extractErrorMessage(e);
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /** スコア計算+プロファイル生成: POST /sessions/{id}/calculate */
  async function calculateProfile(): Promise<string> {
    if (!sessionId.value) {
      throw new Error('セッションが開始されていません');
    }
    isLoading.value = true;
    error.value = null;
    try {
      const data = await apiFetch<CalculateResponse>(
        `/sessions/${sessionId.value}/calculate`,
        { method: 'POST' },
      );
      status.value = 'complete';
      return data.profile_id;
    } catch (e) {
      error.value = extractErrorMessage(e);
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /** プロファイル取得: GET /sessions/{id}/profile */
  async function fetchProfile(): Promise<ProfileOutput> {
    if (!sessionId.value) {
      throw new Error('セッションが開始されていません');
    }
    isLoading.value = true;
    error.value = null;
    try {
      const data = await apiFetch<ProfileResponse>(
        `/sessions/${sessionId.value}/profile`,
      );
      return data;
    } catch (e) {
      error.value = extractErrorMessage(e);
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /** ストアをリセット（新規セッション開始時等に使用） */
  function $reset(): void {
    sessionId.value = null;
    status.value = 'active';
    isLoading.value = false;
    error.value = null;
  }

  return {
    // State
    sessionId,
    status,
    isLoading,
    error,
    // Getters
    isActive,
    isComplete,
    // Actions
    createSession,
    submitAnswer,
    fetchStatus,
    calculateProfile,
    fetchProfile,
    $reset,
  };
});
