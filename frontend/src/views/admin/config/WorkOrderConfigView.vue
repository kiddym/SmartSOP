<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import WorkOrderFieldsView from '@/views/settings/WorkOrderFieldsView.vue'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'
import WorkOrderCategoryManagePanel from '@/components/maintenance/WorkOrderCategoryManagePanel.vue'
import TimeCategoryManagePanel from '@/components/workorder/TimeCategoryManagePanel.vue'
import CostCategoryManagePanel from '@/components/workorder/CostCategoryManagePanel.vue'

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
      <el-tab-pane label="表单字段" name="form-fields" lazy><WorkOrderFieldsView /></el-tab-pane>
      <el-tab-pane label="自定义字段" name="custom-fields" lazy>
        <CustomFieldsView locked-entity="work_order" embedded />
      </el-tab-pane>
      <el-tab-pane label="工单分类" name="categories" lazy><WorkOrderCategoryManagePanel /></el-tab-pane>
      <el-tab-pane label="工时分类" name="time-categories" lazy><TimeCategoryManagePanel /></el-tab-pane>
      <el-tab-pane label="成本分类" name="cost-categories" lazy><CostCategoryManagePanel /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
</style>
