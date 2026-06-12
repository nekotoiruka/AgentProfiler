import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MultiSelectCard from '@/components/MultiSelectCard.vue';
import type { Question } from '@/types/question';

/**
 * MultiSelectCard コンポーネントテスト
 * チェックボックス型複数選択UI
 */

const mockQuestion: Question = {
  id: 'int_001',
  text: '興味のある技術分野を選んでください（複数選択可）',
  category_id: 'interests',
  question_type: 'multi_select',
  source_reference: '',
  choices: [],
  options: [
    { id: 'web_frontend', label: 'Webフロントエンド', tags: ['frontend', 'web'] },
    { id: 'web_backend', label: 'Webバックエンド', tags: ['backend', 'api'] },
    { id: 'mobile', label: 'モバイルアプリ', tags: ['mobile'] },
    { id: 'cloud', label: 'クラウド/インフラ', tags: ['cloud', 'devops'] },
    { id: 'ai', label: '生成AI/LLM', tags: ['generative-ai', 'llm'] },
  ],
  min_select: 1,
  max_select: 3,
};

function createWrapper(overrides: Partial<{
  selectedOptions: string[];
  direction: 'forward' | 'backward';
}> = {}) {
  return mount(MultiSelectCard, {
    props: {
      question: mockQuestion,
      selectedOptions: overrides.selectedOptions ?? [],
      direction: overrides.direction ?? 'forward',
    },
  });
}

describe('MultiSelectCard', () => {
  it('renders question text', () => {
    const wrapper = createWrapper();
    expect(wrapper.find('.multi-select-card__text').text()).toBe(mockQuestion.text);
  });

  it('renders all options as checkboxes', () => {
    const wrapper = createWrapper();
    const options = wrapper.findAll('.multi-select-card__option');
    expect(options).toHaveLength(5);
  });

  it('shows selection count', () => {
    const wrapper = createWrapper({ selectedOptions: ['web_frontend', 'ai'] });
    const count = wrapper.find('.multi-select-card__count');
    expect(count.text()).toContain('2件選択中');
  });

  it('emits toggle-option when checkbox clicked', async () => {
    const wrapper = createWrapper();
    const checkboxes = wrapper.findAll('.multi-select-card__checkbox');
    await checkboxes[0].setValue(true);
    expect(wrapper.emitted('toggle-option')).toBeTruthy();
    expect(wrapper.emitted('toggle-option')![0]).toEqual(['web_frontend']);
  });

  it('marks selected options with --selected class', () => {
    const wrapper = createWrapper({ selectedOptions: ['mobile'] });
    const options = wrapper.findAll('.multi-select-card__option');
    const mobileOption = options[2]; // 3rd option is 'mobile'
    expect(mobileOption.classes()).toContain('multi-select-card__option--selected');
  });

  it('disables unselected options at max_select limit', () => {
    const wrapper = createWrapper({
      selectedOptions: ['web_frontend', 'web_backend', 'cloud'],
    });
    const checkboxes = wrapper.findAll('.multi-select-card__checkbox');
    // mobile (index 2) and ai (index 4) should be disabled
    expect((checkboxes[2].element as HTMLInputElement).disabled).toBe(true);
    expect((checkboxes[4].element as HTMLInputElement).disabled).toBe(true);
    // selected ones should NOT be disabled
    expect((checkboxes[0].element as HTMLInputElement).disabled).toBe(false);
  });

  it('Next button is disabled when below min_select', () => {
    const wrapper = createWrapper({ selectedOptions: [] });
    const nextBtn = wrapper.find('.multi-select-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(true);
  });

  it('Next button is enabled when min_select met', () => {
    const wrapper = createWrapper({ selectedOptions: ['web_frontend'] });
    const nextBtn = wrapper.find('.multi-select-card__next-btn');
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(false);
  });

  it("emits 'next' when Next clicked and enabled", async () => {
    const wrapper = createWrapper({ selectedOptions: ['web_frontend'] });
    const nextBtn = wrapper.find('.multi-select-card__next-btn');
    await nextBtn.trigger('click');
    expect(wrapper.emitted('next')).toBeTruthy();
  });

  it("does not emit 'next' when Next disabled", async () => {
    const wrapper = createWrapper({ selectedOptions: [] });
    const nextBtn = wrapper.find('.multi-select-card__next-btn');
    await nextBtn.trigger('click');
    expect(wrapper.emitted('next')).toBeFalsy();
  });

  it("emits 'back' when Back clicked", async () => {
    const wrapper = createWrapper();
    const backBtn = wrapper.find('.multi-select-card__back-btn');
    await backBtn.trigger('click');
    expect(wrapper.emitted('back')).toBeTruthy();
  });

  it('shows min/max range in selection text', () => {
    const wrapper = createWrapper({ selectedOptions: [] });
    const count = wrapper.find('.multi-select-card__count');
    expect(count.text()).toContain('1〜3件');
  });
});
