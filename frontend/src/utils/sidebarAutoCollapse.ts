/**
 * 决定路由切换时是否需要对 AppSidebar 自动折叠 / 恢复。
 *
 * 规则：
 * - 用户手动 toggle 过 → 接管，此后所有路由切换均 noop
 * - 进入 /procedures/library → collapse
 * - 离开 /procedures/library → restore
 * - 其他情况 → noop
 *
 * 沿用 editorFocus.ts 的"自动折叠 / 用户接管"模式（spec §C）。
 */
export type CollapseDecision = 'collapse' | 'restore' | 'noop'

const LIBRARY_PATH_PREFIX = '/procedures/library'

function isLibrary(path: string): boolean {
  return path.startsWith(LIBRARY_PATH_PREFIX)
}

export function decideAutoCollapse(
  fromPath: string,
  toPath: string,
  userOverride: boolean,
): CollapseDecision {
  if (userOverride) return 'noop'
  const wasLibrary = isLibrary(fromPath)
  const isLib = isLibrary(toPath)
  if (!wasLibrary && isLib) return 'collapse'
  if (wasLibrary && !isLib) return 'restore'
  return 'noop'
}
