# P3 · 入口统一与下线 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一"新建（空白/从 Word）"入口、两者都进编辑器；"从 Word" 瘦身为轻对话框；下线老向导 + beta2 重对话框；把 3 个共享组件迁出 import-v2。

**Architecture:** 新增 `importFromWord` 编排 + `CreateFromWordDialog`（无 triage）；`ProcedureLibraryView` 统一「新建」下拉、blank-create 跳 `/edit`；删老向导/beta2 全部专用文件 + 路由 + 测试；迁 `WordPreviewPanel`/`ImportSideRail`/`ImportMarkingRow` → `components/shared/`，`ImportMarkingRow` 的 `LayerRole` 改取 `layerMark`，随后删孤立的 `importTree`。纯前端，后端零改。

**Tech Stack:** Vue 3 + TS + Vitest + Element Plus。

**Gate（cwd=`frontend/`）：** `npm run lint && npm run typecheck && npm run test && npm run build`

**安全顺序（每个任务收尾必须 Gate 全绿）：** T1 加新入口 → T2 删旧（保留 3 共享 + importTree）→ T3 迁共享 + 删 importTree。

**上位文档：** `docs/superpowers/specs/2026-05-25-p3-entry-unification-retire-design.md`

---

## 关键事实（实现者必读，含引用图）

- `ProcedureLibraryView.vue`：三按钮（`procedure-import` 老向导 / `procedure-import-v2` beta2 / `createVisible` 新建）；`onCreated(proc)` → `open(id)` → `/procedures/{id}`（**详情**，需改为 `/edit`）。`ProcedureTable @open` 也走 `open(id)` → 详情（**保持不变**，仅改 created 的跳转）。
- `CreateProcedureDialog.vue`：emit `created(proc: ProcedureMeta)`；自身 `createProcedure` 后关闭。
- api（`@/api/parse.ts`）：`uploadDocx(file)→{upload_token}`；`parseDocx(token, mode)→ParseResponse`（`.chapters`）；`importProcedure({name,folder_id,description?,upload_token?,chapters})→ProcedureMeta`。`@/api/folders` `fetchFolderTree()`。
- 路由 `router/index.ts`：删 `procedure-import`、`procedure-import-v2`。
- **3 个共享组件**（`components/import-v2/{WordPreviewPanel,ImportSideRail,ImportMarkingRow}.vue`）当前被：编辑器 `EditorPreviewPane`（WordPreviewPanel+ImportSideRail）、`EditorLayerMarking`（ImportMarkingRow）、待删的 `ImportDialog`、测试 `ImportSideRail.spec`/`ImportMarkingRow.spec` 引用。`ImportMarkingRow` 从 `@/utils/importTree` 取 `LayerRole`（`@/utils/layerMark` 有同名同义类型）。
- **`importTree` 引用者**：全部是待删文件（`useImportDialog`/`useImportWizardPersistence`/import-v2 详情卡片与面板/`ImportDialog`/import 向导步骤/`ImportWizardView`）+ `ImportMarkingRow` + 其测试。解耦 `ImportMarkingRow` 后仅剩自身测试 → 可删。`EditorLayerMarking` 用 `@/utils/layerMark`，**不**依赖 importTree。
- **删除清单（src）**：
  - 老向导：`views/procedures/ImportWizardView.vue`；`components/import/`（`UploadStep`/`ModeStep`/`ReviewReportStep`/`BlockMarkingStep`/`TreeReviewStep`/`ImportFormStep`/`ImportTreeNode`）；`composables/useImportWizardPersistence.ts`；`utils/importBlocks.ts`。
  - beta2：`views/procedures/ImportDialogView.vue`；`components/import-v2/`（`ImportDialog`/`ImportTreePanel`/`ImportDetailPanel`/`ImportTreeRow`/`ChapterDetailCard`/`ContentDetailCard`/`StepAnnotationCard`）；`composables/useImportDialog.ts`；`utils/importCols.ts`。
  - T3 再删：`utils/importTree.ts`。
