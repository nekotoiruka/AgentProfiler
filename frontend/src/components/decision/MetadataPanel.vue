<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { AnswerMetadata } from '@/types/decision'

const props = defineProps<{
  modelValue: AnswerMetadata
}>()

const emit = defineEmits<{
  'update:modelValue': [value: AnswerMetadata]
}>()

// パネル展開状態（デフォルト: 折りたたみ）
const isExpanded = ref(false)

// 確信度スライダー値（★1〜5）
const confidenceStars = computed(() => {
  // 0.2〜1.0 を 1〜5 に逆変換
  return Math.round(props.modelValue.confidence * 5)
})

// 確信度マッピング: ★1→0.2, ★2→0.4, ★3→0.6, ★4→0.8, ★5→1.0
const CONFIDENCE_MAP: Record<number, number> = {
  1: 0.2,
  2: 0.4,
  3: 0.6,
  4: 0.8,
  5: 1.0,
}

// exception_note 文字数カウンター
const noteLength = computed(() => props.modelValue.exception_note?.length ?? 0)
const NOTE_MAX_LENGTH = 200

function togglePanel() {
  isExpanded.value = !isExpanded.value
}

function updatePermanence(value: 'permanent' | 'contextual') {
  emit('update:modelValue', { ...props.modelValue, permanence: value })
}

function updateConfidence(stars: number) {
  const confidence = CONFIDENCE_MAP[stars] ?? 0.6
  emit('update:modelValue', { ...props.modelValue, confidence })
}

function updateExceptionNote(text: string) {
  // 200文字制限を強制
  const trimmed = text.slice(0, NOTE_MAX_LENGTH)
  const note = trimmed.length === 0 ? null : trimmed
  emit('update:modelValue', { ...props.modelValue, exception_note: note })
}
</script>

<template>
  <div class="metadata-panel" :class="{ expanded: isExpanded }">
    <button
      class="panel-toggle"
      type="button"
      :aria-expanded="isExpanded"
      aria-controls="metadata-content"
      @click="togglePanel"
    >
      <span class="toggle-icon" aria-hidden="true">{{ isExpanded ? '▾' : '▸' }}</span>
      <span class="toggle-label">回答メタデータ</span>
      <span class="toggle-hint" aria-hidden="true">(任意)</span>
    </button>

    <div
      v-show="isExpanded"
      id="metadata-content"
      class="panel-content"
      role="region"
      aria-label="回答メタデータ設定"
    >
      <!-- Permanence トグル -->
      <fieldset class="field-group">
        <legend class="field-legend">恒常性</legend>
        <div class="permanence-toggle" role="radiogroup" aria-label="恒常性">
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: modelValue.permanence === 'permanent' }"
            role="radio"
            :aria-checked="modelValue.permanence === 'permanent'"
            @click="updatePermanence('permanent')"
          >
            常にそう
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: modelValue.permanence === 'contextual' }"
            role="radio"
            :aria-checked="modelValue.permanence === 'contextual'"
            @click="updatePermanence('contextual')"
          >
            場合による
          </button>
        </div>
      </fieldset>

      <!-- Confidence スライダー ★1〜5 -->
      <fieldset class="field-group">
        <legend class="field-legend">
          確信度
          <span class="confidence-display" aria-hidden="true">
            {{ '★'.repeat(confidenceStars) }}{{ '☆'.repeat(5 - confidenceStars) }}
          </span>
        </legend>
        <label :for="'confidence-slider'" class="sr-only">
          確信度（1〜5）
        </label>
        <input
          id="confidence-slider"
          type="range"
          class="confidence-slider"
          :min="1"
          :max="5"
          :step="1"
          :value="confidenceStars"
          :aria-valuenow="confidenceStars"
          aria-valuemin="1"
          aria-valuemax="5"
          :aria-valuetext="`★${confidenceStars}`"
          @input="updateConfidence(Number(($event.target as HTMLInputElement).value))"
        />
        <div class="slider-labels" aria-hidden="true">
          <span>低い</span>
          <span>高い</span>
        </div>
      </fieldset>

      <!-- Exception Note テキストエリア -->
      <fieldset class="field-group">
        <legend class="field-legend">例外条件</legend>
        <textarea
          class="exception-textarea"
          :value="modelValue.exception_note ?? ''"
          :maxlength="NOTE_MAX_LENGTH"
          placeholder="例外がある場合を記述"
          rows="3"
          aria-label="例外条件（最大200文字）"
          @input="updateExceptionNote(($event.target as HTMLTextAreaElement).value)"
        />
        <div class="char-counter" :class="{ 'near-limit': noteLength >= 180 }">
          {{ noteLength }} / {{ NOTE_MAX_LENGTH }}
        </div>
      </fieldset>
    </div>
  </div>
