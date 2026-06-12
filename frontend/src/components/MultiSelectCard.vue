<script setup lang="ts">
/**
 * MultiSelectCard コンポーネント
 * チェックボックス型の複数選択質問を表示する。
 * 趣味・興味・好きなもの等の収集に使用（スコアリング非対象）。
 */
import { computed } from 'vue';
import type { Question } from '@/types/question';

// --- Props & Emits ---
interface MultiSelectCardProps {
  question: Question;
  selectedOptions: string[];
  direction: 'forward' | 'backward';
}

const props = defineProps<MultiSelectCardProps>();

const emit = defineEmits<{
  (e: 'toggle-option', optionId: string): void;
  (e: 'next'): void;
  (e: 'back'): void;
}>();

// --- Computed ---

/** 選択数 */
const selectedCount = computed(() => props.selectedOptions.length);

/** 最低選択数を満たしているか */
const meetsMinimum = computed(() => {
  if (props.question.min_select === 0) return true;
  return selectedCount.value >= props.question.min_select;
});

/** 最大選択数に達しているか */
const atMaximum = computed(() => {
  if (props.question.max_select === 0) return false;
  return selectedCount.value >= props.question.max_select;
});

/** Nextボタンの有効状態 */
const isNextDisabled = computed(() => !meetsMinimum.value);

/** 選択数テキスト */
const selectionText = computed(() => {
  const min = props.question.min_select;
  const max = props.question.max_select;
  if (min > 0 && max > 0) {
    return `${selectedCount.value}件選択中（${min}〜${max}件）`;
  }
  if (min > 0) {
    return `${selectedCount.value}件選択中（${min}件以上）`;
  }
  if (max > 0) {
    return `${selectedCount.value}件選択中（最大${max}件）`;
  }
  return `${selectedCount.value}件選択中`;
});

// --- Methods ---

function isSelected(optionId: string): boolean {
  return props.selectedOptions.includes(optionId);
}

function isDisabled(optionId: string): boolean {
  // 最大数到達時、未選択の項目を無効化
  return atMaximum.value && !isSelected(optionId);
}

function handleToggle(optionId: string): void {
  if (isDisabled(optionId)) return;
  emit('toggle-option', optionId);
}

function handleNext(): void {
  if (!isNextDisabled.value) {
    emit('next');
  }
}

function handleBack(): void {
  emit('back');
}
</script>

<template>
  <Transition
    :name="direction === 'forward' ? 'card-flip-forward' : 'card-flip-backward'"
    mode="out-in"
  >
    <article
      :key="question.id"
      class="multi-select-card"
      role="group"
      :aria-label="`質問: ${question.text}`"
    >
      <!-- 質問テキスト -->
      <h2 class="multi-select-card__text">
        {{ question.text }}
      </h2>

      <!-- 選択数表示 -->
      <p class="multi-select-card__count" aria-live="polite">
        {{ selectionText }}
      </p>

      <!-- チェックボックスリスト -->
      <div class="multi-select-card__options" role="group" aria-label="選択肢">
        <label
          v-for="option in question.options"
          :key="option.id"
          class="multi-select-card__option"
          :class="{
            'multi-select-card__option--selected': isSelected(option.id),
            'multi-select-card__option--disabled': isDisabled(option.id),
          }"
        >
          <input
            type="checkbox"
            class="multi-select-card__checkbox"
            :value="option.id"
            :checked="isSelected(option.id)"
            :disabled="isDisabled(option.id)"
            @change="handleToggle(option.id)"
          />
          <span class="multi-select-card__label">{{ option.label }}</span>
        </label>
      </div>

      <!-- ナビゲーション -->
      <div class="multi-select-card__actions">
        <button
          type="button"
          class="multi-select-card__back-btn"
          aria-label="前の質問に戻る"
          @click="handleBack"
        >
          ← 戻る
        </button>
        <button
          type="button"
          class="multi-select-card__next-btn"
          :disabled="isNextDisabled"
          aria-label="次の質問に進む"
          @click="handleNext"
        >
          次へ →
        </button>
      </div>
    </article>
  </Transition>
</template>

<style scoped>
/* Card flip animations (shared with QuestionCard) */
.card-flip-forward-enter-active,
.card-flip-forward-leave-active {
  transition: transform 400ms ease, opacity 400ms ease;
  backface-visibility: hidden;
}
.card-flip-forward-enter-from {
  transform: perspective(1200px) rotateY(90deg);
  opacity: 0;
}
.card-flip-forward-leave-to {
  transform: perspective(1200px) rotateY(-90deg);
  opacity: 0;
}
.card-flip-backward-enter-active,
.card-flip-backward-leave-active {
  transition: transform 400ms ease, opacity 400ms ease;
  backface-visibility: hidden;
}
.card-flip-backward-enter-from {
  transform: perspective(1200px) rotateY(-90deg);
  opacity: 0;
}
.card-flip-backward-leave-to {
  transform: perspective(1200px) rotateY(90deg);
  opacity: 0;
}

/* Card layout */
.multi-select-card {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 2rem;
  max-width: 640px;
  margin: 0 auto;
}

.multi-select-card__text {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.6;
  margin: 0 0 0.75rem;
  color: #1a1a2e;
}

.multi-select-card__count {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0 0 1.25rem;
}

/* Options grid */
.multi-select-card__options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.625rem;
  margin-bottom: 1.5rem;
}

.multi-select-card__option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background: #fafafa;
  cursor: pointer;
  transition: border-color 200ms, background-color 200ms;
  user-select: none;
}

.multi-select-card__option:hover:not(.multi-select-card__option--disabled) {
  border-color: #6c63ff;
  background: #f5f3ff;
}

.multi-select-card__option--selected {
  border-color: #6c63ff;
  background: #ede9fe;
}

.multi-select-card__option--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.multi-select-card__checkbox {
  width: 1.125rem;
  height: 1.125rem;
  accent-color: #6c63ff;
  cursor: inherit;
  flex-shrink: 0;
}

.multi-select-card__label {
  font-size: 0.9rem;
  line-height: 1.4;
  color: #333;
}

/* Actions (same style as QuestionCard) */
.multi-select-card__actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
}

.multi-select-card__back-btn {
  padding: 0.625rem 1.25rem;
  font-size: 0.9rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: transparent;
  color: #555;
  cursor: pointer;
  transition: background-color 200ms;
}

.multi-select-card__back-btn:hover {
  background: #f0f0f0;
}

.multi-select-card__back-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.multi-select-card__next-btn {
  padding: 0.625rem 1.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  border: none;
  border-radius: 6px;
  background: #6c63ff;
  color: #fff;
  cursor: pointer;
  transition: background-color 200ms, opacity 200ms;
}

.multi-select-card__next-btn:hover:not(:disabled) {
  background: #5a52d5;
}

.multi-select-card__next-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.multi-select-card__next-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

@media (max-width: 600px) {
  .multi-select-card {
    padding: 1.25rem;
  }
  .multi-select-card__options {
    grid-template-columns: 1fr;
  }
}
</style>
