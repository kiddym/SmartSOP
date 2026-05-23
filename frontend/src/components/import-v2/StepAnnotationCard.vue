<script setup lang="ts">
defineProps<{ active: boolean }>()
const emit = defineEmits<{ (e: 'clear'): void }>()
</script>

<template>
  <div v-if="active" class="card">
    <el-divider content-position="left">步骤标注</el-divider>
    <el-alert type="warning" :closable="false" show-icon title="此节点已标注为「步骤」，导入后将转换为步骤类型" />
    <div class="actions">
      <el-button size="small" @click="emit('clear')">清除步骤标注</el-button>
    </div>
  </div>
</template>

<style scoped>
.card { padding: 0 16px 16px; }
.actions { margin-top: 12px; }
</style>
