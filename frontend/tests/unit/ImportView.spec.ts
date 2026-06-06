import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { dl, imp } = vi.hoisted(() => ({
  dl: vi.fn(),
  imp: vi.fn(),
}))
vi.mock('@/api/imports', () => ({
  downloadTemplate: dl,
  importCsv: imp,
}))

import ImportView from '@/views/admin/ImportView.vue'

function findButton(text: string): HTMLElement | undefined {
  return Array.from(document.querySelectorAll('.el-button')).find(
    (b) => b.textContent?.trim() === text,
  ) as HTMLElement | undefined
}

beforeEach(() => {
  setActivePinia(createPinia())
  dl.mockReset().mockResolvedValue(undefined)
  imp.mockReset()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ImportView', () => {
  it('渲染实体选择与下载/导入按钮', async () => {
    mount(ImportView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    expect(document.body.textContent).toContain('资产')
    expect(document.body.textContent).toContain('位置')
    expect(document.body.textContent).toContain('备件')
    expect(findButton('下载模板 CSV')).toBeTruthy()
    expect(findButton('开始导入')).toBeTruthy()
  })

  it('点击下载模板调用 downloadTemplate（默认 assets）', async () => {
    mount(ImportView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    findButton('下载模板 CSV')!.click()
    await flushPromises()
    expect(dl).toHaveBeenCalledWith('assets')
  })

  it('选实体+上传+提交后展示创建/失败结果与错误表', async () => {
    imp.mockResolvedValue({
      created: 2,
      failed: 1,
      errors: [{ row: 4, message: '资产分类“X”不存在' }],
    })
    const w = mount(ImportView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()

    // 切到 locations 实体。
    const vm = w.vm as unknown as {
      entity: string
      file: File | null
      onSubmit: () => Promise<void>
    }
    vm.entity = 'locations'
    // 模拟已选文件（el-upload 手动模式只缓存 raw）。
    vm.file = new File(['name,address,parent\n甲,路1,\n'], 'locations.csv', { type: 'text/csv' })
    await flushPromises()

    await vm.onSubmit()
    await flushPromises()

    expect(imp).toHaveBeenCalledTimes(1)
    expect(imp.mock.calls[0][0]).toBe('locations')
    expect(document.body.textContent).toContain('成功 2 条')
    expect(document.body.textContent).toContain('失败 1 条')
    expect(document.body.textContent).toContain('资产分类“X”不存在')
  })

  it('未选文件时不调用 importCsv', async () => {
    const w = mount(ImportView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await flushPromises()
    const vm = w.vm as unknown as { onSubmit: () => Promise<void> }
    await vm.onSubmit()
    await flushPromises()
    expect(imp).not.toHaveBeenCalled()
  })
})
