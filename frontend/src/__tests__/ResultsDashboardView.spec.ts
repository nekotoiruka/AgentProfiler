import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ResultsDashboardView from '@/views/ResultsDashboardView.vue';
import type { ProfileOutput } from '@/types/profile';

/**
 * ResultsDashboardView コンポーネントテスト
 * Validates: Requirements 7.1, 7.3, 7.4
 */

// --- Mock Data ---

const mockProfile: ProfileOutput = {
  profile_id: 'prof_000001',
  base_os: {
    axes: {
      extroverted_introverted: 0.72,
      sensing_intuition: 0.35,
      thinking_feeling: 0.68,
      judging_perceiving: 0.51,
    },
    decision_style: 'extroverted_intuitive_thinking_judging',
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

// --- Mocks ---

// useSessionStore mock
const mockFetchProfile = vi.fn();

vi.mock('@/stores/session', () => ({
  useSessionStore: () => ({
    fetchProfile: mockFetchProfile,
  }),
}));

// vue-chartjs Radar stub (Chart.js does not work in jsdom)
vi.mock('vue-chartjs', () => ({
  Radar: {
    name: 'Radar',
    template: '<canvas data-testid="radar-chart"></canvas>',
    props: ['data', 'options'],
  },
}));

// chart.js stub
vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  RadialLinearScale: {},
  PointElement: {},
  LineElement: {},
  Filler: {},
  Tooltip: {},
  Legend: {},
}));

// --- Helper ---

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

  // 1. ローディングスピナー表示
  it('shows loading spinner initially', () => {
    mockFetchProfile.mockReturnValue(new Promise(() => {})); // never resolves
    const wrapper = createWrapper();
    expect(wrapper.find('.results-dashboard__spinner').exists()).toBe(true);
    expect(wrapper.text()).toContain('プロファイルを読み込んでいます');
  });

  // 2. fetchProfile 失敗時のエラーメッセージ
  it('shows error message when fetchProfile fails', async () => {
    mockFetchProfile.mockRejectedValue(new Error('プロファイルの取得に失敗しました'));
    const wrapper = createWrapper();
    await flushPromises();

    expect(wrapper.find('.results-dashboard__error').exists()).toBe(true);
    expect(wrapper.find('.results-dashboard__error-message').text()).toBe(
      'プロファイルの取得に失敗しました',
    );
  });

  // 3. Radar チャートコンポーネント描画
  it('renders Radar chart component when profile loaded', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();

    expect(wrapper.find('[data-testid="radar-chart"]').exists()).toBe(true);
  });

  // 4. decision_style ラベル表示
  it('renders decision_style label', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();

    const label = wrapper.find('.results-dashboard__decision-label');
    expect(label.text()).toBe('extroverted_intuitive_thinking_judging');
  });

  // 5. do_not_list 項目表示
  it('renders do_not_list items', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();

    const listItems = wrapper.findAll('.results-dashboard__list li');
    expect(listItems).toHaveLength(2);
    expect(listItems[0].text()).toBe(
      '一人で長時間考える時間を強制しないでください（外向優位）',
    );
    expect(listItems[1].text()).toBe(
      '過度に詳細な手順指示を与えないでください（直観優位）',
    );
  });

  // 6. lexical_tags チップ表示
  it('renders lexical_tags chips', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();

    const chips = wrapper.findAll('.results-dashboard__chip');
    expect(chips).toHaveLength(5);
    expect(chips[0].text()).toBe('brainstorming');
    expect(chips[4].text()).toBe('prototyping');
  });

  // 7. JSON プレビュー表示
  it('renders JSON preview code block', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const wrapper = createWrapper();
    await flushPromises();

    const codeBlock = wrapper.find('.results-dashboard__code-block');
    expect(codeBlock.exists()).toBe(true);
    // JSON内にprofile_idが含まれる
    expect(codeBlock.text()).toContain('prof_000001');
  });

  // 8. コピーボタンでclipboard.writeText呼び出し
  it('copy button calls navigator.clipboard.writeText', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    });

    const wrapper = createWrapper();
    await flushPromises();

    const copyBtn = wrapper.find('.results-dashboard__copy-button');
    await copyBtn.trigger('click');
    await flushPromises();

    expect(writeTextMock).toHaveBeenCalledWith(
      JSON.stringify(mockProfile, null, 2),
    );
  });

  // 9. コピー成功メッセージ
  it('shows success message after copy', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    const wrapper = createWrapper();
    await flushPromises();

    const copyBtn = wrapper.find('.results-dashboard__copy-button');
    await copyBtn.trigger('click');
    await flushPromises();

    expect(copyBtn.text()).toBe('コピーしました');
  });

  // 10. コピー失敗メッセージ
  it('shows error message on copy failure', async () => {
    mockFetchProfile.mockResolvedValue(mockProfile);
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    });

    const wrapper = createWrapper();
    await flushPromises();

    const copyBtn = wrapper.find('.results-dashboard__copy-button');
    await copyBtn.trigger('click');
    await flushPromises();

    expect(copyBtn.text()).toBe('コピーに失敗しました');
  });
});
