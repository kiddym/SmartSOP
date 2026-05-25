/** 进入编辑页是否应自动折叠侧边栏：仅当来自 Word 导入且侧边栏当前展开。 */
export function shouldAutoCollapse(fromQuery: unknown, currentCollapsed: boolean): boolean {
  return fromQuery === 'import' && currentCollapsed === false
}
