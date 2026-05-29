<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import NodeTreePanel from '@/components/editor/NodeTreePanel.vue'
import NodeDetailPanel from '@/components/editor/NodeDetailPanel.vue'
import ProcedureDetailsPanel from '@/components/editor/ProcedureDetailsPanel.vue'
import PublishChecklistDialog from '@/components/editor/PublishChecklistDialog.vue'
import VersionActionDialog, {
  type VersionActionResult,
} from '@/components/version/VersionActionDialog.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { copyProcedure, deleteProcedure, transitionProcedure, upgradeVersion } from '@/api/procedures'
import { formatDateTime } from '@/utils/format'
import AttachmentPanel from '@/components/editor/AttachmentPanel.vue'
import PdfPreviewDialog from '@/components/PdfPreview/PdfPreviewDialog.vue'
import EditorPreviewPane from '@/components/editor/EditorPreviewPane.vue'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import { useSidebar } from '@/composables/useSidebar'
import { useEditorShortcuts } from '@/composables/useEditorShortcuts'
import { shouldAutoCollapse } from '@/utils/editorFocus'
import type { PanelConfig } from '@/utils/collapsiblePanel'

// 统一节点编辑器（B3b-1）：默认（/edit 与 /view）渲染 NodeTreePanel+NodeDetailPanel（绑 nodeEditor）。
// 即时·乐观写：无 Save / dirty / 草稿持久化 / 离开守卫。生命周期与 meta 仍由 procedureEditor（slim）。
const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))
const store = useProcedureEditorStore()
const nodeStore = useNodeEditorStore()
// 键盘快捷键（E1）：撤销/重做 + 设层级；仅可编辑时生效（/view 只读时 no-op）。
useEditorShortcuts({ editable: () => store.editable })

const activeTab = ref<'node' | 'attach' | 'history'>('node')
const publishVisible = ref(false)
const copyVisible = ref(false)
const pdfPreviewVisible = ref(false)
const versionBusy = ref(false)

const sidebar = useSidebar()
const autoCollapsed = ref(false)
const priorCollapsed = ref<boolean | null>(null)
const DETAIL_CFG: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }

// 即时写：结构与 meta 都已落库，PDF 预览直接打开（无需先存）。
function onPreviewPdf(): void {
  pdfPreviewVisible.value = true
}

async function onPublishConfirm(): Promise<void> {
  const p = store.procedure
  if (!p) return
  try {
    await transitionProcedure(p.id, { status: 'PUBLISHED' }, p.revision)
    publishVisible.value = false
    ElMessage.success('已发布')
    await store.reload()
  } catch {
    /* 拦截器已提示 */
  }
}

