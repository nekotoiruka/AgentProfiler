<script setup lang="ts">
/**
 * SurveyView ページ
 * セッション開始 → 質問ロード → 順次回答 → 結果表示への遷移を管理
 * Requirements: 1.1, 1.2, 1.5, 1.6, 1.7, 2.4, 2.5, 10.2
 */
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useSessionStore } from '@/stores/session';
import { useSurveyStore } from '@/stores/survey';
import QuestionCard from '@/components/QuestionCard.vue';
import MultiSelectCard from '@/components/MultiSelectCard.vue';
import ProgressBar from '@/components/ProgressBar.vue';
import type { AnswerSubmission } from '@/types';

const router = useRouter();
const sessionStore = useSessionStore();
const surveyStore = useSurveyStore();

// --- Local State ---

/** アニメーション方向 */
const direction = ref<'forward' | 'backward'>('forward');

/** 現在選択中の選択肢ID（'__other__' は Other 選択を示す） */
const selectedChoiceId = ref<string | null>(null);

/** Other テキストエリアの入力値 */
const otherText = ref('');

/** multi_select 型の選択済みオプションID */
const selectedOptions = ref<string[]>([]);

/** 初期化完了フラグ */
const isInitialized = ref(false);

/** 初期化エラーメッセージ */
const initError = ref<string | null>(null);

// --- Computed ---

/** ローディング中かどうか（セッション or サーベイ） */
const isLoading = computed(() =>
  sessionStore.isLoading || surveyStore.isLoading,
);

/** 現在のカテゴリ名 */
const categoryName = computed(() =>
  surveyStore.currentCategory?.name ?? '',
);

/** 現在の質問がmulti_select型か */
const isMultiSelect = computed(() =>
  surveyStore.currentQuestion?.question_type === 'multi_select',
);

// --- Lifecycle ---

onMounted(async () => {
  try {
    await sessionStore.createSession();
    await surveyStore.loadQuestions();

    // セッション復帰: 未回答の最初の質問から再開
    resumeFromUnanswered();

    isInitialized.value = true;
  } catch (e) {
    initError.value = e instanceof Error ? e.message : String(e);
  }
});

// --- Functions ---

/**
 * 未回答の最初の質問位置まで進める（セッション復帰用）
 * 既に回答済みの質問をスキップして、最初の未回答質問を表示する
 */
function resumeFromUnanswered(): void {
  for (let ci = 0; ci < surveyStore.categories.length; ci++) {
    const cat = surveyStore.categories[ci];
    for (let qi = 0; qi < cat.questions.length; qi++) {
      if (!surveyStore.answers.has(cat.questions[qi].id)) {
        surveyStore.currentCategoryIndex = ci;
        surveyStore.currentQuestionIndex = qi;
        restoreAnswer();
        return;
      }
    }
  }
  // 全質問回答済みの場合 → 最初の質問に戻す（通常はここには到達しない）
  restoreAnswer();
}

/**
 * 現在の質問に対する既存回答をローカルステートに復元する
 */
function restoreAnswer(): void {
  const question = surveyStore.currentQuestion;
  if (!question) {
    selectedChoiceId.value = null;
    otherText.value = '';
    selectedOptions.value = [];
    return;
  }

  const existing = surveyStore.answers.get(question.id);
  if (existing) {
    if (existing.selected_options) {
      // multi_select 回答
      selectedOptions.value = [...existing.selected_options];
      selectedChoiceId.value = null;
      otherText.value = '';
    } else if (existing.text) {
      // Other 回答
      selectedChoiceId.value = '__other__';
      otherText.value = existing.text;
      selectedOptions.value = [];
    } else {
      selectedChoiceId.value = existing.choice_id ?? null;
      otherText.value = '';
      selectedOptions.value = [];
    }
  } else {
    selectedChoiceId.value = null;
    otherText.value = '';
    selectedOptions.value = [];
  }
}

/**
 * 選択肢が選ばれた時のハンドラ
 * Other から通常選択肢に切り替えた場合は otherText をクリア
 */
function handleSelectChoice(choiceId: string): void {
  selectedChoiceId.value = choiceId;
  otherText.value = '';
}

/** Other が選ばれた時のハンドラ */
function handleSelectOther(): void {
  selectedChoiceId.value = '__other__';
}

/** Other テキスト更新ハンドラ */
function handleUpdateOtherText(text: string): void {
  otherText.value = text;
}

