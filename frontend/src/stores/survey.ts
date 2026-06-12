/**
 * サーベイ管理 Pinia ストア
 * Requirements: 10.1, 10.2, 11.3 - 質問データ、進捗計算、現在の質問管理
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiFetch } from '@/composables/useApi';
import type {
  Category,
  Question,
  AnswerSubmission,
  QuestionsResponse,
} from '@/types';

export const useSurveyStore = defineStore('survey', () => {
  // --- State ---
  const categories = ref<Category[]>([]);
  const currentCategoryIndex = ref(0);
  const currentQuestionIndex = ref(0);
  const answers = ref<Map<string, AnswerSubmission>>(new Map());
  const isLoading = ref(false);

  // --- Getters ---

  /** 現在のカテゴリ */
  const currentCategory = computed<Category | null>(() => {
    return categories.value[currentCategoryIndex.value] ?? null;
  });

  /** 現在の質問 */
  const currentQuestion = computed<Question | null>(() => {
    const cat = currentCategory.value;
    if (!cat) return null;
    return cat.questions[currentQuestionIndex.value] ?? null;
  });

  /** カテゴリ内進捗（0〜100整数） */
  const categoryProgress = computed<number>(() => {
    const cat = currentCategory.value;
    if (!cat || cat.questions.length === 0) return 0;
    const answeredInCategory = cat.questions.filter((q) =>
      answers.value.has(q.id),
    ).length;
    return Math.floor((answeredInCategory / cat.questions.length) * 100);
  });

  /** 全質問数 */
  const totalQuestions = computed<number>(() => {
    return categories.value.reduce(
      (sum, cat) => sum + cat.questions.length,
      0,
    );
  });

  /** 回答済み質問数 */
  const answeredQuestions = computed<number>(() => {
    return answers.value.size;
  });

  /** 全体進捗（0〜100整数） */
  const overallProgress = computed<number>(() => {
    const total = totalQuestions.value;
    if (total === 0) return 0;
    return Math.floor((answeredQuestions.value / total) * 100);
  });

  /** 最後の質問かどうか */
  const isLastQuestion = computed<boolean>(() => {
    if (categories.value.length === 0) return false;
    const lastCat = categories.value[categories.value.length - 1];
    return (
      currentCategoryIndex.value === categories.value.length - 1 &&
      currentQuestionIndex.value === lastCat.questions.length - 1
    );
  });

  /** 前に戻れるかどうか */
  const canGoBack = computed<boolean>(() => {
    return currentCategoryIndex.value > 0 || currentQuestionIndex.value > 0;
  });

  // --- Actions ---

  /** 質問データ取得: GET /questions */
  async function loadQuestions(): Promise<void> {
    isLoading.value = true;
    try {
      const data = await apiFetch<QuestionsResponse>('/questions');
      categories.value = data.categories;
    } finally {
      isLoading.value = false;
    }
  }

  /** 回答をローカルに保存 */
  function setAnswer(questionId: string, answer: AnswerSubmission): void {
    answers.value.set(questionId, answer);
  }

  /** 次の質問へ進む（カテゴリ境界を跨ぐ処理を含む） */
  function nextQuestion(): boolean {
    const cat = currentCategory.value;
    if (!cat) return false;

    // 現在のカテゴリ内に次の質問がある場合
    if (currentQuestionIndex.value < cat.questions.length - 1) {
      currentQuestionIndex.value++;
      return true;
    }

    // 次のカテゴリがある場合
    if (currentCategoryIndex.value < categories.value.length - 1) {
      currentCategoryIndex.value++;
      currentQuestionIndex.value = 0;
      return true;
    }

    // 全質問完了
    return false;
  }

  /** 前の質問に戻る */
  function previousQuestion(): boolean {
    // 現在のカテゴリ内で前に戻れる場合
    if (currentQuestionIndex.value > 0) {
      currentQuestionIndex.value--;
      return true;
    }

    // 前のカテゴリがある場合、そのカテゴリの最後の質問へ
    if (currentCategoryIndex.value > 0) {
      currentCategoryIndex.value--;
      const prevCat = categories.value[currentCategoryIndex.value];
      currentQuestionIndex.value = prevCat.questions.length - 1;
      return true;
    }

    // 最初の質問にいるため戻れない
    return false;
  }

  /** ストアをリセット */
  function $reset(): void {
    categories.value = [];
    currentCategoryIndex.value = 0;
    currentQuestionIndex.value = 0;
    answers.value = new Map();
    isLoading.value = false;
  }

  return {
    // State
    categories,
    currentCategoryIndex,
    currentQuestionIndex,
    answers,
    isLoading,
    // Getters
    currentCategory,
    currentQuestion,
    categoryProgress,
    overallProgress,
    totalQuestions,
    answeredQuestions,
    isLastQuestion,
    canGoBack,
    // Actions
    loadQuestions,
    setAnswer,
    nextQuestion,
    previousQuestion,
    $reset,
  };
});
