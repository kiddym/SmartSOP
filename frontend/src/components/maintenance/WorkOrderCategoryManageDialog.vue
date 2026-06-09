<script setup lang="ts">
import WorkOrderCategoryManagePanel from './WorkOrderCategoryManagePanel.vue'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'update:visible', v: boolean): void; (e: 'changed'): void }>()
function close() { emit('update:visible', false) }
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    title="管理分类"
    width="560px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <WorkOrderCategoryManagePanel v-if="props.visible" @changed="emit('changed')" />

    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>