- **删除清单（测试）**：T2：`BlockMarkingStep.spec`、`importBlocks.spec`、`ImportTreeNode.spec`、`ImportTreeRow.spec`、`ImportTreePanel.spec`、`useImportDialog.spec`、`importWizardPersistence.spec`、`utils/importCols.spec`。T3：`importTree.spec`、`importTreeOps.spec`。
- **提交结尾必带**（harness 规定的合法署名，勿当伪造）：`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## Task 1: 统一「新建」入口 + 从 Word 轻对话框

**Files:** Create `frontend/src/components/CreateFromWordDialog.vue`, `frontend/tests/unit/wordImport.spec.ts`; Modify `frontend/src/api/parse.ts`, `frontend/src/views/procedures/ProcedureLibraryView.vue`

- [ ] **Step 1: 写 `importFromWord` 失败测试**

新建 `frontend/tests/unit/wordImport.spec.ts`：
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const post = vi.fn()
vi.mock('@/api/http', () => ({ http: { post, get: vi.fn() } }))

import { importFromWord } from '@/api/parse'

beforeEach(() => {
  post.mockReset()
  post.mockImplementation((url: string) => {
    if (url === '/uploads') return Promise.resolve({ data: { upload_token: 'tok', filename: 'a.docx' } })
    if (url === '/parse') return Promise.resolve({ data: { chapters: [{ id: 'c', title: 'X' }] } })
    if (url === '/procedures/import') return Promise.resolve({ data: { id: 'p1', code: 'QC-1' } })
    return Promise.reject(new Error('unexpected ' + url))
  })
})

describe('importFromWord', () => {
  it('依次 upload→parse→import，返回新程序', async () => {
    const file = new File(['x'], 'a.docx')
    const proc = await importFromWord(file, 'f1', '我的程序')
    expect(proc.id).toBe('p1')
    const urls = post.mock.calls.map((c) => c[0])
    expect(urls).toEqual(['/uploads', '/parse', '/procedures/import'])
    // import 带上 token + chapters + name + folder
    const body = post.mock.calls[2][1]
    expect(body).toMatchObject({ name: '我的程序', folder_id: 'f1', upload_token: 'tok' })
    expect(body.chapters).toHaveLength(1)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/wordImport.spec.ts`
Expected: FAIL（`importFromWord` 未导出）。

- [ ] **Step 3: 实现 `importFromWord`**

在 `frontend/src/api/parse.ts` 末尾追加（复用已有 `uploadDocx`/`parseDocx`/`importProcedure`）：
```ts
// 从 Word 一步创建草稿：upload→parse→import（triage 移到编辑器，故此处无标定）。
export const importFromWord = async (
  file: File,
  folderId: string,
  name: string,
): Promise<ProcedureMeta> => {
  const up = await uploadDocx(file)
  const parsed = await parseDocx(up.upload_token, 'smart')
  return importProcedure({
    name,
    folder_id: folderId,
    upload_token: up.upload_token,
    chapters: parsed.chapters,
  })
}
```
（`ProcedureMeta` 已在该文件 import；若没有，从 `@/types/procedure` 引入。）

- [ ] **Step 4: 跑测试，确认通过**

Run: `cd frontend && npx vitest run tests/unit/wordImport.spec.ts`
Expected: PASS。

- [ ] **Step 5: 新建 `CreateFromWordDialog.vue`**

