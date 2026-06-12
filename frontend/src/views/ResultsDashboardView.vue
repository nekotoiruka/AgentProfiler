<script setup lang="ts">
/**
 * ResultsDashboardView
 * プロファイル結果のビジュアライゼーション＋JSONプレビュー
 * 双極スライダーUI + 16タイプ日本語名表示
 */
import { ref, computed, onMounted } from 'vue';
import { useSessionStore } from '@/stores/session';
import type { ProfileOutput } from '@/types';

const sessionStore = useSessionStore();

// --- State ---
const profile = ref<ProfileOutput | null>(null);
const isLoading = ref(true);
const fetchError = ref<string | null>(null);
const copyStatus = ref<'idle' | 'success' | 'error'>('idle');

// --- 軸表示情報 ---
const axisLabels = [
  { key: 'extroverted_introverted', leftLabel: '内向的', rightLabel: '外向的', leftCode: 'I', rightCode: 'E' },
  { key: 'sensing_intuition', leftLabel: '直観的', rightLabel: '感覚的', leftCode: 'N', rightCode: 'S' },
  { key: 'thinking_feeling', leftLabel: '感情的', rightLabel: '論理的', leftCode: 'F', rightCode: 'T' },
  { key: 'judging_perceiving', leftLabel: '柔軟的', rightLabel: '計画的', leftCode: 'P', rightCode: 'J' },
] as const;

// --- Computed ---

const formattedJson = computed(() => {
  if (!profile.value) return '';
  return JSON.stringify(profile.value, null, 2);
});

const highlightedJson = computed(() => {
  if (!formattedJson.value) return '';
  return highlightJsonSyntax(formattedJson.value);
});

// --- Lifecycle ---

onMounted(async () => {
  try {
    profile.value = await sessionStore.fetchProfile();
  } catch (e) {
    fetchError.value = e instanceof Error ? e.message : String(e);
  } finally {
    isLoading.value = false;
  }
});

// --- Functions ---

function getAxisValue(key: string): number {
  if (!profile.value) return 0.5;
  const axes = profile.value.base_os.axes as Record<string, number>;
  return axes[key] ?? 0.5;
}

function getSliderPercent(key: string): number {
  return Math.round(getAxisValue(key) * 100);
}

function highlightJsonSyntax(json: string): string {
  return json
    .replace(/"([^"]+)"(?=\s*:)/g, '<span class="json-key">"$1"</span>')
    .replace(/:\s*"([^"]*?)"/g, ': <span class="json-string">"$1"</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="json-bool">$1</span>');
}

async function copyToClipboard(): Promise<void> {
  try {
    await navigator.clipboard.writeText(formattedJson.value);
    copyStatus.value = 'success';
    setTimeout(() => { copyStatus.value = 'idle'; }, 2000);
  } catch {
    copyStatus.value = 'error';
  }
}
</script>

<template>
  <div class="results-dashboard">
    <!-- ローディング -->
    <div v-if="isLoading" class="results-dashboard__loading">
      <div class="results-dashboard__spinner" aria-label="読み込み中" />
      <p>プロファイルを読み込んでいます...</p>
    </div>

    <!-- エラー -->
    <div v-else-if="fetchError" class="results-dashboard__error" role="alert">
      <p class="results-dashboard__error-message">{{ fetchError }}</p>
    </div>

    <!-- メインコンテンツ -->
    <template v-else-if="profile">
      <!-- Decision Style (16タイプ名) -->
      <section class="results-dashboard__type">
        <p class="results-dashboard__type-name">
          {{ profile.base_os.decision_style }}
        </p>
      </section>

      <!-- 双極スライダー: 4軸 -->
      <section class="results-dashboard__axes">
        <h2 class="results-dashboard__section-title">思考特性プロファイル</h2>
        <p class="results-dashboard__axes-note">
          各軸は「傾向の方向」を示します。どちらが優れているということではありません。
        </p>
        <div
          v-for="axis in axisLabels"
          :key="axis.key"
          class="bipolar-slider"
        >
          <div class="bipolar-slider__labels">
            <span class="bipolar-slider__label bipolar-slider__label--left">
              {{ axis.leftLabel }}
              <span class="bipolar-slider__code">{{ axis.leftCode }}</span>
            </span>
            <span class="bipolar-slider__label bipolar-slider__label--right">
              <span class="bipolar-slider__code">{{ axis.rightCode }}</span>
              {{ axis.rightLabel }}
            </span>
          </div>
          <div class="bipolar-slider__track">
            <div class="bipolar-slider__center-line" />
            <div
              class="bipolar-slider__indicator"
              :style="{ left: `${getSliderPercent(axis.key)}%` }"
            />
          </div>
          <div class="bipolar-slider__value">
            {{ getAxisValue(axis.key).toFixed(2) }}
          </div>
        </div>
      </section>

      <!-- Do Not List -->
      <section class="results-dashboard__do-not-list">
        <h2 class="results-dashboard__section-title">Do Not List</h2>
        <ul class="results-dashboard__list">
          <li v-for="(item, index) in profile.base_os.do_not_list" :key="index">
            {{ item }}
          </li>
        </ul>
      </section>

      <!-- Lexical Tags -->
      <section class="results-dashboard__tags">
        <h2 class="results-dashboard__section-title">Lexical Tags</h2>
        <div class="results-dashboard__chip-list">
          <span v-for="tag in profile.lexical_tags" :key="tag" class="results-dashboard__chip">
            {{ tag }}
          </span>
        </div>
      </section>

      <!-- JSON プレビュー -->
      <section class="results-dashboard__json">
        <div class="results-dashboard__json-header">
          <h2 class="results-dashboard__section-title">プロファイル JSON</h2>
          <button
            class="results-dashboard__copy-button"
            :disabled="copyStatus === 'success'"
            @click="copyToClipboard"
          >
            <template v-if="copyStatus === 'idle'">コピー</template>
            <template v-else-if="copyStatus === 'success'">コピーしました ✓</template>
            <template v-else>コピーに失敗しました</template>
          </button>
        </div>
        <div class="results-dashboard__code-block">
          <pre><code v-html="highlightedJson"></code></pre>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.results-dashboard {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
}

