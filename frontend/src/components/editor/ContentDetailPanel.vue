<script setup lang="ts">
import { computed } from 'vue'
import RichTextEditor from './RichTextEditor.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

// content 节点详情（§4.1）：仅富文本，无标题。
const store = useProcedureEditorStore()
const content = computed(() => store.selectedChapter)
const ro = computed(() => !store.editable)

function onChange(value: string): void {
  const id = content.value?.id
  if (id) store.updateChapterFields(id, { rich_content: value }, `rich:${id}`)
}
</script>

<template>
  <div v-if="content" class="content-detail">
    <div v-if="content.mark_status === 'review' && !ro" class="review-banner">
      <span>⚠ 解析存疑（待确认）——确认结构无误后接受</span>
      <el-button size="small" type="warning" plain @click="store.acceptReview(content.id)">接受待确认</el-button>
    </div>
    <RichTextEditor
      :key="`${content.id}:${ro}`"
      :model-value="content.rich_content"
      variant="full"
      :readonly="ro"
      :procedure-id="store.procedure?.id"
      placeholder="输入内容块正文…"
      @update:model-value="onChange"
    />
  </div>
</template>

<style scoped>
.content-detail {
  height: 100%;
}
.review-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  padding: 6px 10px;
  font-size: 13px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 4px;
}
</style>