`frontend/src/components/CreateFromWordDialog.vue`：
```vue
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchFolderTree } from '@/api/folders'
import { importFromWord } from '@/api/parse'
import type { FolderTreeNode } from '@/types/folder'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'imported', id: string): void
}>()
const visible = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })

interface LeafOption { id: string; label: string }
const leaves = ref<LeafOption[]>([])
const file = ref<File | null>(null)
const form = reactive({ folder_id: '', name: '' })
const phase = ref<'' | 'uploading' | 'parsing' | 'creating'>('')
const busy = computed(() => phase.value !== '')
const phaseText = computed(() =>
  phase.value === 'uploading' ? '上传中…' : phase.value === 'parsing' ? '解析中…' : phase.value === 'creating' ? '创建中…' : '',
)

function collectLeaves(nodes: FolderTreeNode[], acc: LeafOption[]): void {
  for (const n of nodes) {
    if (!n.system && n.children.length === 0 && n.prefix) acc.push({ id: n.id, label: n.full_path })
    if (n.children.length) collectLeaves(n.children, acc)
  }
}
async function loadLeaves(): Promise<void> {
  const acc: LeafOption[] = []
  collectLeaves(await fetchFolderTree(), acc)
  leaves.value = acc
}
watch(visible, (open) => {
  if (open) {
    file.value = null
    form.folder_id = ''
    form.name = ''
    phase.value = ''
    void loadLeaves()
  }
})
function onFile(e: Event): void {
  const f = (e.target as HTMLInputElement).files?.[0] ?? null
  file.value = f
  if (f && !form.name.trim()) form.name = f.name.replace(/\.docx$/i, '')
}
async function submit(): Promise<void> {
  if (!file.value) { ElMessage.warning('请选择 .docx 文件'); return }
  if (!form.folder_id) { ElMessage.warning('请选择目标文件夹'); return }
  if (!form.name.trim()) { ElMessage.warning('请输入程序名称'); return }
  try {
    phase.value = 'uploading'
    const up = await fetchAndImport()
    visible.value = false
    emit('imported', up)
  } catch {
    /* 拦截器已提示；保持打开可重试 */
  } finally {
    phase.value = ''
  }
}
// 分阶段进度（importFromWord 内部连贯执行；此处用 phase 表达大致阶段）
async function fetchAndImport(): Promise<string> {
  phase.value = 'parsing'
  const proc = await importFromWord(file.value as File, form.folder_id, form.name.trim())
  phase.value = 'creating'
  ElMessage.success(`已创建 ${proc.code}`)
  return proc.id
}
</script>

<template>
  <el-dialog v-model="visible" title="从 Word 导入" width="520px">
    <el-form label-width="96px">
      <el-form-item label="Word 文件" required>
        <input type="file" accept=".docx" @change="onFile" />
      </el-form-item>
      <el-form-item label="目标文件夹" required>
        <el-select v-model="form.folder_id" filterable placeholder="仅可存程序的叶子文件夹" class="full">
          <el-option v-for="l in leaves" :key="l.id" :label="l.label" :value="l.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="程序名称" required>
        <el-input v-model="form.name" maxlength="200" placeholder="默认取文件名" />
      </el-form-item>
      <div v-if="busy" class="phase">{{ phaseText }}</div>
    </el-form>
    <template #footer>
      <el-button :disabled="busy" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="submit">导入并编辑</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full { width: 100%; }
.phase { color: #606266; font-size: 13px; padding-left: 96px; }
</style>
```

- [ ] **Step 6: 统一「新建」入口 + blank 跳 /edit**

`frontend/src/views/procedures/ProcedureLibraryView.vue`：
1. import 加：`import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'`
2. `const createVisible = ref(false)` 后加 `const wordVisible = ref(false)`
3. 把 `open`/`onCreated` 改为：blank/word 都进编辑器（行级菜单点击仍走 `open` → 详情，不变）：
```ts
function open(id: string): void {
  void router.push(`/procedures/${id}`)
}
function onCreated(proc: ProcedureMeta): void {
  void router.push(`/procedures/${proc.id}/edit`)
}
function onImported(id: string): void {
  void router.push(`/procedures/${id}/edit`)
}
```
4. 模板 `toolbar-actions` 三按钮替换为统一「新建」下拉：
```html
      <div class="toolbar-actions">
        <el-dropdown trigger="click" @command="(c: string) => (c === 'word' ? (wordVisible = true) : (createVisible = true))">
          <el-button type="primary">新建<el-icon class="el-icon--right"><arrow-down /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="blank">空白程序</el-dropdown-item>
              <el-dropdown-item command="word">从 Word 导入</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
```
（顶部 import `ArrowDown`：`import { ArrowDown } from '@element-plus/icons-vue'`，并在 `<script setup>` 暴露；若项目用全局图标注册，按既有方式。如不确定图标可用，去掉图标只留"新建"文字。）
5. 模板底部对话框：保留 `<CreateProcedureDialog v-model="createVisible" @created="onCreated" />`，新增 `<CreateFromWordDialog v-model="wordVisible" @imported="onImported" />`。

