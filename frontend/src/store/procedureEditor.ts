// 编辑器集中状态（§17.2-17.3 / Q153-Q155）。
//
// 变更模型：
//   · 批量/本地/可撤销（经 PUT 保存）：新增、改字段、跳号、同级上下移 → 进脏集 + undo 快照。
//   · 立即后端（确认 + 先存待存改动 + 同步）：删除已存节点、5 种转换、apply-marks、跨 parent 移动。
// 编号 code 用 utils.recomputeCodes 客户端镜像实时预览；保存用 id_map 就地改名，避免整页刷新。

import { defineStore } from 'pinia'
import { fetchProcedureDetail, saveProcedure, applyMarks } from '@/api/procedures'
import {
  convertChapterToStep,
  convertRootToStep,
  contentToSteps as contentToStepsApi,
  deleteChapter as deleteChapterApi,
  moveChapter as moveChapterApi,
  setChapterMarkStatus,
} from '@/api/chapters'
import { convertStepToChapter, deleteStep as deleteStepApi, moveStep as moveStepApi } from '@/api/steps'
import {
  computeFallback,
  formatCode,
  genTempId,
  getAddButtonState,
  isTempId,
  recomputeCodes,
} from '@/utils/editor'
import { computeLayerUpdates, type LayerRole, type LayerRow } from '@/utils/layerMark'
import type {
  AddButtonState,
  ChapterTreeNode,
  ContentType,
  EditorChapter,
  EditorStep,
  FlatRow,
  FormType,
  InputSchema,
  MarkStatus,
  NodeKind,
  StepOut,
} from '@/types/node'
import type { ProcedureFieldView, ProcedureMeta, ProcedureSaveIn } from '@/types/procedure'

const MAX_UNDO = 50
const COALESCE_MS = 800
const CONTENT_MAX_BYTES = 5 * 1024 * 1024 // 富文本总量上限（CONTENT_TOO_LARGE，§8.2）

function byteLength(s: string): number {
  return typeof TextEncoder !== 'undefined' ? new TextEncoder().encode(s).length : s.length
}

function titleFromHtml(html: string): string {
  const text = html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return text.slice(0, 80) || '未命名章节'
}

interface Snapshot {
  chapters: EditorChapter[]
  steps: EditorStep[]
  dirtyChapters: string[]
  dirtySteps: string[]
  metaDirty: boolean
}

