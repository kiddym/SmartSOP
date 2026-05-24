import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StepFormFields from '@/components/editor/StepFormFields.vue'
import type { InputSchema } from '@/types/node'

function mountFields(schema: InputSchema) {
  return mount(StepFormFields, {
    props: { schema },
    global: { plugins: [ElementPlus] },
  })
}

describe('StepFormFields 新增配置分支', () => {
  it('YESNO 显示是/否标签与不适用开关', () => {
    const w = mountFields({ type: 'YESNO' })
    expect(w.text()).toContain('是 标签')
    expect(w.text()).toContain('否 标签')
    expect(w.text()).toContain('包含')
  })

  it('YESNO 编辑是标签派发 update:schema', async () => {
    const w = mountFields({ type: 'YESNO' })
    await w.findAll('input')[0].setValue('Y')
    const events = w.emitted('update:schema')
    expect(events).toBeTruthy()
    expect((events!.at(-1)![0] as InputSchema).yes_label).toBe('Y')
  })

  it('METER 显示名称/下限/上限/小数位', () => {
    const w = mountFields({ type: 'METER' })
    expect(w.text()).toContain('仪表名称')
    expect(w.text()).toContain('下限')
    expect(w.text()).toContain('上限')
    expect(w.text()).toContain('小数位')
  })

  it('SIGNATURE 显示签名提示输入', () => {
    const w = mountFields({ type: 'SIGNATURE' })
    expect(w.text()).toContain('签名提示')
  })

  it('DATE 显示包含时间开关', () => {
    const w = mountFields({ type: 'DATE' })
    expect(w.text()).toContain('包含时间')
  })

  it('PHOTO 显示最大张数', () => {
    const w = mountFields({ type: 'PHOTO' })
    expect(w.text()).toContain('最大张数')
  })

  it('COMMON 仍显示无需配置兜底', () => {
    const w = mountFields({ type: 'COMMON' })
    expect(w.text()).toContain('无需额外配置')
  })
})
