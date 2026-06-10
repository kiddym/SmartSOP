<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import FieldManageView from '@/views/settings/FieldManageView.vue'
import HeadingRulesView from '@/views/settings/HeadingRulesView.vue'
import FolderManageView from '@/views/folders/FolderManageView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = computed<string>(() => (route.query.tab as string) || 'fields')
function onTabChange(t: string | number): void {
  router.replace({ query: { ...route.query, tab: String(t) } })
}
</script>

<template>
  <div class="config-aggregate">
    <el-tabs :model-value="activeTab" @update:model-value="onTabChange">
      <el-tab-pane label="程序字段" name="fields" lazy><FieldManageView /></el-tab-pane>
      <el-tab-pane label="标题字典" name="heading-rules" lazy><HeadingRulesView /></el-tab-pane>
      <el-tab-pane label="文件夹" name="folders" lazy><FolderManageView /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
</style>
