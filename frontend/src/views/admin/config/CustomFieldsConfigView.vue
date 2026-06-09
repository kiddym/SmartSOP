<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = computed<string>(() => (route.query.tab as string) || 'asset')
function onTabChange(t: string | number): void {
  router.replace({ query: { ...route.query, tab: String(t) } })
}
</script>

<template>
  <div class="config-aggregate">
    <el-tabs :model-value="activeTab" @update:model-value="onTabChange">
      <el-tab-pane label="资产" name="asset" lazy><CustomFieldsView locked-entity="asset" embedded /></el-tab-pane>
      <el-tab-pane label="位置" name="location" lazy><CustomFieldsView locked-entity="location" embedded /></el-tab-pane>
      <el-tab-pane label="备件" name="part" lazy><CustomFieldsView locked-entity="part" embedded /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
</style>
