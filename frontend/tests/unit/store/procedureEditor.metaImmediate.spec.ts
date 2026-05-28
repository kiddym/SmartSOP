import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { ProcedureMeta } from '@/types/procedure'

const { updateSpy, reloadDetailSpy } = vi.hoisted(() => ({
  updateSpy: vi.fn(),
  reloadDetailSpy: vi.fn(),
}))
// store 顶层 import 的 api/procedures 函数都给 mock，避免真实请求 / import 副作用。
vi.mock('@/api/procedures', () => ({
  updateProcedure: updateSpy,
  fetchProcedureDetail: reloadDetailSpy,
  saveProcedure: vi.fn(),
  applyMarks: vi.fn(),
  applyLayerRolesApi: vi.fn(),
}))

import { useProcedureEditorStore } from '@/store/procedureEditor'

// ProcedureMeta 字段多，只填代码路径用到的，其余 cast 收口。
function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: 'N', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 3, version: 1, status: 'DRAFT', is_current: true,
    version_change_log: [],
    ...over,
  } as unknown as ProcedureMeta
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers()
  updateSpy.mockReset()
  reloadDetailSpy.mockReset()
})
afterEach(() => vi.useRealTimers())

describe('procedureEditor.setMetaField — immediate (debounced) save', () => {
  it('optimistically updates local then flushes FULL meta via updateProcedure after debounce', async () => {
    updateSpy.mockResolvedValue(meta({ revision: 4 }))
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.setMetaField('name', 'New Name')
    expect(store.procedure!.name).toBe('New Name') // optimistic immediately
    expect(updateSpy).not.toHaveBeenCalled() // debounced
    await vi.advanceTimersByTimeAsync(500)
    expect(updateSpy).toHaveBeenCalledTimes(1)
    expect(updateSpy).toHaveBeenCalledWith(
      'p1',
      expect.objectContaining({ name: 'New Name', level_of_use: 'reference' }),
      3,
    )
    expect(store.procedure!.revision).toBe(4) // revision synced from result
  })

  it('coalesces rapid edits into one flush carrying all changed fields', async () => {
    updateSpy.mockResolvedValue(meta({ revision: 4 }))
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.setMetaField('name', 'A')
    store.setMetaField('description', 'D')
    await vi.advanceTimersByTimeAsync(500)
    expect(updateSpy).toHaveBeenCalledTimes(1)
    expect(updateSpy).toHaveBeenCalledWith('p1', expect.objectContaining({ name: 'A', description: 'D' }), 3)
  })

  it('does not flush when not editable', async () => {
    const store = useProcedureEditorStore()
    store.procedure = meta({ status: 'PUBLISHED' }) // editable=false
    store.setMetaField('name', 'X')
    await vi.advanceTimersByTimeAsync(500)
    expect(updateSpy).not.toHaveBeenCalled()
  })
})
