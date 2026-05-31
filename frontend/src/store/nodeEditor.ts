import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import * as api from '@/api/nodes'
import { isVersionConflict, errorMessage } from '@/api/http'
import type { Node } from '@/types/node'
import { visibleRows, nodeTitle, type TreeRow } from '@/utils/nodeTree'
import { insertSortOrder } from '@/utils/nodeInsert'

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
  _recordMode: 'normal' | 'undoing' | 'redoing' // 撤销/重做录制模式：决定逆操作入哪个栈
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
    _recordMode: 'normal',
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
    canRedo(state): boolean {
      return state.redoStack.length > 0
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

    /**
     * 跨标签 409 冲突的 reload-wins 恢复：全量 re-GET、清空撤销/重做历史、提示用户。
     * 全量 refetch 因为并发修改可能重排兄弟编号；历史里的逆操作引用已失效旧态，必须清空。
     */
    async _recoverFromConflict(id: string): Promise<void> {
      await this._refetch().catch(() => {})
      this.undoStack = []
      this.redoStack = []
      const node = this.nodeMap.get(id)
      const label = node ? nodeTitle(node) : '该节点'
      ElMessage.warning(`「${label}」已被他人修改，已加载最新版本，你刚才的未保存改动已丢弃`)
    },

    _pushUndo(inverse: InverseOp): void {
      if (this._recordMode === 'normal') {
        this.undoStack.push(inverse)
        this.redoStack = [] // 新用户操作令 redo 失效
      } else if (this._recordMode === 'undoing') {
        this.redoStack.push(inverse) // 撤销时捕获 redo
      } else {
        this.undoStack.push(inverse) // 重做时捕获 re-undo（不清 redo）
      }
      if (this.undoStack.length > 100) this.undoStack.shift()
      if (this.redoStack.length > 100) this.redoStack.shift()
    },

    async undo(): Promise<void> {
      const inverse = this.undoStack.pop()
      if (!inverse) return
      this._recordMode = 'undoing'
      try {
        await inverse()
      } catch {
        this.undoStack.push(inverse) // 失败不静默丢弃：重新入栈
        await this._refetch().catch(() => {}) // 与服务端真态对齐（拦截器已提示错误）
      } finally {
        this._recordMode = 'normal'
      }
    },

    async redo(): Promise<void> {
      const inverse = this.redoStack.pop()
      if (!inverse) return
      this._recordMode = 'redoing'
      try {
        await inverse()
      } catch {
        this.redoStack.push(inverse)
        await this._refetch().catch(() => {})
      } finally {
        this._recordMode = 'normal'
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

    /** 批量确认 review（P3：零样式文档逐条确认成本高）。仅取 ids 中仍 review 的节点，
     * 一次 batch 空 change 全部清回 unmarked。不入撤销栈（与单条确认一致）。 */
    async confirmReviewBatch(ids: string[]): Promise<void> {
      if (!this.procedureId) return
      const targets = ids.filter((i) => this.nodeMap.get(i)?.mark_status === 'review')
      if (targets.length === 0) return
      const updates: Record<string, Record<string, never>> = {}
      for (const i of targets) updates[i] = {}
      this.nodes = await api.batchUpdateNodes(this.procedureId, updates)
    },

    async createNode(payload: import('@/types/node').NodeCreate): Promise<void> {
      if (!this.procedureId) return
      const created = await api.createNode(this.procedureId, payload)
      await this._refetch()
      this.selectedId = created.id
      this._pushUndo(() => this.removeNode(created.id))
    },

    /**
     * 行级新增：相对参考节点插入（after-node=紧跟其后，after-subtree=跳过整棵子树）。
     * 委托 createNode 单次写入（保持单条 undo）；相邻无空隙时先 reorder 重排再重算。
     */
    async createRelative(
      refId: string,
      mode: import('@/utils/nodeInsert').InsertMode,
      attrs: Omit<import('@/types/node').NodeCreate, 'sort_order'>,
    ): Promise<void> {
      if (!this.procedureId) return
      let sort = insertSortOrder(this.nodes, refId, mode)
      if (sort === null) {
        await this.reorder(this.nodes.map((x) => x.id)) // 重排至 *1000 等距，恢复空隙
        sort = insertSortOrder(this.nodes, refId, mode)
      }
      await this.createNode({ ...attrs, sort_order: sort ?? undefined })
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
      if (body === node.body) return // 无变化（挂载初始回发 / 空保存 / 防抖重复）不写库、不入撤销栈
      const prevBody = node.body
      let updated: Node
      try {
        updated = await api.patchNode(id, { body }, node.revision)
      } catch (err) {
        if (isVersionConflict(err)) {
          await this._recoverFromConflict(id) // reload-wins
          return
        }
        ElMessage.error(errorMessage(err) ?? '保存失败，请重试')
        throw err // 非冲突瞬时错误：抛出，让 undo()/redo() 重新入栈
      }
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
      let updated: Node
      try {
        updated = await api.patchNode(
          id,
          { input_schema: inputSchema, attachment_marks: attachmentMarks },
          node.revision,
        )
      } catch (err) {
        if (isVersionConflict(err)) {
          await this._recoverFromConflict(id) // reload-wins
          return
        }
        ElMessage.error(errorMessage(err) ?? '保存失败，请重试')
        throw err // 非冲突瞬时错误：抛出，让 undo()/redo() 重新入栈
      }
      this._replaceNode(updated)
      this._pushUndo(() => this.updateForm(id, prevSchema, prevMarks))
    },

    _replaceNode(updated: Node): void {
      const i = this.nodes.findIndex((x) => x.id === updated.id)
      if (i >= 0) this.nodes[i] = updated
    },
  },
})
