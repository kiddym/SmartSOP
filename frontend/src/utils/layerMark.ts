export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content' | 'keep'

/** 文档序里参与层级标定的行——含章节与叶子（step / content）。 */
export interface LayerRow {
  id: string
  kind: 'chapter' | 'step' | 'content'
  level: number // chapter 当前层级（叶子行 level=0 占位）
  hasLeafChildren: boolean // 仅 chapter 有意义：挂了步骤/内容块 → 不可降为 content
}

/** 应用层级后单个行的目标归属（tagged union）。
 * to-content 的 chapter 标题由 store.applyLayerRoles 直接从 chapterMap 取，故此处不带 sourceTitle。 */
export type LayerUpdate =
  | { kind: 'reorder'; parent_id: string | null; sort_order: number; level: number }
  | { kind: 'to-content'; parent_id: string | null; sort_order: number }
  | { kind: 'to-chapter'; parent_id: string | null; sort_order: number; level: number }
  | { kind: 'leaf-reparent'; parent_id: string | null; sort_order: number }

/** 默认角色：chapter 用 level 预填；叶子行预填 keep。 */
export function defaultLayerRole(row: LayerRow): LayerRole {
  if (row.kind !== 'chapter') return 'keep'
  const lv = Math.min(3, Math.max(1, row.level))
  return `chapter_${lv}` as LayerRole
}

function roleLevel(role: LayerRole): number {
  return role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
}

function effectiveRole(row: LayerRow, roleMap: Map<string, LayerRole>): LayerRole {
  const role = roleMap.get(row.id) ?? defaultLayerRole(row)
  if (row.kind === 'chapter') {
    // 章节：content 角色受 hasLeafChildren 约束
    if (role === 'content' && row.hasLeafChildren) return defaultLayerRole(row)
    // 章节不可选 'keep'，夹回默认
    if (role === 'keep') return defaultLayerRole(row)
    return role
  }
  // 叶子：'content' 在叶子上无意义，夹回 keep
  if (role === 'content') return 'keep'
  return role
}

/**
 * 由文档序行 + roleMap 算每个章节节点的目标状态。
 *
 * 对于每行，根据其 kind 和 role：
 * - chapter + chapter_X role: reorder（在祖先链允许的最深层级）
 * - chapter + content role: to-content（降级为当前标题下的内容步骤）
 * - leaf + keep: leaf-reparent（挂到最近的标题）
 * - leaf + chapter_X role: to-chapter（提升为章节，夹紧到祖先链能撑得起的层）
 *
 * l1/l2/l3 上下文：chapter_2 无 l1 时夹回根；chapter_3 无 l2 时夹到 l1；
 * content 行不更新上下文（其后代仍挂前一个标题）。
 */
