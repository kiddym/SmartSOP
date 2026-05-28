// 编辑器程序级元数据 store（B3b-2 起收窄：结构编辑全部迁至 nodeEditor）。
// 即时·乐观写：setMetaField 改本地 + 防抖 updateProcedure。批量保存/撤销/层级/标记/转换/树结构已删。

import { defineStore } from 'pinia'
import { fetchProcedureDetail, updateProcedure } from '@/api/procedures'
import type { ProcedureFieldView, ProcedureMeta, ProcedureUpdate } from '@/types/procedure'

const META_FLUSH_MS = 500
let metaFlushTimer: ReturnType<typeof setTimeout> | null = null

interface State {
  procedure: ProcedureMeta | null
  hasSourceDocx: boolean
  fields: ProcedureFieldView[]
  loading: boolean
  loadError: boolean
}

export const useProcedureEditorStore = defineStore('procedureEditor', {
  state: (): State => ({
    procedure: null,
    hasSourceDocx: false,
    fields: [],
    loading: false,
    loadError: false,
  }),

  getters: {
    editable(state): boolean {
      return !!state.procedure && state.procedure.is_current && state.procedure.status === 'DRAFT'
    },
    revision(state): number {
      return state.procedure?.revision ?? 0
    },
  },

  actions: {
    async load(id: string): Promise<void> {
      this.loading = true
      this.loadError = false
      try {
        const detail = await fetchProcedureDetail(id)
        this.procedure = detail.procedure
        this.hasSourceDocx = detail.has_source_docx
        this.fields = detail.fields
      } catch {
        this.loadError = true
      } finally {
        this.loading = false
      }
    },

    async reload(): Promise<void> {
      if (this.procedure) await this.load(this.procedure.id)
    },

    // 程序级元字段编辑（详情折叠面板）。即时·乐观写：本地先改 + 防抖 flush。
    setMetaField<K extends keyof ProcedureMeta>(key: K, value: ProcedureMeta[K]): void {
      if (!this.procedure) return
      this.procedure[key] = value
      this._scheduleMetaFlush()
    },

    _scheduleMetaFlush(): void {
      if (metaFlushTimer) clearTimeout(metaFlushTimer)
      metaFlushTimer = setTimeout(() => {
        void this._flushMeta()
      }, META_FLUSH_MS)
    },

    async _flushMeta(): Promise<void> {
      metaFlushTimer = null
      const p = this.procedure
      if (!p || !this.editable) return
      const payload: ProcedureUpdate = {
        name: p.name,
        level_of_use: p.level_of_use,
        description: p.description,
        risk_level: p.risk_level,
        quality_level: p.quality_level,
        custom_values: p.custom_values,
        version_update_notes: p.version_update_notes,
        signoff_enabled: p.signoff_enabled,
      }
      try {
        const updated = await updateProcedure(p.id, payload, p.revision)
        // 只同步 revision，避免冲掉 flush 期间的并发本地编辑。
        if (this.procedure && this.procedure.id === updated.id) this.procedure.revision = updated.revision
      } catch {
        await this.reload()
      }
    },
  },
})
