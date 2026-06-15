<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { OrderingChoice } from '@/types/decision'

const props = defineProps<{
  questionId: string
  steps: OrderingChoice[]
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

// モバイル判定（< 768px）
const isMobile = ref(false)
let mediaQuery: MediaQueryList | null = null

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 767px)')
  isMobile.value = mediaQuery.matches
  mediaQuery.addEventListener('change', handleMediaChange)

  // modelValue が空の場合、Fisher-Yates シャッフルで初期化
  if (props.modelValue.length === 0 && props.steps.length > 0) {
    const shuffled = fisherYatesShuffle(props.steps.map(s => s.id))
    emit('update:modelValue', shuffled)
  }
})

function handleMediaChange(e: MediaQueryListEvent) {
  isMobile.value = e.matches
}

/**
 * Fisher-Yates シャッフルアルゴリズム
 * 位置バイアスを排除するために初期順序をランダム化する
 */
function fisherYatesShuffle(arr: string[]): string[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

// 現在の表示順序に基づくステップ一覧
const orderedSteps = computed(() => {
  if (props.modelValue.length === 0) return props.steps
  return props.modelValue
    .map(id => props.steps.find(s => s.id === id))
    .filter((s): s is OrderingChoice => s !== undefined)
})

// --- Desktop: Drag and Drop ---
const draggedIndex = ref<number | null>(null)
const dropTargetIndex = ref<number | null>(null)

function onDragStart(index: number, event: DragEvent) {
  draggedIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function onDragOver(index: number, event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
  dropTargetIndex.value = index
}

function onDragLeave() {
  dropTargetIndex.value = null
}

function onDrop(index: number, event: DragEvent) {
  event.preventDefault()
  dropTargetIndex.value = null

  if (draggedIndex.value === null || draggedIndex.value === index) {
    draggedIndex.value = null
    return
  }

  const newOrder = [...props.modelValue]
  const [moved] = newOrder.splice(draggedIndex.value, 1)
  newOrder.splice(index, 0, moved)
  emit('update:modelValue', newOrder)
  draggedIndex.value = null
}

function onDragEnd() {
  draggedIndex.value = null
  dropTargetIndex.value = null
}

// --- Mobile: ナンバー入力フォールバック ---
const mobileRanks = ref<Record<string, number>>({})

// modelValue 変更時にモバイル用ランクを同期
watch(() => props.modelValue, (val) => {
  if (val.length > 0) {
    const ranks: Record<string, number> = {}
    val.forEach((id, idx) => {
      ranks[id] = idx + 1
    })
    mobileRanks.value = ranks
  }
}, { immediate: true })

// 重複バリデーション
const duplicateError = computed(() => {
  const values = Object.values(mobileRanks.value)
  const seen = new Set<number>()
  for (const v of values) {
    if (v < 1 || v > props.steps.length) continue
    if (seen.has(v)) return true
    seen.add(v)
  }
  return false
})

function onRankChange(stepId: string, value: string) {
  const num = parseInt(value, 10)
  if (isNaN(num) || num < 1 || num > props.steps.length) return
  mobileRanks.value = { ...mobileRanks.value, [stepId]: num }

  // 重複がなければ順序を emit
  const entries = Object.entries(mobileRanks.value)
  const values = entries.map(([, v]) => v)
  const uniqueValues = new Set(values)
  if (uniqueValues.size === props.steps.length && values.every(v => v >= 1 && v <= props.steps.length)) {
    const sorted = entries.sort((a, b) => a[1] - b[1])
    emit('update:modelValue', sorted.map(([id]) => id))
  }
}
</script>

<template>
  <div
    class="ordering-dnd"
    :aria-labelledby="`question-${questionId}`"
    role="list"
    :aria-description="isMobile ? 'ランクを数字で入力してください' : 'ドラッグ&ドロップで順序を変更してください'"
  >
    <!-- Desktop: Drag and Drop -->
    <TransitionGroup v-if="!isMobile" name="ordering" tag="div" class="ordering-list">
      <div
        v-for="(step, index) in orderedSteps"
        :key="step.id"
        class="ordering-item"
        :class="{
          dragging: draggedIndex === index,
          'drop-target': dropTargetIndex === index && draggedIndex !== index,
        }"
        role="listitem"
        :aria-label="`${index + 1}番目: ${step.label}`"
        draggable="true"
        @dragstart="onDragStart(index, $event)"
        @dragover="onDragOver(index, $event)"
        @dragleave="onDragLeave"
        @drop="onDrop(index, $event)"
        @dragend="onDragEnd"
      >
        <span class="drag-handle" aria-hidden="true">⠿</span>
        <span class="ordering-rank">{{ index + 1 }}</span>
        <span class="ordering-label">{{ step.label }}</span>
      </div>
    </TransitionGroup>

    <!-- Mobile: ナンバー入力フォールバック -->
    <div v-else class="ordering-mobile">
      <div
        v-for="step in steps"
        :key="step.id"
        class="ordering-mobile-item"
        role="listitem"
        :aria-label="step.label"
      >
        <label :for="`rank-${questionId}-${step.id}`" class="sr-only">
          {{ step.label }} の順位
        </label>
        <input
          :id="`rank-${questionId}-${step.id}`"
          type="number"
          class="rank-input"
          :min="1"
          :max="steps.length"
          :value="mobileRanks[step.id] ?? ''"
          :aria-invalid="duplicateError"
          @input="onRankChange(step.id, ($event.target as HTMLInputElement).value)"
        />
        <span class="ordering-label">{{ step.label }}</span>
      </div>
      <p v-if="duplicateError" class="error-message" role="alert">
        順位が重複しています。各ステップに異なる番号を入力してください。
      </p>
    </div>
  </div>
</template>

<style scoped>
.ordering-dnd {
  width: 100%;
}

.ordering-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ordering-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border: 2px solid var(--color-border, #e2e8f0);
  border-radius: 0.75rem;
  background: var(--color-bg-card, #ffffff);
  cursor: grab;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  user-select: none;
}

.ordering-item:hover {
  border-color: var(--color-primary, #3b82f6);
}

.ordering-item.dragging {
  opacity: 0.5;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
  cursor: grabbing;
}

.ordering-item.drop-target {
  border-color: var(--color-primary, #3b82f6);
  border-top: 3px solid var(--color-primary, #3b82f6);
}

.drag-handle {
  color: var(--color-text-muted, #94a3b8);
  font-size: 1.25rem;
  cursor: grab;
}

.ordering-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  background: var(--color-primary, #3b82f6);
  color: #ffffff;
  font-size: 0.85rem;
  font-weight: 600;
  flex-shrink: 0;
}

.ordering-label {
  font-size: 0.95rem;
  line-height: 1.5;
  font-weight: 500;
}

/* TransitionGroup アニメーション (200ms) */
.ordering-move {
  transition: transform 0.2s ease;
}

.ordering-enter-active,
.ordering-leave-active {
  transition: all 0.2s ease;
}

.ordering-enter-from,
.ordering-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* Mobile スタイル */
.ordering-mobile {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.ordering-mobile-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 2px solid var(--color-border, #e2e8f0);
  border-radius: 0.75rem;
  background: var(--color-bg-card, #ffffff);
}

.rank-input {
  width: 3rem;
  height: 2.25rem;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 0.5rem;
  text-align: center;
  font-size: 1rem;
  font-weight: 600;
  flex-shrink: 0;
}

.rank-input:focus {
  outline: 2px solid var(--color-primary, #3b82f6);
  outline-offset: 1px;
}

.rank-input[aria-invalid="true"] {
  border-color: var(--color-error, #ef4444);
}

.error-message {
  color: var(--color-error, #ef4444);
  font-size: 0.85rem;
  margin-top: 0.25rem;
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
