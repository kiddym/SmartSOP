<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AxiosError } from 'axios'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import ChapterTreePanel from '@/components/editor/ChapterTreePanel.vue'
import ChapterDetailPanel from '@/components/editor/ChapterDetailPanel.vue'
import ContentDetailPanel from '@/components/editor/ContentDetailPanel.vue'
import StepDetailPanel from '@/components/editor/StepDetailPanel.vue'
import ProcedureDetailsPanel from '@/components/editor/ProcedureDetailsPanel.vue'
import PublishChecklistDialog from '@/components/editor/PublishChecklistDialog.vue'
import VersionActionDialog, {
  type VersionActionResult,
} from '@/components/version/VersionActionDialog.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useEditorPersistence } from '@/composables/useEditorPersistence'
import { useEditorKeyboard } from '@/composables/useEditorKeyboard'
import { copyProcedure, deleteProcedure, transitionProcedure, upgradeVersion } from '@/api/procedures'
import { formatDateTime } from '@/utils/format'
import AttachmentPanel from '@/components/editor/AttachmentPanel.vue'
import EditorPreviewPane from '@/components/editor/EditorPreviewPane.vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))
const store = useProcedureEditorStore()
const persistence = useEditorPersistence(store, id.value)

const activeTab = ref<'node' | 'attach' | 'history'>('node')
const publishVisible = ref(false)
const copyVisible = ref(false)
const versionBusy = ref(false)
const leavingViaAction = ref(false) // 版本动作触发的跳转：绕过未保存守卫
const treeRef = ref<InstanceType<typeof ChapterTreePanel> | null>(null)

const kind = computed<'chapter' | 'content' | 'step' | null>(() => {
  const sid = store.selectedId
  if (!sid) return null
  const c = store.chapterMap.get(sid)
  if (c) return c.content_type === 'content' ? 'content' : 'chapter'
  return store.stepMap.has(sid) ? 'step' : null
})

function errCode(e: unknown): string | undefined {
  return (e as AxiosError<{ detail?: { code?: string } }>).response?.data?.detail?.code
}

async function doSave(): Promise<void> {
  if (!store.isDirty) return
  const errors = store.validateForSave()
  if (errors.length) {
    ElMessage.error(`请先修复：${errors.join('；')}`)
    return
  }
  try {
    await store.save()
    persistence.clear()
    ElMessage.success('已保存')
  } catch (e) {
    if (errCode(e) === 'VERSION_CONFLICT') {
      try {
        await ElMessageBox.confirm('远程版本已被其他人修改。加载远程最新版本（放弃本地未保存改动）？', '版本冲突', {
          confirmButtonText: '加载远程',
          cancelButtonText: '取消',
          type: 'warning',
        })
        await store.reload()
        persistence.clear()
      } catch {
        /* 用户取消，保留本地 */
      }
    }
    /* 其他错误由拦截器提示，保留 dirty */
  }
}

async function onPublishConfirm(): Promise<void> {
  const p = store.procedure
  if (!p) return
  try {
    await transitionProcedure(p.id, { status: 'PUBLISHED' }, p.revision)
    publishVisible.value = false
    persistence.clear()
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
    leavingViaAction.value = true
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
    persistence.clear()
    leavingViaAction.value = true
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
    leavingViaAction.value = true
    ElMessage.success(`已复制为 ${copy.code}`)
    await router.push(`/procedures/${copy.id}/edit`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

async function onDeleteSelected(): Promise<void> {
  const sid = store.selectedId
  if (!sid || !store.editable) return
  try {
    await store.deleteNode(sid)
    ElMessage.success('已删除')
  } catch {
    /* 拦截器已提示 */
  }
}

useEditorKeyboard({
  onSave: () => void doSave(),
  onUndo: () => store.undo(),
  onRedo: () => store.redo(),
  onFocusSearch: () => treeRef.value?.focusSearch(),
  onDelete: () => void onDeleteSelected(),
  onEsc: () => {
    if (store.markMode) store.toggleMarkMode()
  },
  onPromote: () => {
    const id = store.selectedId
    if (id && store.editable) void store.promoteChapter(id)
  },
  onDemote: () => {
    const id = store.selectedId
    if (id && store.editable) void store.demoteChapter(id)
  },
})

onMounted(async () => {
  await store.load(id.value)
  if (store.loadError) return
  // 路由守卫：访问 /edit 但不可编辑 → 跳只读 /view（不留历史）。
  if (route.name === 'procedure-edit' && !store.editable) {
    void router.replace({ name: 'procedure-view', params: { id: id.value } })
    return
  }
  await persistence.tryRestore()
  persistence.start()
})

onBeforeRouteLeave(async () => {
  if (leavingViaAction.value) {
    return true // 升级 / 丢弃 / 复制 触发的跳转，本地草稿已按需保留或清除
  }
  if (!store.isDirty) {
    persistence.clear()
    return true
  }
  try {
    await ElMessageBox.confirm('有未保存的修改，离开前是否保存？', '未保存修改', {
      confirmButtonText: '保存并离开',
      cancelButtonText: '直接离开',
      distinguishCancelAndClose: true,
      type: 'warning',
    })
    await doSave()
    return true
  } catch (action) {
    if (action === 'cancel') {
      persistence.clear()
      return true // 直接离开
    }
    return false // 关闭弹框 → 留在页面
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
        @save="doSave"
        @publish="publishVisible = true"
        @back="goBack"
        @upgrade="onUpgrade"
        @discard="onDiscard"
        @copy="copyVisible = true"
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
        <EditorPreviewPane :procedure-id="store.procedure.id" />
        <div class="left">
          <ChapterTreePanel ref="treeRef" />
        </div>
        <div class="right">
          <ProcedureDetailsPanel />
          <el-tabs v-model="activeTab" class="tabs">
            <el-tab-pane label="节点详情" name="node">
              <div class="pane">
                <ChapterDetailPanel v-if="kind === 'chapter'" :key="store.selectedId ?? 'none'" />
                <ContentDetailPanel v-else-if="kind === 'content'" :key="store.selectedId ?? 'none'" />
                <StepDetailPanel v-else-if="kind === 'step'" :key="store.selectedId ?? 'none'" />
                <el-empty v-else description="选择左侧节点进行编辑" />
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
  width: 340px;
  flex: none;
  min-height: 0;
}
.right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
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
