/**
 * API通信ラッパー
 * Requirements: 11.1, 11.2, 11.3 - REST API通信
 *
 * 指数バックオフ付きリトライ（5xxおよびネットワークエラー対象、最大3回）
 */

import type { ApiErrorResponse } from '@/types';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

/** API通信で発生するエラー */
export class ApiError extends Error {
  constructor(
    public status: number,
    public body: ApiErrorResponse,
  ) {
    super(body.message || body.error);
    this.name = 'ApiError';
  }
}

/** ネットワーク/リトライ限界超過エラー */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NetworkError';
  }
}

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 500;

/**
 * リトライ対象か判定
 * - ネットワークエラー（fetch自体の失敗）
 * - 5xx系ステータス
 */
function isRetryable(error: unknown): boolean {
  if (error instanceof NetworkError) return true;
  if (error instanceof ApiError && error.status >= 500) return true;
  return false;
}

/** 指数バックオフの待機時間を計算 */
function getBackoffDelay(attempt: number): number {
  // 2^attempt * BASE_DELAY_MS にジッターを加える
  const delay = BASE_DELAY_MS * Math.pow(2, attempt);
  const jitter = delay * 0.1 * Math.random();
  return delay + jitter;
}

/** 指定ms待機 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 型安全なAPIフェッチラッパー
 *
 * @param url - APIパス（/sessions など。BASE_URLが自動付与される）
 * @param options - fetch RequestInit オプション
 * @returns パース済みレスポンスボディ
 */
export async function apiFetch<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const fullUrl = `${BASE_URL}${url}`;

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  const mergedOptions: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers as Record<string, string>),
    },
  };

  let lastError: unknown;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(fullUrl, mergedOptions);

      if (!response.ok) {
        let body: ApiErrorResponse;
        try {
          body = await response.json();
        } catch {
          body = { error: 'unknown', message: response.statusText };
        }
        throw new ApiError(response.status, body);
      }

      const data: T = await response.json();
      return data;
    } catch (error) {
      // fetch自体が失敗した場合（ネットワークエラー）
      if (error instanceof TypeError) {
        lastError = new NetworkError(error.message);
      } else {
        lastError = error;
      }

      // リトライ対象かつ最大試行回数未到達なら待機してリトライ
      if (isRetryable(lastError) && attempt < MAX_RETRIES) {
        await sleep(getBackoffDelay(attempt));
        continue;
      }

      throw lastError;
    }
  }

  // 到達しないはずだが型安全のため
  throw lastError;
}
