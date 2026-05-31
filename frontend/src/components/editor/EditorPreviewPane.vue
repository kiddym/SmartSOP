<script setup lang="ts">
import { ref, watch } from 'vue'
import WordPreviewPanel from '@/components/shared/WordPreviewPanel.vue'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import { fetchSourceDocx } from '@/api/procedures'
import { PREVIEW_CONFIG } from '@/utils/editorPreview'

const props = defineProps<{ procedureId: string }>()

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const file = ref<File | null>(null)

// 监听 procedureId：组件实例被复用（切换程序）时按新 id 重新拉取，避免预览停留在前一程序。
watch(
  () => props.procedureId,
  async (id) => {
    file.value = null
    const got = await fetchSourceDocx(id)
    if (got) file.value = new File([got.blob], got.filename, { type: DOCX_MIME })
  },
  { immediate: true },
)
</script>

<template>
  <CollapsiblePanel
    v-if="file"
    label="Word 原文预览"
    side="left"
    storage-key="smartsop.editor.preview"
    :config="PREVIEW_CONFIG"
  >
    <WordPreviewPanel :file="file" class="fill-panel" />
  </CollapsiblePanel>
</template>

<style scoped>
.fill-panel {
  flex: 1;
  min-height: 0;
}
</style>
