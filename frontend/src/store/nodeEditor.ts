import { defineStore } from 'pinia'
import * as api from '@/api/nodes'
import type { Node } from '@/types/node'
import { visibleRows, type TreeRow } from '@/utils/nodeTree'

interface State {
  procedureId: string | null
  nodes: Node[]
  selectedId: string | null
  expanded: Record<string, boolean>
  search: string
  reviewOnly: boolean
  selection: Set<string> // γ 多选（Task 4/5 用）
  loading: boolean
  loadError: boolean
  // 撤销（Task 5）
  undoStack: InverseOp[]
  redoStack: InverseOp[]
  _suppressUndo: boolean // undo 执行期间抑制逆操作自身入栈
}

// 逆操作（Task 5 填充实现；此处先声明类型，store 形状稳定）。
export type InverseOp = () => Promise<void>

export const useNodeEditorStore = defineStore('nodeEditor', {
  state: (): State => ({
    procedureId: null,
    nodes: [],
    selectedId: null,
    expanded: {},
    search: '',
    reviewOnly: false,
    selection: new Set<string>(),
    loading: false,
    loadError: false,
    undoStack: [],
    redoStack: [],
    _suppressUndo: false,
  }),

  getters: {
    rows(state): TreeRow[] {
      return visibleRows(state.nodes, state.expanded, {
        search: state.search,
        reviewOnly: state.reviewOnly,
      })
    },
    nodeMap(state): Map<string, Node> {
      return new Map(state.nodes.map((x) => [x.id, x]))
    },
    reviewCount(state): number {
      return state.nodes.filter((x) => x.mark_status === 'review').length
    },
    selectedNode(state): Node | null {
      return state.selectedId ? this.nodeMap.get(state.selectedId) ?? null : null
    },
    canUndo(state): boolean {
      return state.undoStack.length > 0
    },
  },

  actions: {
    async load(procedureId: string): Promise<void> {
      this.loading = true
      this.loadError = false
      try {
        this.procedureId = procedureId
        this.nodes = await api.listNodes(procedureId)
        this.expanded = {}
        this.selection = new Set()
        this.undoStack = []
        this.redoStack = []
        this.selectedId = this.nodes[0]?.id ?? null
      } catch {
        this.loadError = true
        this.nodes = []
        this.selectedId = null
      } finally {
        this.loading = false
      }
    },

    select(id: string | null): void {
      this.selectedId = id
    },

    toggleExpand(id: string): void {
      // 缺省视为展开，故首次 toggle = 折叠。
      this.expanded[id] = this.expanded[id] === false
    },

    async _refetch(): Promise<void> {
      if (!this.procedureId) return
      this.nodes = await api.listNodes(this.procedureId)
    },

    // 逆操作入栈。undo 执行期间（_suppressUndo）逆操作本身不再入栈。
    _pushUndo(inverse: InverseOp): void {
      if (this._suppressUndo) return
      this.undoStack.push(inverse)
      if (this.undoStack.length > 100) this.undoStack.shift()
    },

    async undo(): Promise<void> {
      const inverse = this.undoStack.pop()
      if (!inverse) return
      this._suppressUndo = true
      try {
        await inverse()
      } finally {
        this._suppressUndo = false
      }
    },

    async setLevel(id: string, level: number | null): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.heading_level ?? null
      this.nodes = await api.batchUpdateNodes(this.procedureId, {
        [id]: { set_heading_level: true, heading_level: level },
      })
      this._pushUndo(() => this.setLevel(id, prev))
    },

    async setKind(id: string, kind: 'node' | 'step'): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.kind ?? 'node'
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: { kind } })
      this._pushUndo(() => this.setKind(id, prev))
    },

    async toggleSkip(id: string): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.skip_numbering ?? false
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: { skip_numbering: !prev } })
      this._pushUndo(() => this.toggleSkip(id))
    },

    async batchSetLevel(ids: string[], level: number | null): Promise<void> {
      if (!this.procedureId || ids.length === 0) return
      const prev = new Map(ids.map((i) => [i, this.nodeMap.get(i)?.heading_level ?? null]))
      const updates: Record<string, { set_heading_level: true; heading_level: number | null }> = {}
      for (const i of ids) updates[i] = { set_heading_level: true, heading_level: level }
      this.nodes = await api.batchUpdateNodes(this.procedureId, updates)
      this._pushUndo(async () => {
        for (const [i, lv] of prev) await this.setLevel(i, lv)
      })
    },

    async batchSetKind(ids: string[], kind: 'node' | 'step'): Promise<void> {
      if (!this.procedureId || ids.length === 0) return
      const prev = new Map(ids.map((i) => [i, this.nodeMap.get(i)?.kind ?? 'node']))
      const updates: Record<string, { kind: 'node' | 'step' }> = {}
      for (const i of ids) updates[i] = { kind }
      this.nodes = await api.batchUpdateNodes(this.procedureId, updates)
      this._pushUndo(async () => {
        for (const [i, k] of prev) await this.setKind(i, k)
      })
    },

    async confirmReview(id: string): Promise<void> {
      if (!this.procedureId) return
      // 空 change → 后端清该节点 review（routers/nodes.py :batch 无条件清 review）。
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: {} })
      // 确认动作不入撤销栈（清 review 不可逆且无害）。
    },

    async createNode(payload: import('@/types/node').NodeCreate): Promise<void> {
      if (!this.procedureId) return
      const created = await api.createNode(this.procedureId, payload)
      await this._refetch()
      this.selectedId = created.id
      this._pushUndo(() => this.removeNode(created.id))
    },

    async removeNode(id: string): Promise<void> {
      if (!this.procedureId) return
      const gone = this.nodeMap.get(id)
      await api.deleteNode(id)
      await this._refetch()
      if (this.selectedId === id) this.selectedId = this.nodes[0]?.id ?? null
      // 删除的撤销 = 重建（新 id，内容/层级/skip 还原；位置近似为末尾）。
      if (gone) {
        this._pushUndo(() =>
          this.createNode({
            body: gone.body,
            heading_level: gone.heading_level,
            kind: gone.kind,
            input_schema: gone.input_schema as import('@/types/node').InputSchema,
            attachment_marks: gone.attachment_marks,
            skip_numbering: gone.skip_numbering,
          }),
        )
      }
    },

    async reorder(orderedIds: string[]): Promise<void> {
      if (!this.procedureId) return
      const prevOrder = this.nodes.map((x) => x.id)
      await api.reorderNodes(this.procedureId, orderedIds)
      await this._refetch()
      this._pushUndo(() => this.reorder(prevOrder))
    },

    async updateBody(id: string, body: string): Promise<void> {
      const node = this.nodeMap.get(id)
      if (!node) return
      const prevBody = node.body
      const updated = await api.patchNode(id, { body }, node.revision)
      this._replaceNode(updated)
      this._pushUndo(() => this.updateBody(id, prevBody))
    },

    async updateForm(
      id: string,
      inputSchema: import('@/types/node').InputSchema,
      attachmentMarks: import('@/types/node').AttachmentMark[],
    ): Promise<void> {
      const node = this.nodeMap.get(id)
      if (!node) return
      const prevSchema = node.input_schema as import('@/types/node').InputSchema
      const prevMarks = node.attachment_marks
      const updated = await api.patchNode(
        id,
        { input_schema: inputSchema, attachment_marks: attachmentMarks },
        node.revision,
      )
      this._replaceNode(updated)
      this._pushUndo(() => this.updateForm(id, prevSchema, prevMarks))
    },

    _replaceNode(updated: Node): void {
      const i = this.nodes.findIndex((x) => x.id === updated.id)
      if (i >= 0) this.nodes[i] = updated
    },
  },
})
