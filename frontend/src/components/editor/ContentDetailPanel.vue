<script setup lang="ts">
import { computed } from 'vue'
import RichTextEditor from './RichTextEditor.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

// 内容块详情：kind='content' 的步骤。
// 新定义：content = title?（可选） + rich_content；step = content + 结构化字段（表单/附件）。
// 因此本面板暴露 title（可空）+ 富文本两栏；与 StepDetailPanel 共享 title 字段，仅省去结构化区。
const store = useProcedureEditorStore()
const content = computed(() => store.selectedStep)
const ro = computed(() => !store.editable)

function onTitleChange(value: string): void {
  const id = content.value?.id
  if (id) store.updateStepFields(id, { title: value }, `title:${id}`)
}

function onChange(value: string): void {
  const id = content.value?.id
  if (id) store.updateStepFields(id, { content: value }, `content:${id}`)
}
</script>

<template>
  <div v-if="content" class="content-detail">
    <el-input
      :model-value="content.title"
      :disabled="ro"
      maxlength="500"
      placeholder="内容块标题（可选）"
      data-test="content-title"
      class="content-title"
      @input="onTitleChange"
    />
    <RichTextEditor
      :key="`${content.id}:${ro}`"
      :model-value="content.content"
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
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.content-title {
  flex: 0 0 auto;
}
</style>
