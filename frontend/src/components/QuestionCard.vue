<script setup lang="ts">
/**
 * QuestionCard コンポーネント
 * カードフリップアニメーション付きの質問表示
 * Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
 */
import { computed } from 'vue';
import type { Question } from '@/types/question';

// --- 定数 ---
const OTHER_ID = '__other__';
const MAX_CHARS = 500;

// --- Props & Emits ---
interface QuestionCardProps {
  question: Question;
  selectedChoiceId: string | null;
  otherText: string;
  direction: 'forward' | 'backward';
}

const props = defineProps<QuestionCardProps>();

const emit = defineEmits<{
  (e: 'select-choice', choiceId: string): void;
  (e: 'select-other'): void;
  (e: 'update-other-text', text: string): void;
  (e: 'next'): void;
  (e: 'back'): void;
}>();

// --- Computed ---

/** Other が選択されているか */
const isOtherSelected = computed(() => props.selectedChoiceId === OTHER_ID);

/** Otherテキストに有効な文字（空白以外）が含まれるか */
const hasValidOtherText = computed(
  () => props.otherText.trim().length > 0,
);

/** Nextボタンの有効状態: 定義済み選択肢が選ばれているか、Otherに有効テキストがあるか */
const isNextDisabled = computed(() => {
  if (props.selectedChoiceId === null) return true;
  if (isOtherSelected.value && !hasValidOtherText.value) return true;
  return false;
});

/** 文字数カウント表示 */
const charCount = computed(() => `${props.otherText.length} / ${MAX_CHARS}`);

// --- Methods ---

function handleChoiceSelect(choiceId: string): void {
  emit('select-choice', choiceId);
}

function handleOtherSelect(): void {
  emit('select-other');
}

function handleOtherInput(event: Event): void {
  const target = event.target as HTMLTextAreaElement;
  // 500文字制限: maxlength属性で制御しつつ、JSでも安全策
  const text = target.value.slice(0, MAX_CHARS);
  emit('update-other-text', text);
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
      class="question-card"
      role="group"
      :aria-label="`質問: ${question.text}`"
    >
      <!-- 質問テキスト -->
      <h2 class="question-card__text">
        {{ question.text }}
      </h2>

      <!-- 選択肢リスト -->
      <div
        class="question-card__choices"
        role="radiogroup"
        aria-label="選択肢"
      >
        <button
          v-for="choice in question.choices"
          :key="choice.id"
          type="button"
          class="question-card__choice-btn"
          :class="{ 'question-card__choice-btn--selected': selectedChoiceId === choice.id }"
          :aria-pressed="selectedChoiceId === choice.id"
          @click="handleChoiceSelect(choice.id)"
        >
          {{ choice.label }}
        </button>

        <!-- Other ボタン -->
        <button
          type="button"
          class="question-card__choice-btn question-card__choice-btn--other"
          :class="{ 'question-card__choice-btn--selected': isOtherSelected }"
          :aria-pressed="isOtherSelected"
          @click="handleOtherSelect"
        >
          Other
        </button>
      </div>

      <!-- Other テキストエリア（slide-in animation） -->
      <Transition name="slide-in">
        <div
          v-if="isOtherSelected"
          class="question-card__other-area"
        >
          <label
            :for="`other-textarea-${question.id}`"
            class="question-card__other-label"
          >
            自由回答（最大{{ MAX_CHARS }}文字）
          </label>
          <textarea
            :id="`other-textarea-${question.id}`"
            class="question-card__other-textarea"
            :value="otherText"
            :maxlength="MAX_CHARS"
            rows="4"
            placeholder="あなたの回答を入力してください..."
            aria-describedby="char-count"
            @input="handleOtherInput"
          />
          <span
            id="char-count"
            class="question-card__char-count"
            :class="{ 'question-card__char-count--limit': otherText.length >= MAX_CHARS }"
          >
            {{ charCount }}
          </span>
        </div>
      </Transition>

      <!-- ナビゲーション -->
      <div class="question-card__actions">
        <button
          type="button"
          class="question-card__back-btn"
          aria-label="前の質問に戻る"
          @click="handleBack"
        >
          ← 戻る
        </button>
        <button
          type="button"
          class="question-card__next-btn"
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
/* --- Card flip animation (forward: rotateY, 400ms) --- */
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

/* --- Card flip animation (backward: reverse direction) --- */
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

/* --- Slide-in transition for Other textarea (300ms) --- */
.slide-in-enter-active,
.slide-in-leave-active {
  transition: max-height 300ms ease, opacity 300ms ease;
  overflow: hidden;
}

.slide-in-enter-from,
.slide-in-leave-to {
  max-height: 0;
  opacity: 0;
}

.slide-in-enter-to,
.slide-in-leave-from {
  max-height: 300px;
  opacity: 1;
}

/* --- Card layout --- */
.question-card {
  background: var(--color-card);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 2rem;
  max-width: 640px;
  margin: 0 auto;
}

.question-card__text {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.6;
  margin: 0 0 1.5rem;
  color: var(--color-foreground);
}

/* --- Choices --- */
.question-card__choices {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.question-card__choice-btn {
  display: block;
  width: 100%;
  padding: 0.875rem 1.25rem;
  font-size: 0.95rem;
  line-height: 1.5;
  text-align: left;
  border: 2px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-foreground);
  cursor: pointer;
  transition: border-color 200ms, background-color 200ms, box-shadow 200ms;
}

.question-card__choice-btn:hover {
  border-color: #6c63ff;
  background: var(--color-primary-muted);
}

.question-card__choice-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.question-card__choice-btn--selected {
  border-color: #6c63ff;
  background: var(--color-primary-muted);
  color: var(--color-foreground);
  box-shadow: 0 0 0 1px #6c63ff;
  font-weight: 500;
}

.question-card__choice-btn--other {
  border-style: dashed;
}

/* --- Other textarea area --- */
.question-card__other-area {
  margin-bottom: 1.5rem;
}

.question-card__other-label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-muted-foreground);
  margin-bottom: 0.5rem;
}

.question-card__other-textarea {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 0.95rem;
  line-height: 1.5;
  border: 2px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-foreground);
  resize: vertical;
  transition: border-color 200ms;
  box-sizing: border-box;
}

.question-card__other-textarea:focus {
  border-color: #6c63ff;
  outline: none;
}

.question-card__char-count {
  display: block;
  text-align: right;
  font-size: 0.8rem;
  color: var(--color-muted-foreground);
  margin-top: 0.25rem;
}

.question-card__char-count--limit {
  color: #e53935;
  font-weight: 600;
}

/* --- Actions --- */
.question-card__actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
}

.question-card__back-btn {
  padding: 0.625rem 1.25rem;
  font-size: 0.9rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: transparent;
  color: var(--color-muted-foreground);
  cursor: pointer;
  transition: background-color 200ms, border-color 200ms;
}

.question-card__back-btn:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-muted-foreground);
}

.question-card__back-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.question-card__next-btn {
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

.question-card__next-btn:hover:not(:disabled) {
  background: #5a52d5;
}

.question-card__next-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.question-card__next-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* --- Responsive --- */
@media (max-width: 600px) {
  .question-card {
    padding: 1.25rem;
    border-radius: 8px;
  }

  .question-card__text {
    font-size: 1.1rem;
  }

  .question-card__choice-btn {
    padding: 0.75rem 1rem;
    font-size: 0.9rem;
  }
}
</style>