- [ ] **Step 7: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿。（老路由/视图此时仍在，只是 UI 不再引用——保留到 T2 删。）

- [ ] **Step 8: 提交**

```bash
git add frontend/src/api/parse.ts frontend/tests/unit/wordImport.spec.ts frontend/src/components/CreateFromWordDialog.vue frontend/src/views/procedures/ProcedureLibraryView.vue
git commit -m "$(cat <<'EOF'
feat(p3): unified 新建 (blank / from Word) entry, both land in editor

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 下线老向导 + beta2 重对话框

**Files:** 删除（src + tests）见下；Modify `frontend/src/router/index.ts`

- [ ] **Step 1: 删源码**

```bash
cd frontend
git rm \
  src/views/procedures/ImportWizardView.vue \
  src/views/procedures/ImportDialogView.vue \
  src/components/import/UploadStep.vue \
  src/components/import/ModeStep.vue \
  src/components/import/ReviewReportStep.vue \
  src/components/import/BlockMarkingStep.vue \
  src/components/import/TreeReviewStep.vue \
  src/components/import/ImportFormStep.vue \
  src/components/import/ImportTreeNode.vue \
  src/components/import-v2/ImportDialog.vue \
  src/components/import-v2/ImportTreePanel.vue \
  src/components/import-v2/ImportDetailPanel.vue \
  src/components/import-v2/ImportTreeRow.vue \
  src/components/import-v2/ChapterDetailCard.vue \
  src/components/import-v2/ContentDetailCard.vue \
  src/components/import-v2/StepAnnotationCard.vue \
  src/composables/useImportDialog.ts \
  src/composables/useImportWizardPersistence.ts \
  src/utils/importCols.ts \
  src/utils/importBlocks.ts
```
（若 `components/import/` 下还有未列出的步骤文件，一并 `git rm`；先 `ls src/components/import` 核对。）

- [ ] **Step 2: 删对应测试**

```bash
git rm \
  tests/unit/BlockMarkingStep.spec.ts \
  tests/unit/importBlocks.spec.ts \
  tests/unit/ImportTreeNode.spec.ts \
  tests/unit/ImportTreeRow.spec.ts \
  tests/unit/ImportTreePanel.spec.ts \
  tests/unit/useImportDialog.spec.ts \
  tests/unit/importWizardPersistence.spec.ts \
  tests/unit/utils/importCols.spec.ts
```

- [ ] **Step 3: 删路由**

`frontend/src/router/index.ts`：删除 `procedure-import` 与 `procedure-import-v2` 两个 route 记录。

- [ ] **Step 4: grep 验无残留**

Run:
```bash
cd frontend && grep -rn "ImportWizardView\|ImportDialogView\|import-v2/ImportDialog\|components/import/\|useImportDialog\|useImportWizardPersistence\|utils/importCols\|utils/importBlocks\|procedure-import" src tests
```
Expected: 仅可能命中将要在 T3 处理的内容之外**无任何残留**；若有遗漏引用，补删/修正。（注意：此步**不应**再出现对上面已删模块的 import。）

- [ ] **Step 5: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿。此时 `components/import-v2/` 仅剩 3 个共享组件（+ `importTree` 仍被 `ImportMarkingRow` 引用）。`components/import/` 目录应已空（可 `rmdir` 或留待 git 自然移除）。

- [ ] **Step 6: 提交**

```bash
git commit -m "$(cat <<'EOF'
chore(p3): retire old import wizard + beta2 import dialog

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 迁移共享组件 + 删除孤立的 importTree

**Files:** 移动 3 组件；Modify `EditorPreviewPane.vue`、`EditorLayerMarking.vue`、`ImportMarkingRow.vue`、两个测试；删 `importTree.ts` + 两测试

- [ ] **Step 1: 移动 3 个共享组件到 `components/shared/`**

