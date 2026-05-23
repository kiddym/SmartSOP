<script setup lang="ts">
import { computed, ref } from 'vue'
import ImportTreeNode from './ImportTreeNode.vue'
import {
  applyBatchMark,
  rebuildTreeFromMarks,
  validateMarkedBlocks,
  type MarkRole,
  type MarkedImportBlock,
} from '@/utils/importBlocks'
import { computeChapterNumbers, type WizardNode } from '@/utils/importTree'

const props = defineProps<{ modelValue: MarkedImportBlock[]; file?: File | null }>()
const emit = defineEmits<{ (e: 'update:modelValue', blocks: MarkedImportBlock[]): void }>()

const selected = ref<string[]>([])

const issues = computed(() => validateMarkedBlocks(props.modelValue))
const preview = computed(() => rebuildTreeFromMarks(props.modelValue) as WizardNode[])
const numberMap = computed(() => computeChapterNumbers(preview.value))
const selectedCount = computed(() => selected.value.length)

function checked(id: string): boolean {
  return selected.value.includes(id)
}

function setChecked(id: string, value: boolean): void {
  selected.value = value ? [...new Set([...selected.value, id])] : selected.value.filter((x) => x !== id)
}

function mark(role: MarkRole): void {
  if (!selected.value.length) return
  emit('update:modelValue', applyBatchMark(props.modelValue, selected.value, role))
}

function roleText(role: MarkRole): string {
  if (role === 'chapter_1') return '一级'
  if (role === 'chapter_2') return '二级'
  if (role === 'chapter_3') return '三级'
  if (role === 'ignored') return '忽略'
  return '正文'
}

function issueFor(id: string): string {
  return issues.value.find((i) => i.block_id === id)?.message ?? ''
}
</script>

<template>
  <div class="marking-step">
    <div class="toolbar">
      <span class="hint">已选 {{ selectedCount }} 项</span>
      <span class="spacer" />
      <el-button size="small" @click="mark('chapter_1')">一级章节</el-button>
      <el-button size="small" @click="mark('chapter_2')">二级章节</el-button>
      <el-button size="small" @click="mark('chapter_3')">三级章节</el-button>
      <el-button size="small" @click="mark('content')">正文</el-button>
      <el-button size="small" @click="mark('ignored')">忽略</el-button>
    </div>

    <el-alert
      v-if="issues.some((i) => i.level === 'error')"
      class="banner"
      type="error"
      :closable="false"
      show-icon
      title="存在层级错误，请修正后再继续导入。"
    />
    <el-alert
      v-else-if="issues.some((i) => i.level === 'warning')"
      class="banner"
      type="warning"
      :closable="false"
      show-icon
      title="存在章节前正文，确认不需要导入时可标为忽略。"
    />

    <div class="panes">
      <div class="blocks">
        <div v-for="block in modelValue" :key="block.id" class="block-row" :class="{ ignored: block.assigned_role === 'ignored' }">
          <el-checkbox :model-value="checked(block.id)" @update:model-value="(v: boolean) => setChecked(block.id, v)" />
          <el-tag size="small" disable-transitions>{{ roleText(block.assigned_role) }}</el-tag>
          <span class="block-text">{{ block.display_text || '（空块）' }}</span>
          <el-tag v-if="block.has_word_numbering" size="small" type="info" disable-transitions>Word编号</el-tag>
          <el-tag v-if="block.mark_status === 'review'" size="small" type="warning" disable-transitions>待确认</el-tag>
          <span v-if="issueFor(block.id)" class="issue">{{ issueFor(block.id) }}</span>
        </div>
      </div>

      <div class="preview">
        <div class="preview-title">导入后树预览</div>
        <template v-if="preview.length">
          <ImportTreeNode
            v-for="node in preview"
            :key="node.id"
            :node="node"
            :depth="0"
            :selected-id="null"
            :readonly="true"
            :number-map="numberMap"
          />
        </template>
        <el-empty v-else description="暂无章节树" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.marking-step {
  padding: 8px 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.hint {
  color: #606266;
  font-size: 13px;
}
.spacer {
  flex: 1;
}
.banner {
  margin-bottom: 12px;
}
.panes {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
  gap: 14px;
  min-height: 360px;
}
.blocks,
.preview {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: auto;
  max-height: 520px;
}
.block-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
}
.block-row.ignored {
  color: #909399;
  background: #fafafa;
}
.block-text {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.issue {
  color: #f56c6c;
  font-size: 12px;
}
.preview {
  padding: 10px;
}
.preview-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
}
</style>
