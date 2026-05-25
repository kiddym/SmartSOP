<script setup lang="ts">
import { onMounted, ref } from 'vue'
import WordPreviewPanel from '@/components/shared/WordPreviewPanel.vue'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import { fetchSourceDocx } from '@/api/procedures'
import { PREVIEW_CONFIG } from '@/utils/editorPreview'

const props = defineProps<{ procedureId: string }>()

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const file = ref<File | null>(null)

onMounted(async () => {
  const got = await fetchSourceDocx(props.procedureId)
  if (!got) return
  file.value = new File([got.blob], got.filename, { type: DOCX_MIME })
})
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
