import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { ProcedureMeta } from '@/types/procedure'

const { detailSpy } = vi.hoisted(() => ({ detailSpy: vi.fn() }))
vi.mock('@/api/procedures', () => ({
  fetchProcedureDetail: detailSpy,
  updateProcedure: vi.fn(),
}))

import { useProcedureEditorStore } from '@/store/procedureEditor'

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: 'N', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 1, version: 1, status: 'DRAFT', is_current: true,
    version_change_log: [],
    ...over,
  } as unknown as ProcedureMeta
}

beforeEach(() => {
  setActivePinia(createPinia())
  detailSpy.mockReset()
})

describe('procedureEditor (slim meta store, B3b-2)', () => {
  it('load() populates procedure/hasSourceDocx/fields from detail', async () => {
    detailSpy.mockResolvedValue({ procedure: meta(), has_source_docx: true, fields: [{ id: 'f1' }] })
    const store = useProcedureEditorStore()
    await store.load('p1')
    expect(store.procedure?.id).toBe('p1')
    expect(store.hasSourceDocx).toBe(true)
    expect(store.fields).toHaveLength(1)
    expect(store.loadError).toBe(false)
  })

  it('load() sets loadError on failure', async () => {
    detailSpy.mockRejectedValue(new Error('boom'))
    const store = useProcedureEditorStore()
    await store.load('p1')
    expect(store.loadError).toBe(true)
    expect(store.procedure).toBeNull()
  })

  it('editable is true only for current DRAFT', async () => {
    const store = useProcedureEditorStore()
    store.procedure = meta({ status: 'DRAFT', is_current: true })
    expect(store.editable).toBe(true)
    store.procedure = meta({ status: 'PUBLISHED', is_current: true })
    expect(store.editable).toBe(false)
    store.procedure = meta({ status: 'DRAFT', is_current: false })
    expect(store.editable).toBe(false)
  })

  it('reload() re-fetches the current procedure', async () => {
    detailSpy.mockResolvedValue({ procedure: meta({ name: 'fresh' }), has_source_docx: false, fields: [] })
    const store = useProcedureEditorStore()
    store.procedure = meta({ name: 'stale' })
    await store.reload()
    expect(detailSpy).toHaveBeenCalledWith('p1')
    expect(store.procedure?.name).toBe('fresh')
  })
})
