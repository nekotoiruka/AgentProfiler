<script setup lang="ts">
/**
 * ResultsDashboardView
 * プロファイル結果のビジュアライゼーション＋JSONプレビュー
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
 */
import { ref, computed, onMounted } from 'vue';
import { Radar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { useSessionStore } from '@/stores/session';
import type { ProfileOutput } from '@/types';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const sessionStore = useSessionStore();

// --- State ---
const profile = ref<ProfileOutput | null>(null);
const isLoading = ref(true);
const fetchError = ref<string | null>(null);
const copyStatus = ref<'idle' | 'success' | 'error'>('idle');

// --- Computed ---

/** レーダーチャートデータ */
const chartData = computed(() => {
  if (!profile.value) {
    return { labels: [], datasets: [] };
  }
  const axes = profile.value.base_os.axes;
  return {
    labels: ['外向/内向', '感覚/直観', '論理/感情', '計画/柔軟'],
    datasets: [
      {
        label: 'プロファイルスコア',
        data: [
          axes.extroverted_introverted,
          axes.sensing_intuition,
          axes.thinking_feeling,
          axes.judging_perceiving,
        ],
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgba(59, 130, 246, 1)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(59, 130, 246, 1)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgba(59, 130, 246, 1)',
      },
    ],
  };
});

/** レーダーチャートオプション */
const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: true,
  scales: {
    r: {
      min: 0,
      max: 1.0,
      ticks: {
        stepSize: 0.2,
        backdropColor: 'transparent',
      },
      pointLabels: {
        font: { size: 13 },
      },
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: { enabled: true },
  },
}));

/** JSON文字列（整形済み） */
const formattedJson = computed(() => {
  if (!profile.value) return '';
  return JSON.stringify(profile.value, null, 2);
});

/** シンタックスハイライト済みHTML */
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

/**
 * JSON文字列に基本的なシンタックスハイライトを適用
 * キー・文字列・数値・真偽値・nullを色分け
 */
function highlightJsonSyntax(json: string): string {
  return json
    // キー ("key":) のハイライト
    .replace(/"([^"]+)"(?=\s*:)/g, '<span class="json-key">"$1"</span>')
    // 文字列値のハイライト（キー以外）
    .replace(/:\s*"([^"]*?)"/g, ': <span class="json-string">"$1"</span>')
    // 数値のハイライト
    .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
    // 真偽値・nullのハイライト
    .replace(/:\s*(true|false|null)/g, ': <span class="json-bool">$1</span>');
}

/**
 * クリップボードにJSON全文をコピー
 * 成功時2秒間確認表示、失敗時エラーメッセージ
 */
async function copyToClipboard(): Promise<void> {
  try {
    await navigator.clipboard.writeText(formattedJson.value);
    copyStatus.value = 'success';
    setTimeout(() => {
      copyStatus.value = 'idle';
    }, 2000);
  } catch {
    copyStatus.value = 'error';
  }
}
</script>

<template>
  <div class="results-dashboard">
    <!-- ローディング状態 -->
    <div v-if="isLoading" class="results-dashboard__loading">
      <div class="results-dashboard__spinner" aria-label="読み込み中" />
      <p>プロファイルを読み込んでいます...</p>
    </div>

    <!-- エラー状態 -->
    <div v-else-if="fetchError" class="results-dashboard__error" role="alert">
      <p class="results-dashboard__error-message">{{ fetchError }}</p>
    </div>

    <!-- メインコンテンツ -->
    <template v-else-if="profile">
      <!-- レーダーチャート: 4軸正規化スコア -->
      <section class="results-dashboard__chart">
        <h2 class="results-dashboard__section-title">4軸プロファイルスコア</h2>
        <div class="results-dashboard__chart-container">
          <Radar :data="chartData" :options="chartOptions" />
        </div>
      </section>

      <!-- Decision Style -->
      <section class="results-dashboard__decision-style">
        <h2 class="results-dashboard__section-title">Decision Style</h2>
        <p class="results-dashboard__decision-label">
          {{ profile.base_os.decision_style }}
        </p>
      </section>

      <!-- Do Not List -->
      <section class="results-dashboard__do-not-list">
        <h2 class="results-dashboard__section-title">Do Not List</h2>
        <ul class="results-dashboard__list">
          <li
            v-for="(item, index) in profile.base_os.do_not_list"
            :key="index"
          >
            {{ item }}
          </li>
        </ul>
      </section>

      <!-- Lexical Tags -->
      <section class="results-dashboard__tags">
        <h2 class="results-dashboard__section-title">Lexical Tags</h2>
        <div class="results-dashboard__chip-list">
          <span
            v-for="tag in profile.lexical_tags"
            :key="tag"
            class="results-dashboard__chip"
          >
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
            @click="copyToClipboard"
            :disabled="copyStatus === 'success'"
          >
            <template v-if="copyStatus === 'idle'">コピー</template>
            <template v-else-if="copyStatus === 'success'">コピーしました</template>
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

/* --- ローディング・エラー --- */
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

@keyframes spin {
  to { transform: rotate(360deg); }
}

.results-dashboard__error {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
}

.results-dashboard__error-message {
  color: #dc2626;
  font-weight: 500;
}

/* --- セクション共通 --- */
.results-dashboard__section-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: #1f2937;
}

/* --- レーダーチャート --- */
.results-dashboard__chart {
  margin-bottom: 2rem;
}

.results-dashboard__chart-container {
  max-width: 400px;
  margin: 0 auto;
}

/* --- Decision Style --- */
.results-dashboard__decision-style {
  margin-bottom: 2rem;
}

.results-dashboard__decision-label {
  font-size: 1.25rem;
  font-weight: 700;
  color: #3b82f6;
  word-break: break-all;
}

/* --- Do Not List --- */
.results-dashboard__do-not-list {
  margin-bottom: 2rem;
}

.results-dashboard__list {
  list-style: disc;
  padding-left: 1.5rem;
  line-height: 1.75;
  color: #374151;
}

/* --- Lexical Tags --- */
.results-dashboard__tags {
  margin-bottom: 2rem;
}

.results-dashboard__chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.results-dashboard__chip {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background-color: #eff6ff;
  color: #1d4ed8;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 500;
}

/* --- JSON プレビュー --- */
.results-dashboard__json {
  margin-bottom: 2rem;
}

.results-dashboard__json-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.results-dashboard__json-header .results-dashboard__section-title {
  margin-bottom: 0;
}

.results-dashboard__copy-button {
  padding: 0.375rem 1rem;
  font-size: 0.8125rem;
  font-weight: 500;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background-color: #ffffff;
  color: #374151;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s;
}

.results-dashboard__copy-button:hover:not(:disabled) {
  background-color: #f9fafb;
  border-color: #9ca3af;
}

.results-dashboard__copy-button:disabled {
  background-color: #ecfdf5;
  border-color: #6ee7b7;
  color: #059669;
  cursor: default;
}

.results-dashboard__code-block {
  max-height: 400px;
  overflow-y: auto;
  background-color: #1f2937;
  border-radius: 0.5rem;
  padding: 1rem;
}

.results-dashboard__code-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.results-dashboard__code-block code {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 0.8125rem;
  line-height: 1.6;
  color: #e5e7eb;
}

/* シンタックスハイライト */
.results-dashboard__code-block :deep(.json-key) {
  color: #93c5fd;
}

.results-dashboard__code-block :deep(.json-string) {
  color: #86efac;
}

.results-dashboard__code-block :deep(.json-number) {
  color: #fbbf24;
}

.results-dashboard__code-block :deep(.json-bool) {
  color: #c084fc;
}
</style>