/**
 * multi_select: オプションのトグル
 */
function handleToggleOption(optionId: string): void {
  const idx = selectedOptions.value.indexOf(optionId);
  if (idx >= 0) {
    selectedOptions.value.splice(idx, 1);
  } else {
    selectedOptions.value.push(optionId);
  }
}

/**
 * 次へ進む: 回答をストアに保存 → API送信 → 次の質問 or 結果ページへ
 */
async function handleNext(): Promise<void> {
  const question = surveyStore.currentQuestion;
  if (!question) return;

  // AnswerSubmission を構築
  const submission: AnswerSubmission = {
    question_id: question.id,
  };

  if (question.question_type === 'multi_select') {
    submission.selected_options = [...selectedOptions.value];
  } else if (selectedChoiceId.value === '__other__') {
    submission.text = otherText.value;
  } else if (selectedChoiceId.value) {
    submission.choice_id = selectedChoiceId.value;
  }

  // ローカルストアに保存
  surveyStore.setAnswer(question.id, submission);

  // APIに送信
  try {
    await sessionStore.submitAnswer(submission);
  } catch {
    // エラーはsessionStoreのerror stateで表示される
    return;
  }

  // 最後の質問の場合 → プロファイル計算して結果ページへ
  if (surveyStore.isLastQuestion) {
    try {
      await sessionStore.calculateProfile();
      router.push('/results');
    } catch {
      // エラーはsessionStoreのerror stateで表示される
    }
    return;
  }

  // 次の質問へ遷移
  direction.value = 'forward';
  surveyStore.nextQuestion();
  restoreAnswer();
}

/**
 * 戻る: 前の質問へ遷移し、保存済み回答を復元
 */
function handleBack(): void {
  direction.value = 'backward';
  surveyStore.previousQuestion();
  restoreAnswer();
}
</script>

<template>
  <div class="survey-view">
    <!-- ローディング状態 -->
    <div v-if="!isInitialized && !initError" class="survey-view__loading">
      <div class="survey-view__spinner" aria-label="読み込み中" />
      <p>質問を読み込んでいます...</p>
    </div>

    <!-- エラー状態 -->
    <div v-else-if="initError" class="survey-view__error" role="alert">
      <p class="survey-view__error-message">{{ initError }}</p>
      <button class="survey-view__retry-button" @click="initError = null; isInitialized = false; $router.go(0)">
        再試行
      </button>
    </div>

    <!-- メインコンテンツ -->
    <template v-else-if="surveyStore.currentQuestion">
      <ProgressBar
        :category-name="categoryName"
        :category-progress="surveyStore.categoryProgress"
        :overall-progress="surveyStore.overallProgress"
      />

      <!-- multi_select 型: チェックボックスカード -->
      <MultiSelectCard
        v-if="isMultiSelect"
        :key="surveyStore.currentQuestion.id"
        :question="surveyStore.currentQuestion"
        :selected-options="selectedOptions"
        :direction="direction"
        @toggle-option="handleToggleOption"
        @next="handleNext"
        @back="handleBack"
      />

      <!-- single_choice 型: 通常の質問カード -->
      <QuestionCard
        v-else
        :key="surveyStore.currentQuestion.id"
        :question="surveyStore.currentQuestion"
        :selected-choice-id="selectedChoiceId"
        :other-text="otherText"
        :direction="direction"
        @select-choice="handleSelectChoice"
        @select-other="handleSelectOther"
        @update-other-text="handleUpdateOtherText"
        @next="handleNext"
        @back="handleBack"
      />

      <!-- API通信エラー表示 -->
      <div
        v-if="sessionStore.error"
        class="survey-view__api-error"
        role="alert"
      >
        <p>{{ sessionStore.error }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.survey-view {
  max-width: 640px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
}

.survey-view__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  gap: 1rem;
}

.survey-view__spinner {
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

.survey-view__error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  gap: 1rem;
}

.survey-view__error-message {
  color: #dc2626;
  font-weight: 500;
}

.survey-view__retry-button {
  padding: 0.5rem 1.5rem;
  background-color: #3b82f6;
  color: white;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.survey-view__retry-button:hover {
  background-color: #2563eb;
}

.survey-view__api-error {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 0.375rem;
  color: #dc2626;
  font-size: 0.875rem;
}
</style>
