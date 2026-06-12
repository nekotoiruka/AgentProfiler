import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ProgressBar from '@/components/ProgressBar.vue';

/**
 * ProgressBar コンポーネントテスト
 * Validates: Requirements 1.3, 1.4
 */

function createWrapper(props: {
  categoryName: string;
  categoryProgress: number;
  overallProgress: number;
}) {
  return mount(ProgressBar, { props });
}

describe('ProgressBar', () => {
  it('renders category name', () => {
    const wrapper = createWrapper({
      categoryName: 'Business OS',
      categoryProgress: 50,
      overallProgress: 25,
    });
    expect(wrapper.find('.category-name').text()).toBe('Business OS');
  });

  it('displays category progress percentage', () => {
    const wrapper = createWrapper({
      categoryName: 'Communication',
      categoryProgress: 75,
      overallProgress: 40,
    });
    const sections = wrapper.findAll('.progress-section');
    // 最初のセクションがカテゴリ進捗
    const categoryValue = sections[0].find('.progress-value');
    expect(categoryValue.text()).toBe('75%');
  });

  it('displays overall progress percentage', () => {
    const wrapper = createWrapper({
      categoryName: 'Business OS',
      categoryProgress: 50,
      overallProgress: 33,
    });
    const sections = wrapper.findAll('.progress-section');
    // 2番目のセクションが全体進捗
    const overallValue = sections[1].find('.progress-value');
    expect(overallValue.text()).toBe('33%');
  });

  it('progress bar fill width matches percentage', () => {
    const wrapper = createWrapper({
      categoryName: 'Business OS',
      categoryProgress: 60,
      overallProgress: 45,
    });
    const fills = wrapper.findAll('.progress-fill');
    // カテゴリ進捗バー
    expect(fills[0].attributes('style')).toContain('width: 60%');
    // 全体進捗バー
    expect(fills[1].attributes('style')).toContain('width: 45%');
  });

  it('handles 0% progress', () => {
    const wrapper = createWrapper({
      categoryName: 'Lifestyle',
      categoryProgress: 0,
      overallProgress: 0,
    });
    const fills = wrapper.findAll('.progress-fill');
    expect(fills[0].attributes('style')).toContain('width: 0%');
    expect(fills[1].attributes('style')).toContain('width: 0%');

    const values = wrapper.findAll('.progress-value');
    expect(values[0].text()).toBe('0%');
    expect(values[1].text()).toBe('0%');
  });

  it('handles 100% progress', () => {
    const wrapper = createWrapper({
      categoryName: 'Business OS',
      categoryProgress: 100,
      overallProgress: 100,
    });
    const fills = wrapper.findAll('.progress-fill');
    expect(fills[0].attributes('style')).toContain('width: 100%');
    expect(fills[1].attributes('style')).toContain('width: 100%');

    const values = wrapper.findAll('.progress-value');
    expect(values[0].text()).toBe('100%');
    expect(values[1].text()).toBe('100%');
  });

  it('clamps values above 100 to 100', () => {
    const wrapper = createWrapper({
      categoryName: 'Test',
      categoryProgress: 150,
      overallProgress: 200,
    });
    const fills = wrapper.findAll('.progress-fill');
    expect(fills[0].attributes('style')).toContain('width: 100%');
    expect(fills[1].attributes('style')).toContain('width: 100%');
  });

  it('clamps values below 0 to 0', () => {
    const wrapper = createWrapper({
      categoryName: 'Test',
      categoryProgress: -10,
      overallProgress: -5,
    });
    const fills = wrapper.findAll('.progress-fill');
    expect(fills[0].attributes('style')).toContain('width: 0%');
    expect(fills[1].attributes('style')).toContain('width: 0%');
  });

  it('has proper ARIA attributes (role, aria-valuenow, etc.)', () => {
    const wrapper = createWrapper({
      categoryName: 'Business OS',
      categoryProgress: 42,
      overallProgress: 67,
    });
    const tracks = wrapper.findAll('.progress-track');

    // カテゴリ進捗バー
    expect(tracks[0].attributes('role')).toBe('progressbar');
    expect(tracks[0].attributes('aria-valuenow')).toBe('42');
    expect(tracks[0].attributes('aria-valuemin')).toBe('0');
    expect(tracks[0].attributes('aria-valuemax')).toBe('100');
    expect(tracks[0].attributes('aria-label')).toBe('Business OSの進捗: 42%');

    // 全体進捗バー
    expect(tracks[1].attributes('role')).toBe('progressbar');
    expect(tracks[1].attributes('aria-valuenow')).toBe('67');
    expect(tracks[1].attributes('aria-valuemin')).toBe('0');
    expect(tracks[1].attributes('aria-valuemax')).toBe('100');
    expect(tracks[1].attributes('aria-label')).toBe('全体進捗: 67%');
  });
});
