import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lc, cc, dc } = vi.hoisted(() => ({
  lc: vi.fn(),
  cc: vi.fn(),
  dc: vi.fn(),
}))
vi.mock('@/api/currencies', () => ({
  listCurrencies: lc,
  createCurrency: cc,
  deleteCurrency: dc,
}))

const authState = vi.hoisted(() => ({ role_code: 'super_admin' as string }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: () => true,
    user: { role_code: authState.role_code },
  }),
}))

import CurrenciesView from '@/views/platform/CurrenciesView.vue'

function mountView() {
  return mount(CurrenciesView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.role_code = 'super_admin'
  lc.mockReset().mockResolvedValue([
    { id: 'c1', code: 'CNY', name: '人民币', symbol: '¥' },
    { id: 'c2', code: 'USD', name: '美元', symbol: '$' },
  ])
  cc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
})

describe('CurrenciesView', () => {
  it('加载并渲染货币行（code/name/symbol）', async () => {
    const w = mountView()
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(w.text()).toContain('CNY')
    expect(w.text()).toContain('人民币')
    expect(w.text()).toContain('¥')
    expect(w.text()).toContain('USD')
    expect(w.text()).toContain('美元')
    expect(w.text()).toContain('$')
  })

  it('super_admin 新增提交携带 code/name/symbol', async () => {
    const w = mountView()
    await flushPromises()

    const newBtn = w.findAll('.el-button').find((b) => b.text() === '新增货币')
    expect(newBtn).toBeTruthy()
    await newBtn!.trigger('click')
    await flushPromises()

    const codeInput = document.querySelector(
      '.el-dialog input[placeholder="请输入货币代码"]',
    ) as HTMLInputElement
    expect(codeInput).toBeTruthy()
    codeInput.value = 'EUR'
    codeInput.dispatchEvent(new Event('input'))

    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入货币名称"]',
    ) as HTMLInputElement
    expect(nameInput).toBeTruthy()
    nameInput.value = '欧元'
    nameInput.dispatchEvent(new Event('input'))

    const symbolInput = document.querySelector(
      '.el-dialog input[placeholder="请输入货币符号"]',
    ) as HTMLInputElement
    expect(symbolInput).toBeTruthy()
    symbolInput.value = '€'
    symbolInput.dispatchEvent(new Event('input'))
    await flushPromises()

    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()

    expect(cc).toHaveBeenCalled()
    expect(cc.mock.calls[0][0]).toMatchObject({ code: 'EUR', name: '欧元', symbol: '€' })
  })

  it('非 super_admin 隐藏新增与行内删除按钮', async () => {
    authState.role_code = 'admin'
    const w = mountView()
    await flushPromises()

    const newBtn = w.findAll('.el-button').find((b) => b.text() === '新增货币')
    expect(newBtn).toBeFalsy()

    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    expect(delBtn).toBeFalsy()
  })
})
