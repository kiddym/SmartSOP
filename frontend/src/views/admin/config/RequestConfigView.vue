<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import RequestFieldsView from '@/views/settings/RequestFieldsView.vue'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = computed<string>(() => (route.query.tab as string) || 'form-fields')
function onTabChange(t: string | number): void {
  router.replace({ query: { ...route.query, tab: String(t) } })
}
</script>

<template>
  <div class="config-aggregate">
    <el-tabs :model-value="activeTab" @update:model-value="onTabChange">
      <el-tab-pane label="表单字段" name="form-fields" lazy><RequestFieldsView /></el-tab-pane>
      <el-tab-pane label="自定义字段" name="custom-fields" lazy>
        <CustomFieldsView locked-entity="request" embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
</style>
