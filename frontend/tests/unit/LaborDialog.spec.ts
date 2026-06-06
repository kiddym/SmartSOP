import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import type { LaborRead } from '@/types/workOrder'

const { cl, ul } = vi.hoisted(() => ({ cl: vi.fn(), ul: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ createLabor: cl, updateLabor: ul }))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/timeCategories', () => ({
  listTimeCategories: vi
    .fn()
    .mockResolvedValue([{ id: 'tc1', name: '常规工时', hourly_rate: '50.00', description: '' }]),
}))

import LaborDialog from '@/components/workorder/LaborDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  cl.mockReset().mockResolvedValue({})
  ul.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('LaborDialog', () => {
  it('create 提交按分钟转 duration_seconds 调 createLabor', async () => {
    const w = mount(LaborDialog, {
      props: { visible: true, workOrderId: 'w1', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.minutes = 30
    vm.form.user_id = 'u1'
    vm.form.time_category_id = 'tc1'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cl).toHaveBeenCalled()
    expect(cl.mock.calls[0][0]).toBe('w1')
    expect(cl.mock.calls[0][1]).toMatchObject({
      duration_seconds: 1800,
      user_id: 'u1',
      time_category_id: 'tc1',
      include_to_total: true,
    })
    expect(w.emitted('saved')).toBeTruthy()
  })

  it('include_to_total 关闭后随 payload 发送 false', async () => {
    const w = mount(LaborDialog, {
      props: { visible: true, workOrderId: 'w1', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.minutes = 10
    vm.form.include_to_total = false
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cl.mock.calls[0][1]).toMatchObject({ include_to_total: false })
  })

  it('edit 回填 duration_seconds 并调 updateLabor', async () => {
    const editingLabor: LaborRead = {
      id: 'l1',
      work_order_id: 'w1',
      user_id: 'u1',
      time_category_id: 'tc1',
      started_at: null,
      stopped_at: '2026-06-01T01:00:00',
      duration_seconds: 1800,
      hourly_rate: '50.00',
      notes: '测试备注',
      include_to_total: true,
      running: false,
      cost: '25.00',
      running_elapsed_seconds: null,
    }
    const w = mount(LaborDialog, {
      props: { visible: true, workOrderId: 'w1', editing: editingLabor },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    expect(vm.form.minutes).toBe(30)
    vm.form.minutes = 45
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ul).toHaveBeenCalled()
    expect(ul.mock.calls[0][0]).toBe('w1')
    expect(ul.mock.calls[0][1]).toBe('l1')
    expect(ul.mock.calls[0][2]).toMatchObject({ duration_seconds: 2700 })
    expect(cl).not.toHaveBeenCalled()
  })
})