</template>

<style scoped>
.metadata-panel {
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 0.75rem;
  background: var(--color-bg-card, #ffffff);
  margin-top: 1rem;
  overflow: hidden;
}

.panel-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.75rem 1rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--color-text-muted, #64748b);
  transition: color 0.2s ease;
}

.panel-toggle:hover {
  color: var(--color-text, #1e293b);
}

.toggle-icon {
  font-size: 0.75rem;
  width: 1rem;
  text-align: center;
}

.toggle-label {
  font-weight: 500;
}

.toggle-hint {
  font-size: 0.8rem;
  opacity: 0.7;
}

.panel-content {
  padding: 0 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field-group {
  border: none;
  padding: 0;
  margin: 0;
}

.field-legend {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text, #1e293b);
  margin-bottom: 0.5rem;
}

/* Permanence トグル */
.permanence-toggle {
  display: flex;
  gap: 0;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 0.5rem;
  overflow: hidden;
}

.toggle-btn {
  flex: 1;
  padding: 0.5rem 1rem;
  border: none;
  background: var(--color-bg-card, #ffffff);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text-muted, #64748b);
  transition: all 0.2s ease;
}

.toggle-btn:not(:last-child) {
  border-right: 1px solid var(--color-border, #e2e8f0);
}

.toggle-btn.active {
  background: var(--color-primary, #3b82f6);
  color: #ffffff;
}

.toggle-btn:hover:not(.active) {
  background: var(--color-bg-hover, #f8fafc);
}

/* Confidence スライダー */
.confidence-display {
  font-size: 0.9rem;
  color: var(--color-warning, #f59e0b);
}

.confidence-slider {
  width: 100%;
  height: 0.5rem;
  appearance: none;
  -webkit-appearance: none;
  background: var(--color-border, #e2e8f0);
  border-radius: 0.25rem;
  outline: none;
  cursor: pointer;
}

.confidence-slider::-webkit-slider-thumb {
  appearance: none;
  -webkit-appearance: none;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: var(--color-primary, #3b82f6);
  cursor: pointer;
  border: 2px solid #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.confidence-slider::-moz-range-thumb {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: var(--color-primary, #3b82f6);
  cursor: pointer;
  border: 2px solid #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.confidence-slider:focus {
  outline: 2px solid var(--color-primary, #3b82f6);
  outline-offset: 2px;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--color-text-muted, #94a3b8);
  margin-top: 0.25rem;
}

/* Exception Note テキストエリア */
.exception-textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 0.5rem;
  font-size: 0.9rem;
  line-height: 1.5;
  resize: vertical;
  min-height: 4rem;
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.exception-textarea:focus {
  outline: none;
  border-color: var(--color-primary, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.exception-textarea::placeholder {
  color: var(--color-text-muted, #94a3b8);
}

.char-counter {
  text-align: right;
  font-size: 0.75rem;
  color: var(--color-text-muted, #94a3b8);
  margin-top: 0.25rem;
}

.char-counter.near-limit {
  color: var(--color-warning, #f59e0b);
}

/* Screen reader only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
