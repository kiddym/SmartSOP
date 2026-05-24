import { describe, expect, it } from 'vitest'
import { collectDeprecatedFieldValues } from '@/utils/editor'
import type { FieldDetailOut } from '@/types/field'

type ArchivedDef = Pick<FieldDetailOut, 'key' | 'name' | 'field_type' | 'options'>

const arch = (over: Partial<ArchivedDef> & { key: string }): ArchivedDef => ({
  name: over.key,
  field_type: 'text',
  options: [],
  ...over,
})

describe('collectDeprecatedFieldValues', () => {
  it('活跃字段的值不计入（在主区已展示）', () => {
    const out = collectDeprecatedFieldValues({ owner: '张三' }, ['owner'], [])
    expect(out).toEqual([])
  })

  it('字段已退役但仍有值 → 用归档字段名作标签', () => {
    const out = collectDeprecatedFieldValues(
      { supplier: '旧供应商' },
      [],
      [arch({ key: 'supplier', name: '供应商' })],
    )
    expect(out).toEqual([{ key: 'supplier', label: '供应商', value: '旧供应商' }])
  })

  it('字段定义已彻底删除 → 标签回退为 key', () => {
    const out = collectDeprecatedFieldValues({ legacy: 'foo' }, [], [])
    expect(out).toEqual([{ key: 'legacy', label: 'legacy', value: 'foo' }])
  })

  it('空值（空串/null/空数组）跳过', () => {
    const out = collectDeprecatedFieldValues(
      { a: '', b: null, c: [], d: '留存' },
      [],
      [],
    )
    expect(out.map((e) => e.key)).toEqual(['d'])
  })

  it('select 值映射为选项标签', () => {
    const out = collectDeprecatedFieldValues(
      { grade: 'a' },
      [],
      [arch({ key: 'grade', name: '等级', field_type: 'select', options: [
        { value: 'a', label: '甲' },
        { value: 'b', label: '乙' },
      ] })],
    )
    expect(out[0].value).toBe('甲')
  })

  it('多选数组 → 选项标签以「, 」连接', () => {
    const out = collectDeprecatedFieldValues(
      { tags: ['x', 'y'] },
      [],
      [arch({ key: 'tags', name: '标签', field_type: 'multi_select', options: [
        { value: 'x', label: 'X' },
        { value: 'y', label: 'Y' },
      ] })],
    )
    expect(out[0].value).toBe('X, Y')
  })
})
