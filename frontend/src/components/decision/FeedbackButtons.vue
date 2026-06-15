<script setup lang="ts">
/**
 * FeedbackButtons コンポーネント
 * エージェント回答下部のフィードバック3ボタン UI
 * Requirements: 11.1, 11.2
 */
import { ref, computed } from 'vue'

type FeedbackType = 'approve' | 'reject' | 'skip'

interface FeedbackEvent {
  feedback_type: FeedbackType
  user_correction?: string
}

const MAX_CHARS = 2000

const emit = defineEmits<{
  feedback: [payload: FeedbackEvent]
}>()

// reject 時にテキストエリアを表示するフラグ
const showCorrection = ref(false)
const correctionText = ref('')

const charCount = computed(() => correctionText.value.length)
const isAtLimit = computed(() => charCount.value >= MAX_CHARS)

// reject テキストが有効か（1文字以上の非空白）
const hasValidCorrection = computed(
  () => correctionText.value.trim().length > 0,
)

function handleApprove() {
  resetState()
  emit('feedback', { feedback_type: 'approve' })
}

function handleReject() {
  if (!showCorrection.value) {
    // テキストエリアを展開
    showCorrection.value = true
    return
  }
  // テキスト入力済みの場合は送信
  if (hasValidCorrection.value) {
    emit('feedback', {
      feedback_type: 'reject',
      user_correction: correctionText.value.trim(),
    })
    resetState()
  }
}

function handleSkip() {
  resetState()
  emit('feedback', { feedback_type: 'skip' })
}

function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  // 2000文字制限: maxlength 属性と JS 両方で制御
  correctionText.value = target.value.slice(0, MAX_CHARS)
}

function resetState() {
  showCorrection.value = false
  correctionText.value = ''
}
</script>

<template>
  <div class="feedback-buttons" role="group" aria-label="フィードバック">
    <div class="feedback-buttons__actions">
      <button
        type="button"
        class="feedback-btn feedback-btn--approve"
        aria-label="私らしい"
        @click="handleApprove"
      >
        <span class="feedback-btn__icon">👍</span>
        <span class="feedback-btn__label">私らしい</span>
      </button>

      <button
        type="button"
        class="feedback-btn feedback-btn--reject"
        :class="{ 'feedback-btn--active': showCorrection }"
        aria-label="私ならこう言わない"
        :aria-expanded="showCorrection"
        @click="handleReject"
      >
        <span class="feedback-btn__icon">✏️</span>
        <span class="feedback-btn__label">私ならこう言わない</span>
      </button>

      <button
        type="button"
        class="feedback-btn feedback-btn--skip"
        aria-label="スキップ"
        @click="handleSkip"
      >
        <span class="feedback-btn__icon">⏭️</span>
        <span class="feedback-btn__label">スキップ</span>
      </button>
    </div>

    <!-- reject 時のテキストエリア展開 -->
    <Transition name="slide-in">
      <div v-if="showCorrection" class="feedback-buttons__correction">
        <label
          for="correction-textarea"
          class="feedback-buttons__correction-label"
        >
          あなたならどう言いますか？（最大{{ MAX_CHARS }}文字）
        </label>
        <textarea
          id="correction-textarea"
          class="feedback-buttons__textarea"
          :value="correctionText"
          :maxlength="MAX_CHARS"
          rows="4"
          placeholder="あなたの表現を入力してください..."
          aria-describedby="correction-char-count"
          @input="handleInput"
        />
        <div class="feedback-buttons__textarea-footer">
          <span
            id="correction-char-count"
            class="feedback-buttons__char-count"
            :class="{ 'feedback-buttons__char-count--limit': isAtLimit }"
          >
            {{ charCount }} / {{ MAX_CHARS }}
          </span>
          <button
            type="button"
            class="feedback-buttons__submit-btn"
            :disabled="!hasValidCorrection"
            @click="handleReject"
          >
            送信
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* --- Slide-in transition (300ms) --- */
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
  max-height: 400px;
  opacity: 1;
}

/* --- Container --- */
.feedback-buttons {
  margin-top: 0.75rem;
}

.feedback-buttons__actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* --- Button base --- */
.feedback-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.875rem;
  font-size: 0.85rem;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  background: var(--color-surface, #ffffff);
  color: var(--color-foreground, #1a202c);
  cursor: pointer;
  transition: background-color 200ms, border-color 200ms, box-shadow 200ms;
}

.feedback-btn:hover {
  background: var(--color-surface-hover, #f7fafc);
  border-color: var(--color-muted-foreground, #a0aec0);
}

.feedback-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.feedback-btn--active {
  border-color: #6c63ff;
  background: var(--color-primary-light, #eff6ff);
}

.feedback-btn__icon {
  font-size: 1rem;
  line-height: 1;
}

.feedback-btn__label {
  font-weight: 500;
}

/* --- Correction area --- */
.feedback-buttons__correction {
  margin-top: 0.75rem;
}

.feedback-buttons__correction-label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-muted-foreground, #718096);
  margin-bottom: 0.5rem;
}

.feedback-buttons__textarea {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 0.95rem;
  line-height: 1.5;
  border: 2px solid var(--color-border, #e2e8f0);
  border-radius: 8px;
  background: var(--color-surface, #ffffff);
  color: var(--color-foreground, #1a202c);
  resize: vertical;
  transition: border-color 200ms;
  box-sizing: border-box;
}

.feedback-buttons__textarea:focus {
  border-color: #6c63ff;
  outline: none;
}

.feedback-buttons__textarea-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.375rem;
}

.feedback-buttons__char-count {
  font-size: 0.8rem;
  color: var(--color-muted-foreground, #718096);
}

.feedback-buttons__char-count--limit {
  color: #e53935;
  font-weight: 600;
}

.feedback-buttons__submit-btn {
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
  font-weight: 600;
  border: none;
  border-radius: 6px;
  background: #6c63ff;
  color: #fff;
  cursor: pointer;
  transition: background-color 200ms, opacity 200ms;
}

.feedback-buttons__submit-btn:hover:not(:disabled) {
  background: #5a52d5;
}

.feedback-buttons__submit-btn:focus-visible {
  outline: 3px solid #6c63ff;
  outline-offset: 2px;
}

.feedback-buttons__submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* --- Responsive --- */
@media (max-width: 600px) {
  .feedback-buttons__actions {
    flex-direction: column;
  }

  .feedback-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
