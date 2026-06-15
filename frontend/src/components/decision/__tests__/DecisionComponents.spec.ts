import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BinaryChoice from '../BinaryChoice.vue'
import MetadataPanel from '../MetadataPanel.vue'
import FeedbackButtons from '../FeedbackButtons.vue'
import OrderingDnD from '../OrderingDnD.vue'

describe('BinaryChoice', () => {
  const choices = [
    { id: 'a', label: 'Choice A' },
    { id: 'b', label: 'Choice B' },
  ] as [{ id: string; label: string }, { id: string; label: string }]

  it('renders two choices', () => {
    const wrapper = mount(BinaryChoice, {
      props: { questionId: 'q1', choices, modelValue: null },
    })
    expect(wrapper.findAll('.choice-card')).toHaveLength(2)
  })

  it('emits update:modelValue on click', async () => {
    const wrapper = mount(BinaryChoice, {
      props: { questionId: 'q1', choices, modelValue: null },
    })
    await wrapper.findAll('.choice-card')[0].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['a'])
  })

  it('highlights selected card', () => {
    const wrapper = mount(BinaryChoice, {
      props: { questionId: 'q1', choices, modelValue: 'b' },
    })
    const cards = wrapper.findAll('.choice-card')
    expect(cards[1].classes()).toContain('selected')
    expect(cards[0].classes()).not.toContain('selected')
  })

  it('exclusive selection - second click replaces', async () => {
    const wrapper = mount(BinaryChoice, {
      props: { questionId: 'q1', choices, modelValue: 'a' },
    })
    await wrapper.findAll('.choice-card')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['b'])
  })
})

describe('OrderingDnD', () => {
  const steps = [
    { id: 's1', label: 'Step 1' },
    { id: 's2', label: 'Step 2' },
    { id: 's3', label: 'Step 3' },
  ]

  // matchMedia モック（desktop: matches = false）
  function mockMatchMedia(mobile: boolean) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query: string) => ({
        matches: mobile,
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }),
    })
  }

  it('emits update:modelValue with reordered data on drop', async () => {
    mockMatchMedia(false)
    const wrapper = mount(OrderingDnD, {
      props: { questionId: 'q1', steps, modelValue: ['s1', 's2', 's3'] },
    })
    // ドラッグ&ドロップのデータフローをテスト
    const items = wrapper.findAll('.ordering-item')
    // ドラッグ開始（index 0）
    await items[0].trigger('dragstart', {
      dataTransfer: { effectAllowed: '', setData: () => {} },
    })
    // ドロップ（index 2）
    await items[2].trigger('drop', {
      dataTransfer: { dropEffect: '' },
    })
    // s1 が index 2 に移動 → ['s2', 's3', 's1']
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['s2', 's3', 's1']])
  })

  it('renders mobile fallback with number inputs on narrow viewport', async () => {
    mockMatchMedia(true)
    const wrapper = mount(OrderingDnD, {
      props: { questionId: 'q1', steps, modelValue: ['s1', 's2', 's3'] },
    })
    // onMounted で isMobile が更新されるのを待つ
    await wrapper.vm.$nextTick()
    // モバイルモードではナンバー入力が表示される
    expect(wrapper.findAll('.rank-input')).toHaveLength(3)
    expect(wrapper.find('.ordering-mobile').exists()).toBe(true)
  })
})

describe('MetadataPanel', () => {
  const defaultMetadata = {
    permanence: 'permanent' as const,
    confidence: 0.6,
    exception_note: null,
    is_core_rule: false,
    ambiguity: 0.0,
  }

  it('starts collapsed', () => {
    const wrapper = mount(MetadataPanel, {
      props: { modelValue: defaultMetadata },
    })
    expect(wrapper.find('#metadata-content').isVisible()).toBe(false)
  })

  it('expands on toggle click', async () => {
    const wrapper = mount(MetadataPanel, {
      props: { modelValue: defaultMetadata },
    })
    await wrapper.find('.panel-toggle').trigger('click')
    expect(wrapper.find('#metadata-content').isVisible()).toBe(true)
  })

  it('applies default metadata values', () => {
    const wrapper = mount(MetadataPanel, {
      props: { modelValue: defaultMetadata },
    })
    // permanence: permanent がアクティブ
    const toggleBtns = wrapper.findAll('.toggle-btn')
    expect(toggleBtns[0].classes()).toContain('active')
    // confidence: 0.6 → ★3
    const slider = wrapper.find('#confidence-slider')
    expect(slider.attributes('value')).toBe('3')
  })
})

describe('FeedbackButtons', () => {
  it('renders 3 buttons', () => {
    const wrapper = mount(FeedbackButtons)
    expect(wrapper.findAll('.feedback-btn')).toHaveLength(3)
  })

  it('emits approve on approve click', async () => {
    const wrapper = mount(FeedbackButtons)
    await wrapper.find('.feedback-btn--approve').trigger('click')
    expect(wrapper.emitted('feedback')?.[0]).toEqual([{ feedback_type: 'approve' }])
  })

  it('shows textarea on reject click', async () => {
    const wrapper = mount(FeedbackButtons)
    await wrapper.find('.feedback-btn--reject').trigger('click')
    expect(wrapper.find('.feedback-buttons__correction').exists()).toBe(true)
  })

  it('emits skip on skip click', async () => {
    const wrapper = mount(FeedbackButtons)
    await wrapper.find('.feedback-btn--skip').trigger('click')
    expect(wrapper.emitted('feedback')?.[0]).toEqual([{ feedback_type: 'skip' }])
  })

  it('enforces 2000 char limit on correction textarea', async () => {
    const wrapper = mount(FeedbackButtons)
    // テキストエリアを展開
    await wrapper.find('.feedback-btn--reject').trigger('click')
    const textarea = wrapper.find('#correction-textarea')
    expect(textarea.attributes('maxlength')).toBe('2000')
  })
})