export function computeLayerUpdates(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, LayerUpdate> {
  const out = new Map<string, LayerUpdate>()
  let l1: string | null = null
  let l2: string | null = null
  let l3: string | null = null
  const sortCounter = new Map<string | null, number>()
  const nextSort = (p: string | null): number => {
    const n = sortCounter.get(p) ?? 0
    sortCounter.set(p, n + 1)
    return n
  }

  // 标题级 → 解析出 parent + 实际落定 level（夹紧到祖先链能撑得起的层）
  const placeChapter = (requestedLevel: number): { parent: string | null; level: number } => {
    if (requestedLevel >= 3 && l2) return { parent: l2, level: 3 }
    if (requestedLevel >= 2 && l1) return { parent: l1, level: 2 }
    return { parent: null, level: 1 }
  }

  const setHeadingContext = (id: string, level: number): void => {
    if (level === 1) { l1 = id; l2 = null; l3 = null }
    else if (level === 2) { l2 = id; l3 = null }
    else { l3 = id }
  }

  for (const row of rows) {
    const role = effectiveRole(row, roleMap)

    if (row.kind === 'chapter') {
      if (role === 'content') {
        // 章节降级为当前标题下的内容步骤；不更新 l1/l2/l3 上下文
        const parent = l3 ?? l2 ?? l1
        out.set(row.id, { kind: 'to-content', parent_id: parent, sort_order: nextSort(parent) })
        continue
      }

      // 章节保持为标题（chapter_1/2/3）
      const requested = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
      const { parent, level } = placeChapter(requested)
      setHeadingContext(row.id, level)
      out.set(row.id, { kind: 'reorder', parent_id: parent, sort_order: nextSort(parent), level })
      continue
    }

    // 叶子（step / content）
    if (role === 'keep') {
      const parent = l3 ?? l2 ?? l1
      out.set(row.id, { kind: 'leaf-reparent', parent_id: parent, sort_order: nextSort(parent) })
      continue
    }

    // 叶子提升为章节
    const requested = role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
    const { parent, level } = placeChapter(requested)
    setHeadingContext(row.id, level)
    out.set(row.id, { kind: 'to-chapter', parent_id: parent, sort_order: nextSort(parent), level })
  }

  return out
}

export interface LayerConflict {
  parent_id: string | null
  chapterChildren: string[]
  leafChildren: string[]
}

/**
 * Dry-run §Q25 同级互斥校验。
 *
 * 与后端 layer_apply_service 等价:按 walk 末态 (u.parent_id) 分组。
 * 后端 apply-layer-roles 端点执行同一份 walk 后会落到完全相同的拓扑,
 * 因此前端 dry-run 不会假阳性 / 假阴性。
 */
export function validateLayerQ25(
  _rows: LayerRow[],
  updates: Map<string, LayerUpdate>,
): LayerConflict[] {
  // 算每行的 (endKind, endParent) — apply 完成后的真实归属。
  type End = { kind: 'chapter' | 'leaf'; parent: string | null }
  const endOf = new Map<string, End>()
  for (const [id, u] of updates) {
    switch (u.kind) {
      case 'reorder':       endOf.set(id, { kind: 'chapter', parent: u.parent_id }); break
      case 'to-content':    endOf.set(id, { kind: 'leaf',    parent: u.parent_id }); break
      case 'to-chapter':    endOf.set(id, { kind: 'chapter', parent: u.parent_id }); break
      case 'leaf-reparent': endOf.set(id, { kind: 'leaf',    parent: u.parent_id }); break
    }
  }
  const groups = new Map<string | null, { chapters: string[]; leaves: string[] }>()
  for (const [id, end] of endOf) {
    const g = groups.get(end.parent) ?? { chapters: [], leaves: [] }
    if (end.kind === 'chapter') g.chapters.push(id)
    else g.leaves.push(id)
    groups.set(end.parent, g)
  }
  const conflicts: LayerConflict[] = []
  for (const [parent_id, g] of groups) {
    if (g.chapters.length > 0 && g.leaves.length > 0) {
      conflicts.push({ parent_id, chapterChildren: g.chapters, leafChildren: g.leaves })
    }
  }
  return conflicts
}

/** 「所见即所选」缩进：章节按其落定 level；叶子 keep 缩在当前 heading 下；叶子提升为章节按新 level。 */
export function computeLayerIndents(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  let l1Set = false
  let l2Set = false
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (row.kind === 'chapter') {
      if (role === 'content') {
        // 章节降级为 content 步骤：缩进按当前 heading 下一层；不更新 heading 上下文
        map.set(row.id, headingLevel)
        continue
      }
      // 章节保持标题：夹紧到祖先链能撑得起的层（与 computeLayerUpdates 同算法）
      const requested = roleLevel(role)
      const lv = requested >= 3 && l2Set ? 3 : requested >= 2 && l1Set ? 2 : 1
      map.set(row.id, lv - 1)
      headingLevel = lv
      if (lv === 1) { l1Set = true; l2Set = false }
      else if (lv === 2) { l2Set = true }
      continue
    }
    // 叶子（step / content）
    if (role === 'keep') {
      map.set(row.id, headingLevel)
      continue
    }
    // 叶子提升为章节
    const requested = roleLevel(role)
    const lv = requested >= 3 && l2Set ? 3 : requested >= 2 && l1Set ? 2 : 1
    map.set(row.id, lv - 1)
    headingLevel = lv
    if (lv === 1) { l1Set = true; l2Set = false }
    else if (lv === 2) { l2Set = true }
  }
  return map
}
