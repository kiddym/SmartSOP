<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ImportDialog from '@/components/import-v2/ImportDialog.vue'

const router = useRouter()
const visible = ref(true)

function onClose(v: boolean): void {
  visible.value = v
  if (!v) void router.push({ name: 'procedure-library' })
}

function onImported(id: string): void {
  void router.push(`/procedures/${id}/edit`)
}
</script>

<template>
  <div>
    <ImportDialog
      :model-value="visible"
      @update:model-value="onClose"
      @imported="onImported"
    />
  </div>
</template>
