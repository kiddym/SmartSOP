import { describe, it, expect } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ConfigConsoleView from '@/views/admin/config/ConfigConsoleView.vue'

function mountHub() {
  return mount(ConfigConsoleView, {
    global: { plugins: [createPinia()], stubs: { 'router-link': RouterLinkStub } },
  })
}

describe('ConfigConsoleView', () => {
  it('渲染六个部署阶段区块', () => {
    const wrapper = mountHub()
    const text = wrapper.text()
    for (const t of ['组织基础', '人员权限', '全局参数', '业务模块', '自动化', '运维']) {
      expect(text).toContain(t)
    }
  })
  it('业务模块区块含四个聚合页入口', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    for (const to of ['/admin/config/sop', '/admin/config/work-order', '/admin/config/request', '/admin/config/custom-fields']) {
      expect(targets).toContain(to)
    }
  })
  it('组织基础/全局参数指向组织设置聚合页对应 tab', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    expect(targets).toContain('/admin/config/organization?tab=company')
    expect(targets).toContain('/admin/config/organization?tab=global')
  })
})
