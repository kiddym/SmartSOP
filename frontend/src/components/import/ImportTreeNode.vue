<script setup lang="ts">
import type { WizardNode } from '@/utils/importTree'

// 导入向导树审查行（递归）。纯展示 + 冒泡操作事件，树变更由 TreeReviewStep 用纯函数处理。
defineProps<{ node: WizardNode; depth: number; selectedId: string | null; readonly?: boolean }>()
const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'delete', id: string): void
  (e: 'move', id: string, dir: -1 | 1): void
}>()

const TYPE_LABEL = { chapter: '章', content: '容' } as const
</script>

<template>
  <div class="tnode">
    <div
      class="row"
      :class="{ selected: selectedId === node.id, review: node.mark_status === 'review' }"
      :style="{ paddingLeft: `${8 + depth * 18}px` }"
      @click="emit('select', node.id)"
    >
      <el-tag size="small" :type="node.content_type === 'chapter' ? 'primary' : 'info'" disable-transitions>
        {{ TYPE_LABEL[node.content_type] }}
      </el-tag>
      <span class="title" :class="{ empty: !node.title }">
        {{ node.title || '（无标题）' }}
      </span>
      <el-tag v-if="node.mark_status === 'review'" size="small" type="warning" disable-transitions>
        待确认
      </el-tag>
      <el-tag v-if="node.skip_numbering" size="small" disable-transitions>不编号</el-tag>
      <span class="spacer" />
      <span v-if="!readonly" class="ops" @click.stop>
        <el-button text size="small" title="上移" @click="emit('move', node.id, -1)">↑</el-button>
        <el-button text size="small" title="下移" @click="emit('move', node.id, 1)">↓</el-button>
        <el-button text size="small" type="danger" title="删除（含子节点）" @click="emit('delete', node.id)">
          ✕
        </el-button>
      </span>
    </div>
    <ImportTreeNode
      v-for="child in node.children"
      :key="child.id"
      :node="child"
      :depth="depth + 1"
      :selected-id="selectedId"
      :readonly="readonly"
      @select="(id) => emit('select', id)"
      @delete="(id) => emit('delete', id)"
      @move="(id, dir) => emit('move', id, dir)"
    />
  </div>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
}
.row:hover {
  background: #f5f7fa;
}
.row.selected {
  background: #ecf5ff;
}
.row.review {
  background: #fdf6ec;
}
.row.review.selected {
  background: #faecd8;
}
.title {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}
.title.empty {
  color: #c0c4cc;
  font-style: italic;
}
.spacer {
  flex: 1;
}
.ops {
  display: flex;
  gap: 0;
  opacity: 0;
}
.row:hover .ops,
.row.selected .ops {
  opacity: 1;
}
</style>