async function onUpgrade(): Promise<void> {
  const p = store.procedure
  if (!p) return
  try {
    await ElMessageBox.confirm('升级将归档当前版本并创建新草稿版本，是否继续？', '升级版本', {
      type: 'warning',
    })
  } catch {
    return
  }
  versionBusy.value = true
  try {
    const next = await upgradeVersion(p.id)
    ElMessage.success(`已创建 v${next.version} 草稿`)
    await router.push(`/procedures/${next.id}/edit`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

async function onDiscard(): Promise<void> {
  const p = store.procedure
  if (!p) return
  let reason: string
  try {
    const r = await ElMessageBox.prompt('请输入丢弃原因', '丢弃此草稿', {
      inputValidator: (v) => (v && v.trim() ? true : '原因必填'),
      type: 'warning',
    })
    reason = r.value
  } catch {
    return
  }
  versionBusy.value = true
  try {
    const result = await deleteProcedure(p.id, reason)
    if (result) {
      ElMessage.success(`已丢弃草稿，当前版本回到 v${result.new_current_version}`)
      await router.push(`/procedures/${result.new_current_id}`)
    } else {
      ElMessage.success('已删除')
      await router.push({ name: 'procedure-library' })
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

async function onCopyConfirm(payload: VersionActionResult): Promise<void> {
  const p = store.procedure
  if (!p) return
  versionBusy.value = true
  try {
    const copy = await copyProcedure(p.id, {
      target_folder_id: payload.target_folder_id,
      name: payload.name || undefined,
    })
    copyVisible.value = false
    ElMessage.success(`已复制为 ${copy.code}`)
    await router.push(`/procedures/${copy.id}/edit`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

onMounted(async () => {
  await store.load(id.value)
  if (store.loadError) return
  await nodeStore.load(id.value) // 结构（即时·乐观）；在 /edit→/view 重定向前加载，否则复用组件的 /view 实例树为空
  // 访问 /edit 但不可编辑 → 跳只读 /view（不留历史）。
  if (route.name === 'procedure-edit' && !store.editable) {
    void router.replace({ name: 'procedure-view', params: { id: id.value } })
    return
  }

  // Word 导入进入 → 专注模式：自动折叠侧边栏（离开恢复）。
  if (shouldAutoCollapse(route.query.from, sidebar.collapsed.value)) {
    priorCollapsed.value = sidebar.collapsed.value
    sidebar.collapsed.value = true
    autoCollapsed.value = true
    void router.replace({ path: route.path, query: {} })
  }
  watch(
    () => sidebar.collapsed.value,
    () => {
      autoCollapsed.value = false
    },
  )
})

onUnmounted(() => {
  if (autoCollapsed.value) {
    sidebar.collapsed.value = priorCollapsed.value ?? false
  }
})

function goBack(): void {
  void router.push({ name: 'procedure-library' })
}
</script>

<template>
  <div v-loading="store.loading" class="editor">
    <template v-if="store.loadError">
      <el-result icon="error" title="加载失败">
        <template #extra>
          <el-button type="primary" @click="store.load(id)">重试</el-button>
        </template>
      </el-result>
    </template>

    <template v-else-if="store.procedure">
      <EditorTopBar
        @publish="publishVisible = true"
        @back="goBack"
        @upgrade="onUpgrade"
        @discard="onDiscard"
        @copy="copyVisible = true"
        @preview-pdf="onPreviewPdf"
      />

      <el-alert
        v-if="!store.editable"
        type="warning"
        :closable="false"
        show-icon
        class="ro-banner"
        :title="`只读模式：仅当前版本的草稿可编辑（当前 v${store.procedure.version} · ${store.procedure.status}）。`"
      />

      <div class="body">
        <EditorPreviewPane v-if="store.hasSourceDocx" :procedure-id="store.procedure.id" />
        <div class="left">
          <NodeTreePanel :readonly="!store.editable" />
        </div>
        <CollapsiblePanel
          label="节点详情"
          side="right"
          storage-key="smartsop.editor.detail"
          :config="DETAIL_CFG"
        >
          <div class="right-scroll">
            <ProcedureDetailsPanel />
            <el-tabs v-model="activeTab" class="tabs">
              <el-tab-pane label="节点详情" name="node">
                <div class="pane">
                  <NodeDetailPanel :readonly="!store.editable" />
                </div>
              </el-tab-pane>
              <el-tab-pane label="附件" name="attach">
                <AttachmentPanel
                  :procedure-id="store.procedure.id"
                  :editable="store.editable"
                  class="pane"
                />
              </el-tab-pane>
              <el-tab-pane label="版本历史" name="history">
                <el-timeline v-if="store.procedure.version_change_log.length" class="pane">
                  <el-timeline-item
                    v-for="(entry, i) in store.procedure.version_change_log"
                    :key="i"
                    :timestamp="formatDateTime(String(entry.changed_at ?? ''))"
                  >
                    {{ entry.change_type }} — {{ entry.description || '' }}
                  </el-timeline-item>
                </el-timeline>
                <el-empty v-else description="暂无版本记录（回退 / 升级见 Phase 7）" />
              </el-tab-pane>
            </el-tabs>
          </div>
        </CollapsiblePanel>
      </div>

      <PublishChecklistDialog v-model="publishVisible" @confirm="onPublishConfirm" />
      <VersionActionDialog
        v-model="copyVisible"
        title="复制为新程序"
        :need-reason="false"
        :need-folder="true"
        :need-name="true"
        :loading="versionBusy"
        @confirm="onCopyConfirm"
      />
      <PdfPreviewDialog v-model="pdfPreviewVisible" :procedure-id="store.procedure.id" />
    </template>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 0px);
  min-height: 480px;
}
.ro-banner {
  border-radius: 0;
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.left {
  flex: 1;
  min-width: 280px;
  min-height: 0;
}
.right-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.tabs {
  flex: 1;
  padding: 0 14px;
}
.pane {
  padding: 8px 0 40px;
}
</style>
