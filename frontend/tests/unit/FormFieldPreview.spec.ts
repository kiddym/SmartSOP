import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FormFieldPreview from '@/components/editor/FormFieldPreview.vue'
import type { InputSchema } from '@/types/node'

function mountPreview(schema: InputSchema) {
  return mount(FormFieldPreview, {
    props: { schema },
    global: { plugins: [ElementPlus] },
  })
}

describe('FormFieldPreview', () => {
  it('NUMBER 显示单位与范围、小数位', () => {
    const w = mountPreview({ type: 'NUMBER', unit: '℃', min: 0, max: 100, decimals: 1 })
    expect(w.text()).toContain('℃')
    expect(w.text()).toContain('范围 0 ~ 100')
    expect(w.text()).toContain('1 位小数')
  })

  it('METER 显示名称与下限上限', () => {
    const w = mountPreview({ type: 'METER', name: '压力', unit: 'MPa', lower_limit: 1, upper_limit: 9 })
    expect(w.text()).toContain('压力')
    expect(w.text()).toContain('下限 1 / 上限 9')
  })

  it('METER 缺省名称回退为「仪表读数」', () => {
    const w = mountPreview({ type: 'METER' })
    expect(w.text()).toContain('仪表读数')
  })

  it('CHECK 默认渲染通过/不通过两按钮', () => {
    const w = mountPreview({ type: 'CHECK' })
    expect(w.text()).toContain('通过')
    expect(w.text()).toContain('不通过')
  })

  it('CHECK 自定义标签生效', () => {
    const w = mountPreview({ type: 'CHECK', pass_label: '合格', fail_label: '不合格' })
    expect(w.text()).toContain('合格')
    expect(w.text()).toContain('不合格')
  })

  it('YESNO 默认是/否，无不适用', () => {
    const w = mountPreview({ type: 'YESNO' })
    expect(w.text()).toContain('是')
    expect(w.text()).toContain('否')
    expect(w.text()).not.toContain('不适用')
  })

  it('YESNO na_enabled 时显示不适用', () => {
    const w = mountPreview({ type: 'YESNO', na_enabled: true })
    expect(w.text()).toContain('不适用')
  })

  it('CHECKBOX 按 options 渲染对应数量复选框', () => {
    const w = mountPreview({ type: 'CHECKBOX', options: ['甲', '乙', '丙'] })
    expect(w.findAll('.el-checkbox').length).toBe(3)
    expect(w.text()).toContain('甲')
  })

  it('CHECKBOX 无选项显示未配置提示', () => {
    const w = mountPreview({ type: 'CHECKBOX' })
    expect(w.text()).toContain('未配置选项')
  })

  it('RADIO 按 options 渲染对应数量单选', () => {
    const w = mountPreview({ type: 'RADIO', options: ['A', 'B'] })
    expect(w.findAll('.el-radio').length).toBe(2)
  })

  it('UPLOAD 显示占位与 accept/max_count', () => {
    const w = mountPreview({ type: 'UPLOAD', accept: 'image/*', max_count: 3 })
    expect(w.text()).toContain('添加文件')
    expect(w.text()).toContain('image/*')
    expect(w.text()).toContain('3')
  })

  it('PHOTO 显示最多张数', () => {
    const w = mountPreview({ type: 'PHOTO', max_count: 5 })
    expect(w.text()).toContain('添加照片')
    expect(w.text()).toContain('5 张')
  })

  it('SIGNATURE 显示占位与提示', () => {
    const w = mountPreview({ type: 'SIGNATURE', hint: '请操作人签名' })
    expect(w.text()).toContain('添加签名')
    expect(w.text()).toContain('请操作人签名')
  })

  it('DATE 无时间时占位为选择日期', () => {
    const w = mountPreview({ type: 'DATE' })
    expect(w.find('input').attributes('placeholder')).toBe('选择日期')
  })

  it('DATE with_time 时占位为选择日期时间', () => {
    const w = mountPreview({ type: 'DATE', with_time: true })
    expect(w.find('input').attributes('placeholder')).toBe('选择日期时间')
  })

  it('COMMON 显示操作说明提示', () => {
    const w = mountPreview({ type: 'COMMON' })
    expect(w.text()).toContain('通用操作说明型')
  })

  it('NONE 显示无需填写提示', () => {
    const w = mountPreview({ type: 'NONE' })
    expect(w.text()).toContain('无需填写')
  })
})
