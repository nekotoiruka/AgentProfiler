import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ResultsDashboardView from '@/views/ResultsDashboardView.vue';
import type { ProfileOutput } from '@/types/profile';

/**
 * ResultsDashboardView コンポーネントテスト
 * 双極スライダーUI + 16タイプ日本語名
 */

const mockProfile: ProfileOutput = {
  profile_id: 'prof_000001',
  base_os: {
    axes: {
      extroverted_introverted: 0.72,
      sensing_intuition: 0.35,
      thinking_feeling: 0.68,
      judging_perceiving: 0.51,
    },
    decision_style: '覇道の戦略家（ENTJ）',
    do_not_list: [
      '一人で長時間考える時間を強制しないでください（外向優位）',
      '過度に詳細な手順指示を与えないでください（直観優位）',
    ],
  },
  lexical_tags: ['brainstorming', 'data-driven', 'agile', 'remote-work', 'prototyping'],
  semantic_contexts: {
    problem_solving: '問題に直面した際...',
    communication_style: 'コミュニケーションにおいては...',
    work_rhythm: '業務のリズムとしては...',
    analog_habits: 'デジタル以外の習慣として...',
    lifestyle_preferences: 'ライフスタイルにおいては...',
  },
  context_layers: { base_os: 1, lexical_tags: 2, semantic_contexts: 3 },
};

const mockFetchProfile = vi.fn();

vi.mock('@/stores/session', () => ({
  useSessionStore: () => ({
    fetchProfile: mockFetchProfile,
  }),
}));

function createWrapper() {
  return mount(ResultsDashboardView, {
    global: {
      plugins: [createPinia()],
    },
  });
}

describe('ResultsDashboardView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    mockFetchProfile.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('shows loading spinner initially', () => {
    mockFetchProfile.mockReturnValue(new Promise(() => {}));
    const wrapper = createWrapper();
    expect(wrapper.find('.results-dashboard__spinner').exists()).toBe(true);
  });

  it('shows error message when fetchProfile fails', async () => {
    mockFetchProfile.mockRejectedValue(new Error('取得失敗'));
    const wrapper = createWrapper();
    await flushPromises();
    expect(wrapper.find('.results-dashboard__error-message').text()).toBe('取得失敗');
  });

  it('renders type name (decision_style)', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();
    expect(wrapper.find('.results-dashboard__type-name').text()).toBe('覇道の戦略家（ENTJ）');
  });

  it('renders 4 bipolar sliders', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();
    const sliders = wrapper.findAll('.bipolar-slider');
    expect(sliders).toHaveLength(4);
  });

  it('slider indicator position matches score', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();
    const indicators = wrapper.findAll('.bipolar-slider__indicator');
    // EI = 0.72 → left: 72%
    expect(indicators[0].attributes('style')).toContain('left: 72%');
  });

  it('renders do_not_list items', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();
    const items = wrapper.findAll('.results-dashboard__list li');
    expect(items).toHaveLength(2);
  });

  it('renders lexical_tags chips', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();
    const chips = wrapper.findAll('.results-dashboard__chip');
    expect(chips).toHaveLength(5);
  });

  it('renders JSON preview', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();
    expect(wrapper.find('.results-dashboard__code-block').text()).toContain('prof_000001');
  });

  it('copy button calls clipboard API', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: writeTextMock } });

    const wrapper = createWrapper();
    await flushPromises();
    await wrapper.find('.results-dashboard__copy-button').trigger('click');
    await flushPromises();
    expect(writeTextMock).toHaveBeenCalled();
  });

  it('shows success message after copy', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

    const wrapper = createWrapper();
    await flushPromises();
    await wrapper.find('.results-dashboard__copy-button').trigger('click');
    await flushPromises();
    expect(wrapper.find('.results-dashboard__copy-button').text()).toContain('コピーしました');
  });
});
