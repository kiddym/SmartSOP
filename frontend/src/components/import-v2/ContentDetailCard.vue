<script setup lang="ts">
import type { WizardNode } from '@/utils/importTree'

defineProps<{
  node: WizardNode
  parent: { id: string; title: string; number: string } | null
}>()
const emit = defineEmits<{
  (e: 'accept-review'): void
  (e: 'select-parent', id: string): void
}>()
</script>

<template>
  <div class="card">
    <div class="head">
      <div class="badge">📄 内容块</div>
      <div v-if="parent" class="ref" @click="emit('select-parent', parent.id)">
        归属：{{ parent.number }} {{ parent.title || '(无标题)' }}
      </div>
    </div>

    <el-divider content-position="left">内容预览（只读）</el-divider>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div class="preview" v-html="node.rich_content || '<i>（空内容）</i>'" />

    <div v-if="node.mark_status === 'review'" class="actions">
      <el-button size="small" type="warning" plain @click="emit('accept-review')">✓ 接受待确认</el-button>
    </div>
  </div>
</template>

<style scoped>
.card { padding: 16px; }
.badge { display: inline-block; padding: 2px 8px; background: #f4f4f5; color: #909399; border-radius: 4px; font-size: 12px; }
.ref { margin-top: 6px; font-size: 13px; color: #409eff; cursor: pointer; }
.ref:hover { text-decoration: underline; }
.preview { border: 1px dashed #dcdfe6; border-radius: 4px; padding: 12px; max-height: 380px; overflow: auto; font-size: 13px; }
.preview :deep(img) { max-width: 100%; }
.actions { margin-top: 12px; }
</style>
