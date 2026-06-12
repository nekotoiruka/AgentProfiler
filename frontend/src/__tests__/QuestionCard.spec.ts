import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import QuestionCard from '@/components/QuestionCard.vue';
import type { Question } from '@/types/question';

/**
 * QuestionCard コンポーネントテスト
 * Validates: Requirements 1.2, 2.1, 2.2, 2.3, 2.6
 */

// --- テスト用ヘルパー ---

const mockQuestion: Question = {
  id: 'bos_001',
  text: 'プロジェクトが危機的状況に陥った時、最初に取る行動は？',
  category_id: 'business_os',
  question_type: 'single_choice',
  source_reference: 'OEJTS_E/I_adapted',
  choices: [
    { id: 'a', label: 'チーム全員を集めて即座にブレインストーミングを開始する' },
    { id: 'b', label: '一人で状況を整理し、解決策を練ってから共有する' },
    { id: 'c', label: 'データを集めて根本原因を特定してから対策を立てる' },
    { id: 'd', label: '過去の類似事例を参照し、実績ある手法を適用する' },
  ],
  options: [],
  min_select: 0,
  max_select: 0,
};

function createWrapper(overrides: Partial<{
  selectedChoiceId: string | null;
  otherText: string;
  direction: 'forward' | 'backward';
}> = {}) {
  return mount(QuestionCard, {
    props: {
      question: mockQuestion,
      selectedChoiceId: overrides.selectedChoiceId ?? null,
      otherText: overrides.otherText ?? '',
      direction: overrides.direction ?? 'forward',
    },
    global: {
      stubs: {
        Transition: false,
      },
    },
  });
}

describe('QuestionCard', () => {
  // --- 質問表示 ---
  it('renders question text', () => {
    const wrapper = createWrapper();
    expect(wrapper.find('.question-card__text').text()).toBe(mockQuestion.text);
  });

  it('renders all 4 choices + Other button', () => {
    const wrapper = createWrapper();
    const buttons = wrapper.findAll('.question-card__choice-btn');
    // 4 choices + 1 Other = 5 buttons
    expect(buttons).toHaveLength(5);
    expect(buttons[4].text()).toBe('Other');
  });

  // --- 選択肢イベント ---
  it("emits 'select-choice' when choice button clicked", async () => {
    const wrapper = createWrapper();
    const choiceButtons = wrapper.findAll('.question-card__choice-btn');
    await choiceButtons[0].trigger('click');
    expect(wrapper.emitted('select-choice')).toBeTruthy();
    expect(wrapper.emitted('select-choice')![0]).toEqual(['a']);
  });

  it("emits 'select-other' when Other button clicked", async () => {
    const wrapper = createWrapper();
    const otherBtn = wrapper.find('.question-card__choice-btn--other');
    await otherBtn.trigger('click');
    expect(wrapper.emitted('select-other')).toBeTruthy();
  });

  // --- Other textarea 表示/非表示 ---
  it("shows textarea when selectedChoiceId is '__other__'", () => {
    const wrapper = createWrapper({ selectedChoiceId: '__other__' });
    expect(wrapper.find('.question-card__other-area').exists()).toBe(true);
    expect(wrapper.find('textarea').exists()).toBe(true);
  });

  it("hides textarea when selectedChoiceId is not '__other__'", () => {
    const wrapper = createWrapper({ selectedChoiceId: 'a' });
    expect(wrapper.find('.question-card__other-area').exists()).toBe(false);
  });

  // --- Other テキスト入力 ---
  it("emits 'update-other-text' on textarea input", async () => {
    const wrapper = createWrapper({ selectedChoiceId: '__other__' });
    const textarea = wrapper.find('textarea');
    // input イベントをシミュレート
    const el = textarea.element as HTMLTextAreaElement;
    el.value = 'テスト入力';
    await textarea.trigger('input');
    expect(wrapper.emitted('update-other-text')).toBeTruthy();
    expect(wrapper.emitted('update-other-text')![0]).toEqual(['テスト入力']);
  });

  it('truncates text at 500 characters', async () => {
    const wrapper = createWrapper({ selectedChoiceId: '__other__' });
    const textarea = wrapper.find('textarea');
    const longText = 'あ'.repeat(600);
    const el = textarea.element as HTMLTextAreaElement;
    el.value = longText;
    await textarea.trigger('input');
    // handleOtherInput で slice(0, 500) が適用される
    const emitted = wrapper.emitted('update-other-text')![0][0] as string;
    expect(emitted.length).toBe(500);
  });

  it('shows character count', () => {
    const wrapper = createWrapper({
      selectedChoiceId: '__other__',
      otherText: 'Hello',
    });
    const charCount = wrapper.find('.question-card__char-count');
    expect(charCount.text()).toBe('5 / 500');
  });

  // --- Next ボタン ---
  it('Next button is disabled when no selection', () => {
    const wrapper = createWrapper({ selectedChoiceId: null });
    const nextBtn = wrapper.find('.question-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(true);
  });

  it('Next button is disabled when Other selected but text is empty', () => {
    const wrapper = createWrapper({
      selectedChoiceId: '__other__',
      otherText: '',
    });
    const nextBtn = wrapper.find('.question-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(true);
  });

  it('Next button is enabled when choice selected', () => {
    const wrapper = createWrapper({ selectedChoiceId: 'a' });
    const nextBtn = wrapper.find('.question-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(false);
  });

  it('Next button is enabled when Other has non-whitespace text', () => {
    const wrapper = createWrapper({
      selectedChoiceId: '__other__',
      otherText: '有効なテキスト',
    });
    const nextBtn = wrapper.find('.question-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(false);
  });

  it('Next button is disabled when Other has whitespace-only text', () => {
    const wrapper = createWrapper({
      selectedChoiceId: '__other__',
      otherText: '   \t\n  ',
    });
    const nextBtn = wrapper.find('.question-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(true);
  });

  // --- ナビゲーションイベント ---
  it("emits 'next' when Next button clicked and enabled", async () => {
    const wrapper = createWrapper({ selectedChoiceId: 'b' });
    const nextBtn = wrapper.find('.question-card__next-btn');
    await nextBtn.trigger('click');
    expect(wrapper.emitted('next')).toBeTruthy();
  });

  it("does not emit 'next' when Next button is disabled", async () => {
    const wrapper = createWrapper({ selectedChoiceId: null });
    const nextBtn = wrapper.find('.question-card__next-btn');
    await nextBtn.trigger('click');
    expect(wrapper.emitted('next')).toBeFalsy();
  });

  it("emits 'back' when Back button clicked", async () => {
    const wrapper = createWrapper();
    const backBtn = wrapper.find('.question-card__back-btn');
    await backBtn.trigger('click');
    expect(wrapper.emitted('back')).toBeTruthy();
  });
});
