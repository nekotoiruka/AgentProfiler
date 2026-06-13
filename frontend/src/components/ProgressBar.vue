<script setup lang="ts">
/**
 * ProgressBar コンポーネント
 * カテゴリ内進捗と全体進捗の両方をビジュアルバーで表示する。
 * Validates: Requirements 1.3, 1.4
 */

interface ProgressBarProps {
  categoryName: string;
  categoryProgress: number; // 0-100 integer
  overallProgress: number;  // 0-100 integer
}

const props = defineProps<ProgressBarProps>();

// 値を0-100の範囲にクランプ（不正値の防御）
function clamp(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}
</script>

<template>
  <div class="progress-bar">
    <!-- カテゴリ内進捗 -->
    <div class="progress-section">
      <div class="progress-label">
        <span class="category-name">{{ props.categoryName }}</span>
        <span class="progress-value">{{ clamp(props.categoryProgress) }}%</span>
      </div>
      <div
        class="progress-track"
        role="progressbar"
        :aria-valuenow="clamp(props.categoryProgress)"
        :aria-valuemin="0"
        :aria-valuemax="100"
        :aria-label="`${props.categoryName}の進捗: ${clamp(props.categoryProgress)}%`"
      >
        <div
          class="progress-fill"
          :style="{ width: `${clamp(props.categoryProgress)}%` }"
        />
      </div>
    </div>

    <!-- 全体進捗 -->
    <div class="progress-section">
      <div class="progress-label">
        <span class="category-name">全体進捗</span>
        <span class="progress-value">{{ clamp(props.overallProgress) }}%</span>
      </div>
      <div
        class="progress-track"
        role="progressbar"
        :aria-valuenow="clamp(props.overallProgress)"
        :aria-valuemin="0"
        :aria-valuemax="100"
        :aria-label="`全体進捗: ${clamp(props.overallProgress)}%`"
      >
        <div
          class="progress-fill"
          :style="{ width: `${clamp(props.overallProgress)}%` }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
  line-height: 1.25rem;
}

.category-name {
  font-weight: 500;
  color: var(--color-foreground);
}

.progress-value {
  font-variant-numeric: tabular-nums;
  color: var(--color-muted-foreground);
}

.progress-track {
  height: 8px;
  border-radius: 4px;
  background-color: var(--color-border);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  background-color: #3b82f6;
  transition: width 300ms ease;
}
</style>
