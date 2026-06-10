import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SopConfigView from '@/views/admin/config/SopConfigView.vue'
import WorkOrderConfigView from '@/views/admin/config/WorkOrderConfigView.vue'
import RequestConfigView from '@/views/admin/config/RequestConfigView.vue'
import CustomFieldsConfigView from '@/views/admin/config/CustomFieldsConfigView.vue'

// stub all embedded children — aggregate pages only own the tab skeleton
const stubs = {
  FieldManageView: { template: '<div class="s-field-manage" />' },
  HeadingRulesView: { template: '<div class="s-heading-rules" />' },
  FolderManageView: { template: '<div class="s-folder-manage" />' },
  WorkOrderFieldsView: { template: '<div class="s-wo-fields" />' },
  RequestFieldsView: { template: '<div class="s-req-fields" />' },
  CustomFieldsView: { template: '<div class="s-custom-fields" />' },
  WorkOrderCategoryManagePanel: { template: '<div class="s-wo-cat" />' },
  TimeCategoryManagePanel: { template: '<div class="s-time-cat" />' },
  CostCategoryManagePanel: { template: '<div class="s-cost-cat" />' },
}

function mountWith(comp: unknown, query: Record<string, string> = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: comp as never }] })
  router.push({ path: '/', query })
  return router.isReady().then(() =>
    mount(comp as never, { global: { plugins: [createPinia(), router], stubs } }),
  )
}

describe('SopConfigView', () => {
  it('渲染程序字段/标题字典/文件夹三个 tab', async () => {
    const w = await mountWith(SopConfigView)
    const labels = w.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['程序字段', '标题字典', '文件夹']))
  })
  it('按 query.tab=heading-rules 选中标题字典', async () => {
    const w = await mountWith(SopConfigView, { tab: 'heading-rules' })
    expect(w.find('.el-tabs__item.is-active').text()).toBe('标题字典')
  })
  it('按 query.tab=folders 选中文件夹', async () => {
    const w = await mountWith(SopConfigView, { tab: 'folders' })
    expect(w.find('.el-tabs__item.is-active').text()).toBe('文件夹')
  })
})

describe('WorkOrderConfigView', () => {
  it('渲染五个 tab', async () => {
    const w = await mountWith(WorkOrderConfigView)
    const labels = w.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['表单字段', '自定义字段', '工单分类', '工时分类', '成本分类']))
  })
})

describe('RequestConfigView', () => {
  it('渲染表单字段与自定义字段两个 tab', async () => {
    const w = await mountWith(RequestConfigView)
    const labels = w.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['表单字段', '自定义字段']))
  })
})

describe('CustomFieldsConfigView', () => {
  it('渲染资产/位置/备件三个 tab', async () => {
    const w = await mountWith(CustomFieldsConfigView)
    const labels = w.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['资产', '位置', '备件']))
  })
})
