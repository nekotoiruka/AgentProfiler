/**
 * AgentList.vue ユニットテスト
 * Validates: Requirements 21.1, 21.2
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, type Ref } from 'vue'
import AgentList from './AgentList.vue'

// モック用のリアクティブ状態
let mockAgents: Ref<any[]>
let mockLoading: Ref<boolean>
const mockListAgents = vi.fn()

vi.mock('./composables/useAgents', () => ({
  useAgents: () => ({
    agents: mockAgents,
    loading: mockLoading,
    listAgents: mockListAgents,
  }),
}))

describe('AgentList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAgents = ref([])
    mockLoading = ref(false)
  })

  it('ローディング中に読み込みメッセージを表示する', () => {
    mockLoading = ref(true)

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    expect(wrapper.find('.loading').text()).toBe('読み込み中...')
    expect(wrapper.find('ul').exists()).toBe(false)
  })

  it('マウント時に listAgents を profileId で呼び出す', () => {
    mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    expect(mockListAgents).toHaveBeenCalledWith('prof_001234')
  })

  it('エージェント一覧を display_name で表示する', () => {
    mockAgents = ref([
      { agent_id: 'agent_1', profile_id: 'prof_001234', display_name: 'アリス', created_at: '2024-01-01', is_active: true },
      { agent_id: 'agent_2', profile_id: 'prof_001234', display_name: 'ボブ', created_at: '2024-01-02', is_active: true },
    ])

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    const items = wrapper.findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toBe('アリス')
    expect(items[1].text()).toBe('ボブ')
  })

  it('エージェントをクリックすると select イベントを emit する', async () => {
    const agent = { agent_id: 'agent_1', profile_id: 'prof_001234', display_name: 'アリス', created_at: '2024-01-01', is_active: true }
    mockAgents = ref([agent])

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    await wrapper.find('li').trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual([agent])
  })

  it('選択されたエージェントに selected クラスと aria-selected が付与される', async () => {
    mockAgents = ref([
      { agent_id: 'agent_1', profile_id: 'prof_001234', display_name: 'アリス', created_at: '2024-01-01', is_active: true },
      { agent_id: 'agent_2', profile_id: 'prof_001234', display_name: 'ボブ', created_at: '2024-01-02', is_active: true },
    ])

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    const items = wrapper.findAll('li')
    await items[0].trigger('click')

    // DOM更新後に再取得
    const updatedItems = wrapper.findAll('li')
    expect(updatedItems[0].classes()).toContain('selected')
    expect(updatedItems[0].attributes('aria-selected')).toBe('true')
    expect(updatedItems[1].attributes('aria-selected')).toBe('false')
  })

  it('Enter キーでエージェントを選択できる', async () => {
    const agent = { agent_id: 'agent_1', profile_id: 'prof_001234', display_name: 'アリス', created_at: '2024-01-01', is_active: true }
    mockAgents = ref([agent])

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    await wrapper.find('li').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual([agent])
  })

  it('Space キーでエージェントを選択できる', async () => {
    const agent = { agent_id: 'agent_1', profile_id: 'prof_001234', display_name: 'アリス', created_at: '2024-01-01', is_active: true }
    mockAgents = ref([agent])

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    await wrapper.find('li').trigger('keydown', { key: ' ' })

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual([agent])
  })

  it('listbox role と aria-label が設定されている', () => {
    mockAgents = ref([
      { agent_id: 'agent_1', profile_id: 'prof_001234', display_name: 'アリス', created_at: '2024-01-01', is_active: true },
    ])

    const wrapper = mount(AgentList, {
      props: { profileId: 'prof_001234' },
    })

    const ul = wrapper.find('ul')
    expect(ul.attributes('role')).toBe('listbox')
    expect(ul.attributes('aria-label')).toBe('エージェント一覧')
  })
})