.results-dashboard__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  gap: 1rem;
}

.results-dashboard__spinner {
  width: 2.5rem;
  height: 2.5rem;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.results-dashboard__error { display: flex; align-items: center; justify-content: center; min-height: 40vh; }
.results-dashboard__error-message { color: #dc2626; font-weight: 500; }

.results-dashboard__section-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: #1f2937;
}

/* --- Type Name --- */
.results-dashboard__type {
  text-align: center;
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, #1e1b4b, #312e81);
  border-radius: 12px;
}

.results-dashboard__type-name {
  font-size: 1.75rem;
  font-weight: 800;
  color: #e0e7ff;
  letter-spacing: 0.05em;
  margin: 0;
}

/* --- Bipolar Slider --- */
.results-dashboard__axes {
  margin-bottom: 2rem;
}

.results-dashboard__axes-note {
  font-size: 0.8rem;
  color: #6b7280;
  margin-bottom: 1.25rem;
  font-style: italic;
}

.bipolar-slider {
  margin-bottom: 1.5rem;
}

.bipolar-slider__labels {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.375rem;
}

.bipolar-slider__label {
  font-size: 0.85rem;
  font-weight: 500;
  color: #374151;
}

.bipolar-slider__code {
  font-weight: 700;
  color: #6c63ff;
  margin: 0 0.25rem;
}

.bipolar-slider__track {
  position: relative;
  height: 12px;
  background: linear-gradient(to right, #818cf8, #e5e7eb 50%, #34d399);
  border-radius: 6px;
  overflow: visible;
}

.bipolar-slider__center-line {
  position: absolute;
  left: 50%;
  top: -2px;
  bottom: -2px;
  width: 2px;
  background: #9ca3af;
  transform: translateX(-50%);
}

.bipolar-slider__indicator {
  position: absolute;
  top: 50%;
  width: 20px;
  height: 20px;
  background: #1f2937;
  border: 3px solid #ffffff;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  transition: left 0.3s ease;
}

.bipolar-slider__value {
  text-align: center;
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
  font-variant-numeric: tabular-nums;
}

/* --- Do Not List --- */
.results-dashboard__do-not-list { margin-bottom: 2rem; }
.results-dashboard__list { list-style: disc; padding-left: 1.5rem; line-height: 1.75; color: #374151; }

/* --- Tags --- */
.results-dashboard__tags { margin-bottom: 2rem; }
.results-dashboard__chip-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.results-dashboard__chip {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background-color: #eff6ff;
  color: #1d4ed8;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 500;
}

/* --- JSON Preview --- */
.results-dashboard__json { margin-bottom: 2rem; }
.results-dashboard__json-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }
.results-dashboard__json-header .results-dashboard__section-title { margin-bottom: 0; }
.results-dashboard__copy-button {
  padding: 0.375rem 1rem;
  font-size: 0.8125rem;
  font-weight: 500;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background-color: #ffffff;
  color: #374151;
  cursor: pointer;
  transition: background-color 0.15s;
}
.results-dashboard__copy-button:hover:not(:disabled) { background-color: #f9fafb; }
.results-dashboard__copy-button:disabled { background-color: #ecfdf5; border-color: #6ee7b7; color: #059669; cursor: default; }

.results-dashboard__code-block {
  max-height: 400px;
  overflow-y: auto;
  background-color: #1f2937;
  border-radius: 0.5rem;
  padding: 1rem;
}
.results-dashboard__code-block pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
.results-dashboard__code-block code { font-family: 'Menlo', monospace; font-size: 0.8125rem; line-height: 1.6; color: #e5e7eb; }
.results-dashboard__code-block :deep(.json-key) { color: #93c5fd; }
.results-dashboard__code-block :deep(.json-string) { color: #86efac; }
.results-dashboard__code-block :deep(.json-number) { color: #fbbf24; }
.results-dashboard__code-block :deep(.json-bool) { color: #c084fc; }
</style>
