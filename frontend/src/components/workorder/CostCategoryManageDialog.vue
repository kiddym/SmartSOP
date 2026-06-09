<script setup lang="ts">
import { ref } from 'vue'
import CostCategoryManagePanel from './CostCategoryManagePanel.vue'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const panelRef = ref<InstanceType<typeof CostCategoryManagePanel> | null>(null)

function close() {
  emit('update:visible', false)
}

defineExpose({
  openCreate: (...a: unknown[]) => panelRef.value?.openCreate(...a as []),
  openEdit: (...a: unknown[]) => panelRef.value?.openEdit(...a as [Parameters<InstanceType<typeof CostCategoryManagePanel>['openEdit']>[0]]),
  submitForm: () => panelRef.value?.submitForm(),
  handleDelete: (...a: unknown[]) => panelRef.value?.handleDelete(...a as [Parameters<InstanceType<typeof CostCategoryManagePanel>['handleDelete']>[0]]),
  get form() {
    return panelRef.value?.form
  },
})
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    title="管理成本分类"
    width="560px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <CostCategoryManagePanel
      v-if="props.visible"
      ref="panelRef"
      @changed="emit('changed')"
    />
    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>
