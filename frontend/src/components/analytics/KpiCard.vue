<script setup lang="ts">
defineProps<{ label: string; value: string | number; unit?: string; hint?: string }>()
</script>

<template>
  <el-card class="kpi" shadow="never">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value">
      {{ value }}<span v-if="unit" class="kpi-unit">{{ unit }}</span>
    </div>
    <div v-if="hint" class="kpi-hint">{{ hint }}</div>
  </el-card>
</template>

<style scoped>
.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.kpi-value {
  font-size: 24px;
  font-weight: 600;
  margin-top: 4px;
}
.kpi-unit {
  font-size: 13px;
  font-weight: 400;
  margin-left: 4px;
  color: var(--el-text-color-secondary);
}
.kpi-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
