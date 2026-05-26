<script setup lang="ts">
import { computed } from 'vue'
import StatusTag from '@/components/StatusTag.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import type { ProcedureStatus } from '@/types/procedure'

// 编辑器顶栏（§1.1 / Q161）：面包屑 + 状态 chip + 未保存 chip + 主动作按钮组 + ⋮ 更多。
const emit = defineEmits<{
  (e: 'save'): void
  (e: 'publish'): void
  (e: 'back'): void
  (e: 'upgrade'): void
  (e: 'discard'): void
  (e: 'copy'): void
  (e: 'preview-pdf'): void
}>()

const store = useProcedureEditorStore()
const p = computed(() => store.procedure)
const canUndo = computed(() => store.undoStack.length > 0)
const canRedo = computed(() => store.redoStack.length > 0)
const showPublish = computed(() => store.editable)
const showUpgrade = computed(() => !!p.value && p.value.is_current && p.value.status === 'PUBLISHED')
// 丢弃 DRAFT：仅当前版的 v>1 草稿（v1 草稿走整组删除路径，§22.11）。
const showDiscard = computed(
  () => !!p.value && p.value.is_current && p.value.status === 'DRAFT' && p.value.version > 1,
)
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
      <el-tag v-if="store.isDirty" size="small" type="warning">● 未保存</el-tag>
    </div>

    <div v-if="store.editable" class="right">
      <el-button-group>
        <el-button size="small" :disabled="!canUndo" title="撤销大纲结构 (Ctrl+Z) · 类型转换 / 标记应用 不在范围内" @click="store.undo()">↶</el-button>
        <el-button size="small" :disabled="!canRedo" title="重做 (Ctrl+Shift+Z)" @click="store.redo()">↷</el-button>
      </el-button-group>
      <el-button
        size="small"
        :type="store.markMode ? 'primary' : 'default'"
        @click="store.toggleMarkMode()"
      >
        标记模式
      </el-button>
      <el-button size="small" @click="emit('preview-pdf')">PDF 预览</el-button>
      <el-button
        size="small"
        type="success"
        :loading="store.saving"
        :disabled="!store.isDirty"
        @click="emit('save')"
      >
        保存
      </el-button>
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
.code {
  font-weight: 600;
  color: #606266;
}
.name {
  font-weight: 600;
}
.path {
  color: #909399;
  font-size: 12px;
}
.right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
}
</style>
