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
  },
})