// sessionStorage 草稿的完整可恢复状态（§7）。
export interface EditorDraftState {
  procedure: ProcedureMeta | null
  chapters: EditorChapter[]
  steps: EditorStep[]
  selectedId: string | null
  expanded: Record<string, boolean>
  dirtyChapters: string[]
  dirtySteps: string[]
  metaDirty: boolean
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function emptyStep(chapterId: string | null, sortOrder: number): EditorStep {
  return {
    id: genTempId(),
    chapter_id: chapterId,
    title: '',
    content: '',
    input_schema: { type: 'COMMON' },
    attachment_marks: [],
    skip_numbering: false,
    sort_order: sortOrder,
  }
}

function ingestChapters(tree: ChapterTreeNode[]): EditorChapter[] {
  const out: EditorChapter[] = []
  const walk = (nodes: ChapterTreeNode[], parentId: string | null): void => {
    for (const n of nodes) {
      out.push({
        id: n.id,
        parent_id: parentId,
        content_type: n.content_type,
        title: n.title,
        rich_content: n.rich_content,
        skip_numbering: n.skip_numbering,
        mark_status: n.mark_status,
        sort_order: n.sort_order,
      })
      walk(n.children, n.id)
    }
  }
  walk(tree, null)
  return out
}

function ingestStep(s: StepOut): EditorStep {
  return {
    id: s.id,
    chapter_id: s.chapter_id,
    title: s.title,
    content: s.content,
    input_schema: s.input_schema,
    attachment_marks: s.attachment_marks,
    skip_numbering: s.skip_numbering,
    sort_order: s.sort_order,
  }
}

// patch 是否真的改动了目标的任一字段（含数组/对象，按值比较），用于跳过空操作。
function patchChangesAnything(target: Record<string, unknown>, patch: Record<string, unknown>): boolean {
  return Object.keys(patch).some((k) => JSON.stringify(target[k]) !== JSON.stringify(patch[k]))
}

interface State {
  procedure: ProcedureMeta | null
  hasSourceDocx: boolean
  fields: ProcedureFieldView[]
  chapters: EditorChapter[]
  steps: EditorStep[]
  selectedId: string | null
  expanded: Record<string, boolean>
  dirtyChapters: Set<string>
  dirtySteps: Set<string>
  metaDirty: boolean
  markMode: boolean
  layerMode: boolean
  loading: boolean
  saving: boolean
  loadError: boolean
  undoStack: Snapshot[]
  redoStack: Snapshot[]
  lastUndoTag: string | null
  lastUndoAt: number
}

export const useProcedureEditorStore = defineStore('procedureEditor', {
  state: (): State => ({
    procedure: null,
    hasSourceDocx: false,
    fields: [],
    chapters: [],
    steps: [],
    selectedId: null,
    expanded: {},
    dirtyChapters: new Set<string>(),
    dirtySteps: new Set<string>(),
    metaDirty: false,
    markMode: false,
    layerMode: false,
    loading: false,
    saving: false,
    loadError: false,
    undoStack: [],
    redoStack: [],
    lastUndoTag: null,
    lastUndoAt: 0,
  }),

  getters: {
    editable(state): boolean {
      return !!state.procedure && state.procedure.is_current && state.procedure.status === 'DRAFT'
    },
    isDirty(state): boolean {
      return state.dirtyChapters.size > 0 || state.dirtySteps.size > 0 || state.metaDirty
    },
    revision(state): number {
      return state.procedure?.revision ?? 0
    },
    chapterMap(state): Map<string, EditorChapter> {
      return new Map(state.chapters.map((c) => [c.id, c]))
    },
    stepMap(state): Map<string, EditorStep> {
      return new Map(state.steps.map((s) => [s.id, s]))
    },
    codeMaps(state) {
      return recomputeCodes(state.chapters, state.steps)
    },
    // 章节编号层级（1-based，仅 chapter/content；step 不参与）。
    levelMap(state): Map<string, number> {
      const byParent = new Map<string | null, EditorChapter[]>()
      for (const c of state.chapters) {
        const list = byParent.get(c.parent_id) ?? []
        list.push(c)
        byParent.set(c.parent_id, list)
      }
      const levels = new Map<string, number>()
      const walk = (parentId: string | null, level: number): void => {
        for (const c of byParent.get(parentId) ?? []) {
          levels.set(c.id, level)
          walk(c.id, level + 1)
        }
      }
      walk(null, 1)
      return levels
    },
    // 文档序章节/正文行（层级标定面板数据源）。
    layerRows(): LayerRow[] {
      const levels = this.levelMap
      const hasStep = new Set(this.steps.map((s) => s.chapter_id))
      const byParent = new Map<string | null, EditorChapter[]>()
      for (const c of this.chapters) {
        const g = byParent.get(c.parent_id) ?? []
        g.push(c)
        byParent.set(c.parent_id, g)
      }
      const cmp = (a: EditorChapter, b: EditorChapter): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const rows: LayerRow[] = []
      const walk = (parent: string | null): void => {
        for (const c of [...(byParent.get(parent) ?? [])].sort(cmp)) {
          rows.push({
            id: c.id,
            content_type: c.content_type,
            level: levels.get(c.id) ?? 1,
            hasStepChildren: hasStep.has(c.id),
          })
          walk(c.id)
        }
      }
      walk(null)
      return rows
    },
    // 某 parent 直接子节点的类型集合（Q25）；parentId=null 表示根级。
    childKindsOf(): (parentId: string | null) => NodeKind[] {
      return (parentId: string | null): NodeKind[] => {
        const kinds: NodeKind[] = []
        for (const c of this.chapters) {
          if (c.parent_id === parentId) kinds.push(c.content_type === 'content' ? 'content' : 'chapter')
        }
        for (const s of this.steps) {
          if (s.chapter_id === parentId) kinds.push('step')
        }
        return kinds
      }
    },
    addButtonStateFor(): (parentId: string | null) => AddButtonState {
      return (parentId: string | null): AddButtonState => getAddButtonState(this.childKindsOf(parentId))
    },
    selectedChapter(state): EditorChapter | null {
      return state.selectedId ? (this.chapterMap.get(state.selectedId) ?? null) : null
    },
    selectedStep(state): EditorStep | null {
      return state.selectedId ? (this.stepMap.get(state.selectedId) ?? null) : null
    },
    markedNodes(state): EditorChapter[] {
      return state.chapters.filter((c) => c.mark_status === 'step' || c.mark_status === 'content')
    },
    // 扁平 DFS 行（尊重 expanded）；树渲染 / 虚拟滚动 / 搜索过滤的统一单元。
    flatRows(state): FlatRow[] {
      const chByParent = new Map<string | null, EditorChapter[]>()
      for (const c of state.chapters) {
        const list = chByParent.get(c.parent_id) ?? []
        list.push(c)
        chByParent.set(c.parent_id, list)
      }
      const stByChapter = new Map<string | null, EditorStep[]>()
      for (const s of state.steps) {
        const list = stByChapter.get(s.chapter_id) ?? []
        list.push(s)
        stByChapter.set(s.chapter_id, list)
      }
      const cmp = (a: { sort_order: number; id: string }, b: { sort_order: number; id: string }): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      for (const g of chByParent.values()) g.sort(cmp)
      for (const g of stByChapter.values()) g.sort(cmp)

      const { chapterCodes, stepCodes } = this.codeMaps
      const levels = this.levelMap
      const rows: FlatRow[] = []

      const walk = (parentId: string | null, depth: number): void => {
        for (const ch of chByParent.get(parentId) ?? []) {
          const kind: NodeKind = ch.content_type === 'content' ? 'content' : 'chapter'
          const level = levels.get(ch.id) ?? 1
          const hasChildChapters = (chByParent.get(ch.id)?.length ?? 0) > 0
          const hasChildSteps = (stByChapter.get(ch.id)?.length ?? 0) > 0
          const hasChildren = kind === 'chapter' && (hasChildChapters || hasChildSteps)
          rows.push({
            id: ch.id,
            kind,
            depth,
            parent_id: ch.parent_id,
            title: ch.title,
            code: formatCode({ kind, level, code: chapterCodes.get(ch.id) ?? '', skipNumbering: ch.skip_numbering }),
            skip_numbering: ch.skip_numbering,
            mark_status: ch.mark_status,
            form_type: null,
            has_children: hasChildren,
            expanded: state.expanded[ch.id] ?? false,
            fallback: computeFallback(kind, ch.rich_content),
          })
          if (hasChildren && (state.expanded[ch.id] ?? false)) walk(ch.id, depth + 1)
        }
        for (const st of stByChapter.get(parentId) ?? []) {
          rows.push({
            id: st.id,
            kind: 'step',
            depth,
            parent_id: st.chapter_id,
            title: st.title,
            code: formatCode({ kind: 'step', level: 0, code: stepCodes.get(st.id) ?? '', skipNumbering: st.skip_numbering }),
            skip_numbering: st.skip_numbering,
            mark_status: 'unmarked',
            form_type: (st.input_schema?.type ?? 'COMMON') as FormType,
            has_children: false,
            expanded: false,
            fallback: computeFallback('step', st.content),
          })
        }
      }
      walk(null, 0)
      return rows
    },
  },

  actions: {
    // ---- 加载 ---- //
    async load(id: string): Promise<void> {
      this.loading = true
      this.loadError = false
      try {
        const detail = await fetchProcedureDetail(id)
        this.procedure = detail.procedure
        this.hasSourceDocx = detail.has_source_docx
        this.fields = detail.fields
        this.chapters = ingestChapters(detail.chapters)
        this.steps = detail.steps.map(ingestStep)
        this.resetEditState()
        this.expandAll()
        this.selectedId = this.firstNodeId()
      } catch {
        this.loadError = true
      } finally {
        this.loading = false
      }
    },

    resetEditState(): void {
      this.dirtyChapters = new Set()
      this.dirtySteps = new Set()
      this.metaDirty = false
      this.undoStack = []
      this.redoStack = []
      this.lastUndoTag = null
    },

    firstNodeId(): string | null {
      return this.flatRows[0]?.id ?? null
    },

    expandAll(): void {
      const next: Record<string, boolean> = {}
      for (const c of this.chapters) if (c.content_type === 'chapter') next[c.id] = true
      this.expanded = next
    },

    selectNode(id: string | null): void {
      this.selectedId = id
    },

    setExpanded(id: string, value: boolean): void {
      this.expanded = { ...this.expanded, [id]: value }
    },

    toggleExpanded(id: string): void {
      this.setExpanded(id, !(this.expanded[id] ?? false))
    },

    // ---- undo 快照 ---- //
    pushUndo(tag?: string): void {
      const now = Date.now()
      if (tag && tag === this.lastUndoTag && now - this.lastUndoAt < COALESCE_MS) {
        this.lastUndoAt = now
        return
      }
      this.undoStack.push(this.snapshot())
      if (this.undoStack.length > MAX_UNDO) this.undoStack.shift()
      this.redoStack = []
      this.lastUndoTag = tag ?? null
      this.lastUndoAt = now
    },

    snapshot(): Snapshot {
      return {
        chapters: clone(this.chapters),
        steps: clone(this.steps),
        dirtyChapters: [...this.dirtyChapters],
        dirtySteps: [...this.dirtySteps],
        metaDirty: this.metaDirty,
      }
    },

    restore(snap: Snapshot): void {
      this.chapters = clone(snap.chapters)
      this.steps = clone(snap.steps)
      this.dirtyChapters = new Set(snap.dirtyChapters)
      this.dirtySteps = new Set(snap.dirtySteps)
      this.metaDirty = snap.metaDirty
      if (this.selectedId && !this.chapterMap.has(this.selectedId) && !this.stepMap.has(this.selectedId)) {
        this.selectedId = this.firstNodeId()
      }
    },

    undo(): void {
      const snap = this.undoStack.pop()
      if (!snap) return
      this.redoStack.push(this.snapshot())
      this.restore(snap)
      this.lastUndoTag = null
    },

    redo(): void {
      const snap = this.redoStack.pop()
      if (!snap) return
      this.undoStack.push(this.snapshot())
      this.restore(snap)
      this.lastUndoTag = null
    },

    // ---- 本地编辑（脏 + 可撤销） ---- //
    updateChapterFields(id: string, patch: Partial<EditorChapter>, undoTag?: string): void {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      if (!patchChangesAnything(ch as unknown as Record<string, unknown>, patch)) return // 空操作不置脏、不入撤销栈
      this.pushUndo(undoTag)
      Object.assign(ch, patch)
      this.dirtyChapters.add(id)
    },

    updateStepFields(id: string, patch: Partial<EditorStep>, undoTag?: string): void {
      const st = this.stepMap.get(id)
      if (!st) return
      if (!patchChangesAnything(st as unknown as Record<string, unknown>, patch)) return // 空操作（如编辑器回发等值内容）不置脏、不入撤销栈
      this.pushUndo(undoTag)
      Object.assign(st, patch)
      this.dirtySteps.add(id)
    },

    setStepFormType(id: string, type: FormType): void {
      const st = this.stepMap.get(id)
      if (!st) return
      this.pushUndo()
      st.input_schema = { type } as InputSchema
      this.dirtySteps.add(id)
    },

    toggleSkipNumbering(id: string): void {
      const ch = this.chapterMap.get(id)
      if (ch) {
        this.updateChapterFields(id, { skip_numbering: !ch.skip_numbering })
        return
      }
      const st = this.stepMap.get(id)
      if (st) this.updateStepFields(id, { skip_numbering: !st.skip_numbering })
    },

    toggleContentType(id: string): void {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      const wasReview = ch.mark_status === 'review'
      const next: ContentType = ch.content_type === 'chapter' ? 'content' : 'chapter'
      this.updateChapterFields(id, { content_type: next }, `content_type:${id}`)
      if (wasReview) void this.setMark(id, 'unmarked')
    },

    promoteContentToChapter(id: string): void {
      const ch = this.chapterMap.get(id)
      if (!ch || ch.content_type !== 'content') return
      const hasChildren =
        this.chapters.some((c) => c.parent_id === id) ||
        this.steps.some((s) => s.chapter_id === id)
      if (hasChildren) return

      this.pushUndo()
      const originalHtml = ch.rich_content
      const childId = genTempId()
      const child: EditorChapter = {
        id: childId,
        parent_id: id,
        content_type: 'content',
        title: '',
        rich_content: originalHtml,
        skip_numbering: true,
        mark_status: 'unmarked',
        sort_order: 0,
      }
      ch.content_type = 'chapter'
      ch.title = ch.title.trim() || titleFromHtml(originalHtml)
      ch.rich_content = ''
      ch.skip_numbering = false
      this.chapters.push(child)
      this.dirtyChapters.add(id)
      this.dirtyChapters.add(childId)
      this.setExpanded(id, true)
      this.selectedId = id
    },

    nextSortOrder(siblings: { sort_order: number }[]): number {
      return siblings.reduce((m, s) => Math.max(m, s.sort_order), -1) + 1
    },

    addChapterNode(parentId: string | null, contentType: ContentType): string {
      this.pushUndo()
      const siblings = this.chapters.filter((c) => c.parent_id === parentId)
      const node: EditorChapter = {
        id: genTempId(),
        parent_id: parentId,
        content_type: contentType,
        title: '',
        rich_content: '',
        skip_numbering: false,
        mark_status: 'unmarked',
        sort_order: this.nextSortOrder(siblings),
      }
      this.chapters.push(node)
      this.dirtyChapters.add(node.id)
      if (parentId) this.setExpanded(parentId, true)
      this.selectedId = node.id
      return node.id
    },

    addStepNode(chapterId: string | null): string {
      this.pushUndo()
      const siblings = this.steps.filter((s) => s.chapter_id === chapterId)
      const node = emptyStep(chapterId, this.nextSortOrder(siblings))
      this.steps.push(node)
      this.dirtySteps.add(node.id)
      if (chapterId) this.setExpanded(chapterId, true)
      this.selectedId = node.id
      return node.id
    },

    // 同级上下移（reorder）：在节点所属分组内交换 sort_order。
    reorder(id: string, dir: 'up' | 'down'): void {
      const ch = this.chapterMap.get(id)
      if (ch) {
        const group = this.chapters
          .filter((c) => c.parent_id === ch.parent_id)
          .sort((a, b) => a.sort_order - b.sort_order)
        this.swapInGroup(group, id, dir)
        return
      }
      const st = this.stepMap.get(id)
      if (st) {
        const group = this.steps
          .filter((s) => s.chapter_id === st.chapter_id)
          .sort((a, b) => a.sort_order - b.sort_order)
        this.swapInGroup(group, id, dir)
      }
    },

    swapInGroup(group: { id: string; sort_order: number }[], id: string, dir: 'up' | 'down'): void {
      const idx = group.findIndex((n) => n.id === id)
      const target = dir === 'up' ? idx - 1 : idx + 1
      if (idx < 0 || target < 0 || target >= group.length) return
      this.pushUndo()
      const a = group[idx]
      const b = group[target]
      const tmp = a.sort_order
      a.sort_order = b.sort_order
      b.sort_order = tmp
      const dirtyA = this.chapterMap.has(a.id) ? this.dirtyChapters : this.dirtySteps
      const dirtyB = this.chapterMap.has(b.id) ? this.dirtyChapters : this.dirtySteps
      dirtyA.add(a.id)
      dirtyB.add(b.id)
    },

    // 同 parent 重排到任意 targetIndex（拖拽 reorder，本地可撤销）；重写整组 sort_order = 0..n。
    reorderWithin(id: string, targetIndex: number): void {
      const ch = this.chapterMap.get(id)
      const isChapter = !!ch
      const parentKey = isChapter ? ch!.parent_id : this.stepMap.get(id)?.chapter_id ?? null
      const cmp = (a: EditorChapter | EditorStep, b: EditorChapter | EditorStep): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const group: (EditorChapter | EditorStep)[] = isChapter
        ? [...this.chapters.filter((c) => c.parent_id === parentKey)].sort(cmp)
        : [...this.steps.filter((s) => s.chapter_id === parentKey)].sort(cmp)
      const from = group.findIndex((n) => n.id === id)
      if (from < 0) return
      this.pushUndo()
      const [moved] = group.splice(from, 1)
      const clamped = Math.max(0, Math.min(targetIndex, group.length))
      group.splice(clamped, 0, moved)
      const dirty = isChapter ? this.dirtyChapters : this.dirtySteps
      group.forEach((n, i) => {
        n.sort_order = i
        dirty.add(n.id)
      })
    },

    // 删除已存节点的纯本地副作用（在后端 DELETE 成功后调用，或对临时节点直接调用）。
    removeNodeLocal(id: string): void {
      const ch = this.chapterMap.get(id)
      if (ch) {
        const ids = this.collectSubtree(id)
        this.chapters = this.chapters.filter((c) => !ids.has(c.id))
        this.steps = this.steps.filter((s) => !(s.chapter_id && ids.has(s.chapter_id)))
        for (const x of ids) {
          this.dirtyChapters.delete(x)
          delete this.expanded[x]
        }
      } else {
        this.steps = this.steps.filter((s) => s.id !== id)
        this.dirtySteps.delete(id)
      }
      if (this.selectedId && !this.chapterMap.has(this.selectedId) && !this.stepMap.has(this.selectedId)) {
        this.selectedId = this.firstNodeId()
      }
    },

    collectSubtree(rootId: string): Set<string> {
      const ids = new Set<string>([rootId])
      let changed = true
      while (changed) {
        changed = false
        for (const c of this.chapters) {
          if (c.parent_id && ids.has(c.parent_id) && !ids.has(c.id)) {
            ids.add(c.id)
            changed = true
          }
        }
      }
      return ids
    },

    // 删除节点：临时节点纯本地（可撤销）；已存节点先存待存改动再调 DELETE，然后整树同步。
    async deleteNode(id: string): Promise<void> {
      if (isTempId(id)) {
        this.pushUndo()
        this.removeNodeLocal(id)
        return
      }
      const map = await this.ensureSaved()
      const real = map[id] ?? id
      if (this.chapterMap.has(real)) await deleteChapterApi(real)
      else await deleteStepApi(real)
      await this.reload()
    },

    // ---- 立即后端转换 / 移动 / 标记（不可撤销，先存待存改动） ---- //
    // 返回 id_map：调用方据此把可能仍是临时的 id 解析为真实 id。
    async ensureSaved(): Promise<Record<string, string>> {
      return this.isDirty ? await this.save() : {}
    },

    async reload(): Promise<void> {
      if (!this.procedure) return
      const keep = this.selectedId
      const keepExpanded = { ...this.expanded }
      await this.load(this.procedure.id)
      // 保留用户的展开/折叠意图（仅对仍存在的章节），不被 load() 的 expandAll 覆盖。
      this.expanded = Object.fromEntries(
        Object.entries(keepExpanded).filter(([k]) => this.chapterMap.has(k)),
      )
      if (keep && (this.chapterMap.has(keep) || this.stepMap.has(keep))) this.selectedId = keep
    },

    async convertToStep(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await convertChapterToStep(map[id] ?? id)
      await this.reload()
    },
    async convertRootToStep(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await convertRootToStep(map[id] ?? id)
      await this.reload()
    },
    async contentToSteps(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await contentToStepsApi(map[id] ?? id)
      await this.reload()
    },
    async convertToChapter(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await convertStepToChapter(map[id] ?? id)
      await this.reload()
    },

    canPromoteChapter(id: string): boolean {
      const ch = this.chapterMap.get(id)
      return !!(ch && ch.parent_id)
    },

    canDemoteChapter(id: string): boolean {
      const ch = this.chapterMap.get(id)
      if (!ch) return false
      const siblings = this.chapters
        .filter((c) => c.parent_id === ch.parent_id)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      const myIdx = siblings.findIndex((c) => c.id === id)
      if (myIdx <= 0) return false
      return siblings[myIdx - 1].content_type === 'chapter'
    },

    async moveCrossParent(id: string, targetParentId: string | null, targetIndex: number): Promise<void> {
      const map = await this.ensureSaved()
      const realId = map[id] ?? id
      const realParent = targetParentId ? (map[targetParentId] ?? targetParentId) : null
      if (this.chapterMap.has(realId)) {
        await moveChapterApi(realId, { target_parent_id: realParent, target_index: targetIndex })
      } else {
        await moveStepApi(realId, { target_chapter_id: realParent, target_index: targetIndex })
      }
      await this.reload()
    },

    async promoteChapter(id: string): Promise<void> {
      if (!this.canPromoteChapter(id)) return
      const wasReview = this.chapterMap.get(id)?.mark_status === 'review'
      const ch = this.chapterMap.get(id)!
      const parent = this.chapterMap.get(ch.parent_id!)!
      const grandParentId = parent.parent_id
      // 找到 parent 在其兄弟中的排序位置，把当前节点插到 parent 之后
      const parentSiblings = this.chapters
        .filter((c) => c.parent_id === grandParentId)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      const parentIdx = parentSiblings.findIndex((c) => c.id === parent.id)
      await this.moveCrossParent(id, grandParentId, parentIdx + 1)
      if (wasReview) await this.setMark(id, 'unmarked')
    },

    async demoteChapter(id: string): Promise<void> {
      if (!this.canDemoteChapter(id)) return
      const wasReview = this.chapterMap.get(id)?.mark_status === 'review'
      const ch = this.chapterMap.get(id)!
      const siblings = this.chapters
        .filter((c) => c.parent_id === ch.parent_id)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      const myIdx = siblings.findIndex((c) => c.id === id)
      const prevSibling = siblings[myIdx - 1]
      const prevChildren = this.chapters.filter((c) => c.parent_id === prevSibling.id)
      await this.moveCrossParent(id, prevSibling.id, prevChildren.length)
      if (wasReview) await this.setMark(id, 'unmarked')
    },

    // ---- 标记模式 / 层级标定模式（互斥） ---- //
    toggleMarkMode(): void {
      this.markMode = !this.markMode
      if (this.markMode) this.layerMode = false
    },
    toggleLayerMode(): void {
      this.layerMode = !this.layerMode
      if (this.layerMode) this.markMode = false
    },
    applyLayerRoles(roleMap: Map<string, LayerRole>): void {
      const updates = computeLayerUpdates(this.layerRows, roleMap)
      this.pushUndo('layer')
      const clearReview: string[] = []
      for (const [id, u] of updates) {
        const ch = this.chapterMap.get(id)
        if (!ch) continue
        // 应用层级=对结构的刻意确认，连带清待确认（与 toggleContentType/promote/demote 一致）。
        if (ch.mark_status === 'review') clearReview.push(id)
        ch.parent_id = u.parent_id
        ch.content_type = u.content_type
        ch.sort_order = u.sort_order
        this.dirtyChapters.add(id)
      }
      this.layerMode = false
      for (const id of clearReview) void this.setMark(id, 'unmarked')
    },

    // 设置单节点 mark_status。调用方须保证 id 为真实 id（临时节点先 ensureSaved 解析）；
    // isTempId 为后端 404 兜底：临时节点只改本地、不发请求（apply-marks 读 DB，故必须先持久化）。
    async setMark(id: string, status: MarkStatus): Promise<void> {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      const prev = ch.mark_status
      ch.mark_status = status
      if (isTempId(id)) return
      try {
        await setChapterMarkStatus(id, status)
      } catch {
        ch.mark_status = prev
      }
    },

    // 接受单个待确认：清 review（保留解析判定的类型/结构）。
    async acceptReview(id: string): Promise<void> {
      await this.setMark(id, 'unmarked')
    },

    // 接受全部待确认。
    async acceptAllReviews(): Promise<void> {
      await this.ensureSaved()
      const ids = this.chapters.filter((c) => c.mark_status === 'review').map((c) => c.id)
      for (const id of ids) await this.setMark(id, 'unmarked')
    },

    async cycleMark(id: string): Promise<void> {
      // 先保存待存改动，把可能的临时 id 解析为真实 id，再写后端（避免 404 + 标记静默丢失）。
      const map = await this.ensureSaved()
      const real = map[id] ?? id
      const ch = this.chapterMap.get(real)
      if (!ch) return
      const order: MarkStatus[] = ['unmarked', 'step', 'content']
      const idx = order.indexOf(ch.mark_status === 'review' ? 'unmarked' : ch.mark_status)
      await this.setMark(real, order[(idx + 1) % order.length])
    },

    async applyAllMarks(): Promise<void> {
      await this.ensureSaved()
      await applyMarks(this.procedure!.id)
      this.markMode = false
      await this.reload()
    },

    // 程序级元字段编辑（详情折叠面板）。不进 undo 栈（undo 聚焦树结构）。
    setMetaField<K extends keyof ProcedureMeta>(key: K, value: ProcedureMeta[K]): void {
      if (!this.procedure) return
      this.procedure[key] = value
      this.metaDirty = true
    },

    // ---- sessionStorage 草稿（§7：导出 / 导入完整可恢复状态） ---- //
    exportDraft(): EditorDraftState {
      return {
        procedure: clone(this.procedure),
        chapters: clone(this.chapters),
        steps: clone(this.steps),
        selectedId: this.selectedId,
        expanded: { ...this.expanded },
        dirtyChapters: [...this.dirtyChapters],
        dirtySteps: [...this.dirtySteps],
        metaDirty: this.metaDirty,
      }
    },

    importDraft(d: EditorDraftState): void {
      if (d.procedure) this.procedure = clone(d.procedure)
      this.chapters = clone(d.chapters)
      this.steps = clone(d.steps)
      this.selectedId = d.selectedId
      this.expanded = { ...d.expanded }
      this.dirtyChapters = new Set(d.dirtyChapters)
      this.dirtySteps = new Set(d.dirtySteps)
      this.metaDirty = d.metaDirty
      this.undoStack = []
      this.redoStack = []
      this.lastUndoTag = null
    },

    // ---- 客户端保存预校验（§8.2） ---- //
    validateForSave(): string[] {
      const errors: string[] = []
      const emptyChapters = this.chapters.filter(
        (c) => c.content_type === 'chapter' && !c.title.trim(),
      ).length
      if (emptyChapters > 0) errors.push(`有 ${emptyChapters} 个章节标题为空`)
      const oversized = [...this.chapters.filter((c) => c.content_type === 'content'), ...this.steps].filter(
        (n) => byteLength('rich_content' in n ? n.rich_content : n.content) > CONTENT_MAX_BYTES,
      ).length
      if (oversized > 0) errors.push(`有 ${oversized} 个节点正文超过 5MB`)
      return errors
    },

    // ---- 保存（PUT 整批；id_map 就地改名） ---- //
    buildPayload(): ProcedureSaveIn {
      const p = this.procedure!
      const chapters = [...this.dirtyChapters]
        .map((id) => this.chapterMap.get(id))
        .filter((c): c is EditorChapter => !!c)
        .map((c) => ({
          id: c.id,
          parent_id: c.parent_id,
          content_type: c.content_type,
          title: c.title,
          rich_content: c.content_type === 'content' ? c.rich_content : '',
          skip_numbering: c.skip_numbering,
          sort_order: c.sort_order,
        }))
      const steps = [...this.dirtySteps]
        .map((id) => this.stepMap.get(id))
        .filter((s): s is EditorStep => !!s)
        .map((s) => ({
          id: s.id,
          chapter_id: s.chapter_id,
          title: s.title,
          content: s.content,
          input_schema: s.input_schema,
          attachment_marks: s.attachment_marks,
          skip_numbering: s.skip_numbering,
          sort_order: s.sort_order,
        }))
      return {
        name: p.name,
        level_of_use: p.level_of_use,
        description: p.description,
        risk_level: p.risk_level,
        quality_level: p.quality_level,
        custom_values: p.custom_values,
        version_update_notes: p.version_update_notes,
        signoff_enabled: p.signoff_enabled,
        chapters,
        steps,
        deleted_chapter_ids: [],
        deleted_step_ids: [],
      }
    },

    applyIdMap(idMap: Record<string, string>): void {
      const remap = (id: string | null): string | null => (id && idMap[id] ? idMap[id] : id)
      for (const c of this.chapters) {
        c.id = remap(c.id) as string
        c.parent_id = remap(c.parent_id)
      }
      for (const s of this.steps) {
        s.id = remap(s.id) as string
        s.chapter_id = remap(s.chapter_id)
      }
      const nextExpanded: Record<string, boolean> = {}
      for (const [k, v] of Object.entries(this.expanded)) nextExpanded[(idMap[k] ?? k) as string] = v
      this.expanded = nextExpanded
      this.selectedId = remap(this.selectedId)
    },

    async save(): Promise<Record<string, string>> {
      if (!this.procedure || !this.editable) return {}
      this.saving = true
      try {
        const result = await saveProcedure(this.procedure.id, this.buildPayload(), this.revision)
        this.applyIdMap(result.id_map)
        const { id_map: idMap, ...meta } = result
        this.procedure = meta as ProcedureMeta
        this.resetEditState()
        return idMap
      } finally {
        this.saving = false
      }
    },
  },
})
