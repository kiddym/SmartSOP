<script setup lang="ts">
import { computed, ref } from 'vue'
import StatusTag from '@/components/StatusTag.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { ProcedureStatus } from '@/types/procedure'

// 编辑器顶栏（B3b-1）：面包屑 + 状态 + 撤销（nodeEditor）+ autosave 指示 + 生命周期按钮。
// 即时·乐观写：无 Save / dirty。
const emit = defineEmits<{
  (e: 'publish'): void
  (e: 'back'): void
  (e: 'upgrade'): void
  (e: 'discard'): void
  (e: 'copy'): void
  (e: 'preview-pdf'): void
}>()

const store = useProcedureEditorStore()
const node = useNodeEditorStore()
const p = computed(() => store.procedure)
const showPublish = computed(() => store.editable)
const showUpgrade = computed(() => !!p.value && p.value.is_current && p.value.status === 'PUBLISHED')
const showDiscard = computed(
  () => !!p.value && p.value.is_current && p.value.status === 'DRAFT' && p.value.version > 1,
)

// autosave 指示：$onAction 计 nodeEditor mutating actions（复制自退役的 NodeEditorView）。
const inflight = ref(0)
const saving = ref(false)
const MUTATING = new Set([
  'setLevel', 'setKind', 'toggleSkip', 'batchSetLevel', 'batchSetKind',
  'confirmReview', 'createNode', 'removeNode', 'reorder', 'updateBody', 'updateForm', 'undo',
])
node.$onAction(({ name, after, onError }) => {
  if (!MUTATING.has(name)) return
  inflight.value++
  saving.value = true
  const done = (): void => {
    inflight.value = Math.max(0, inflight.value - 1)
    if (inflight.value === 0) saving.value = false
  }
  after(done)
  onError(done)
})
</script>

<template>
  <div class="topbar">
    <div class="left">
      <el-button text size="small" @click="emit('back')">← 返回</el-button>
      <span class="code">{{ p?.code }}</span>
      <span class="name">{{ p?.name }}</span>
      <span class="path">{{ p?.folder_full_path }}</span>
      <StatusTag v-if="p" :status="p.status as ProcedureStatus" />
      <el-tag v-if="p" size="small" type="info">v{{ p.version }}</el-tag>
    </div>

    <div v-if="store.editable" class="right">
      <el-button class="etb-undo" size="small" :disabled="!node.canUndo" title="撤销 (节点编辑)" @click="node.undo()">↶ 撤销</el-button>
      <span class="etb-save" :class="{ 'is-saving': saving }">{{ saving ? '保存中…' : '✓ 已保存' }}</span>
      <el-button size="small" @click="emit('preview-pdf')">PDF 预览</el-button>
      <el-button v-if="showPublish" size="small" type="primary" @click="emit('publish')">发布</el-button>
      <el-button v-if="showUpgrade" size="small" @click="emit('upgrade')">升级版本</el-button>
      <el-dropdown trigger="click">
        <el-button size="small" text>⋮</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-if="showDiscard" @click="emit('discard')">丢弃此 DRAFT</el-dropdown-item>
            <el-dropdown-item @click="emit('copy')">复制为新程序</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: var(--el-bg-color, #fff);
}
.left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
}
.code { font-weight: 600; color: #606266; }
.name { font-weight: 600; }
.path { color: #909399; font-size: 12px; }
.right { display: flex; align-items: center; gap: 8px; flex: none; }
.etb-save { font-size: 12px; color: #67c23a; }
.etb-save.is-saving { color: #909399; }
</style>