```bash
cd frontend && mkdir -p src/components/shared
git mv src/components/import-v2/WordPreviewPanel.vue src/components/shared/WordPreviewPanel.vue
git mv src/components/import-v2/ImportSideRail.vue src/components/shared/ImportSideRail.vue
git mv src/components/import-v2/ImportMarkingRow.vue src/components/shared/ImportMarkingRow.vue
```

- [ ] **Step 2: 更新引用 + 解耦 LayerRole**

1. `src/components/editor/EditorPreviewPane.vue`：把
   `import WordPreviewPanel from '@/components/import-v2/WordPreviewPanel.vue'` →`@/components/shared/WordPreviewPanel.vue`；
   `import ImportSideRail from '@/components/import-v2/ImportSideRail.vue'` →`@/components/shared/ImportSideRail.vue`。
2. `src/components/editor/EditorLayerMarking.vue`：
   `import ImportMarkingRow from '@/components/import-v2/ImportMarkingRow.vue'` →`@/components/shared/ImportMarkingRow.vue`。
3. `src/components/shared/ImportMarkingRow.vue`：`import type { LayerRole } from '@/utils/importTree'` → `from '@/utils/layerMark'`。
4. 测试：
   - `tests/unit/ImportSideRail.spec.ts`：import 路径 →`@/components/shared/ImportSideRail.vue`。
   - `tests/unit/ImportMarkingRow.spec.ts`：import 路径 →`@/components/shared/ImportMarkingRow.vue`（若它还从 importTree 取 LayerRole，改 layerMark）。

- [ ] **Step 3: 删孤立的 importTree**

先核：`cd frontend && grep -rn "utils/importTree" src tests`
Expected：应**只剩** `tests/unit/importTree.spec.ts`、`tests/unit/importTreeOps.spec.ts`（源码无引用）。确认后：
```bash
git rm src/utils/importTree.ts tests/unit/importTree.spec.ts tests/unit/importTreeOps.spec.ts
```
（若 grep 还显示某 src 文件引用 importTree，说明遗漏，先处理再删。）

- [ ] **Step 4: 清理空目录**

`components/import-v2/` 应已空：`cd frontend && ls src/components/import-v2 2>/dev/null`（空则无文件，git 已随移动/删除清空）。`components/import/` 同理。

- [ ] **Step 5: 前端全量 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿（编辑器从 shared 引用；importTree 已删无残留）。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(p3): relocate shared components to components/shared/, drop importTree

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 收尾

- 最终 Gate：`cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`；后端无改动（可选 `cd backend && .venv/bin/python -m pytest -q` 确认 514 不变）。
- 可选手动冒烟：程序库「新建」→「空白」建程序直接进编辑器；「从 Word 导入」选 docx+文件夹 → 进度 → 进编辑器（带预览栏 + 待确认 + 可层级标定）；旧 `/procedures/import`、`/procedures/import-v2` 已 404。
- 验证草稿（P1 决定 C）：`ProcedureDraftsView` 能删纯草稿（后端已支持）；若缺删除入口，补一个小动作（非必须）。
- 用 superpowers:finishing-a-development-branch 收束 → 统一模型全部落地。

## Self-Review 记录

- **Spec 覆盖**：D1 统一入口 + blank→/edit（T1）；D2 轻对话框（T1 importFromWord + CreateFromWordDialog）；D3 迁移 + LayerRole 解耦（T3）；D4 下线 + 删路由 + 删 importTree（T2/T3）。
- **顺序安全（每任务 Gate 绿）**：T1 仅新增（旧仍在但 UI 不引用）；T2 删旧（3 共享 + importTree 保留，无悬挂）；T3 迁共享 + 删孤立 importTree。
- **占位符**：无；删除步骤给出确切 `git rm` 列表 + grep 验证关。
- **引用闭合**：T2 后 importTree 仅余 ImportMarkingRow + 自身测试；T3 解耦后删除。共享组件 importers（EditorPreviewPane/EditorLayerMarking/2 测试）全部在 T3 改路径。
- **不破坏**：后端零改；行级 `open(id)`→详情不变（仅 created/imported→/edit）；`importFromWord` 复用既有 api。
