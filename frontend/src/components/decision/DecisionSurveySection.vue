<script setup lang="ts">
/**
 * Decision Engine カテゴリのサーベイ統合コンポーネント
 * format に応じて適切な UI コンポーネントを切り替える
 * Requirements: 12.5, 1.2, 2.2, 3.2, 4.2, 5.5, 17.1, 17.7
 */
import { ref, computed } from 'vue'
import BinaryChoice from './BinaryChoice.vue'
import OrderingDnD from './OrderingDnD.vue'
import MetadataPanel from './MetadataPanel.vue'
import type { AnswerMetadata, OrderingChoice } from '@/types/decision'

interface Choice {
  id: string
  label: string
}

interface Question {
  id: string
  text: string
  category_id: string
  format?: 'single_select' | 'binary_choice' | 'ordering'
  choices?: Choice[]
  steps?: OrderingChoice[]
}

const props = defineProps<{
  question: Question
  sessionId: string
}>()

const emit = defineEmits<{
  answered: [questionId: string, answer: { choice_id?: string; ordered_ids?: string[]; metadata?: AnswerMetadata }]
}>()

// 回答状態
const selectedChoice = ref<string | null>(null)
const orderedIds = ref<string[]>([])
const metadata = ref<AnswerMetadata>({
  permanence: 'permanent',
  confidence: 0.6,
  exception_note: null,
  is_core_rule: false,
  ambiguity: 0.0,
})

// format 判定
const format = computed(() => props.question.format || 'single_select')
const isBinaryChoice = computed(() => format.value === 'binary_choice')
const isOrdering = computed(() => format.value === 'ordering')
const isSingleSelect = computed(() => format.value === 'single_select')

// Binary choice 用
const binaryChoices = computed(() => {
  if (!props.question.choices || props.question.choices.length !== 2) return null
  return props.question.choices as [Choice, Choice]
})

// 回答確定
function confirmAnswer() {
  if (isBinaryChoice.value && selectedChoice.value) {
    emit('answered', props.question.id, {
      choice_id: selectedChoice.value,
      metadata: metadata.value,
    })
  } else if (isOrdering.value && orderedIds.value.length > 0) {
    emit('answered', props.question.id, {
      ordered_ids: orderedIds.value,
      metadata: metadata.value,
    })
  } else if (isSingleSelect.value && selectedChoice.value) {
    emit('answered', props.question.id, {
      choice_id: selectedChoice.value,
      metadata: metadata.value,
    })
  }
}

function handleSingleSelect(choiceId: string) {
  selectedChoice.value = choiceId
}
</script>

<template>
  <div class="decision-survey-section">
    <h3 class="question-text">{{ question.text }}</h3>

    <!-- Binary Choice (tradeoff) -->
    <BinaryChoice
      v-if="isBinaryChoice && binaryChoices"
      :question-id="question.id"
      :choices="binaryChoices"
      v-model="selectedChoice"
    />

    <!-- Ordering (drag and drop) -->
    <OrderingDnD
      v-else-if="isOrdering && question.steps"
      :question-id="question.id"
      :steps="question.steps"
      v-model="orderedIds"
    />

    <!-- Single Select (standard 4-choice) -->
    <div v-else-if="isSingleSelect && question.choices" class="single-select-group" role="radiogroup">
      <button
        v-for="choice in question.choices"
        :key="choice.id"
        class="single-choice-btn"
        :class="{ selected: selectedChoice === choice.id }"
        role="radio"
        :aria-checked="selectedChoice === choice.id"
        @click="handleSingleSelect(choice.id)"
      >
        {{ choice.label }}
      </button>
    </div>

    <!-- Metadata Panel (all question types) -->
    <MetadataPanel v-model="metadata" />

    <!-- Confirm button -->
    <button
      class="confirm-btn"
      :disabled="!selectedChoice && orderedIds.length === 0"
      @click="confirmAnswer"
    >
      次へ
    </button>
  </div>
</template>

<style scoped>
.decision-survey-section {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

.question-text {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.single-select-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.single-choice-btn {
  width: 100%;
  padding: 1rem 1.25rem;
  border: 2px solid var(--color-border, #e2e8f0);
  border-radius: 0.75rem;
  background: var(--color-bg-card, #ffffff);
  cursor: pointer;
  text-align: left;
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.single-choice-btn:hover {
  border-color: var(--color-primary, #3b82f6);
}

.single-choice-btn.selected {
  border-color: var(--color-primary, #3b82f6);
  background: var(--color-primary-light, #eff6ff);
}

.confirm-btn {
  display: block;
  width: 100%;
  margin-top: 1.5rem;
  padding: 0.875rem;
  border: none;
  border-radius: 0.75rem;
  background: var(--color-primary, #3b82f6);
  color: #ffffff;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.confirm-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.confirm-btn:hover:not(:disabled) {
  opacity: 0.9;
}
</style>
