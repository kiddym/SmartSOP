<script setup lang="ts">
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'
import type { ProcedureRow } from '@/types/procedure'

defineProps<{ rows: ProcedureRow[]; loading?: boolean }>()
const emit = defineEmits<{ (e: 'open', id: string): void }>()
</script>

<template>
  <el-table
    v-loading="loading"
    :data="rows"
    stripe
    @row-click="(row: ProcedureRow) => emit('open', row.id)"
  >
    <!-- mono 数据列：编号/版本/日期 走等宽字体（docs/design-system.md §2.2）。
         class-name 落在 <td>，font-mono 通过继承生效到单元格内文本。 -->
    <el-table-column prop="code" label="编码" width="140" class-name="font-mono" />
    <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
    <el-table-column label="状态" width="110">
      <template #default="{ row }">
        <StatusTag :status="row.status" />
      </template>
    </el-table-column>
    <el-table-column prop="folder_full_path" label="文件夹" min-width="180" show-overflow-tooltip />
    <el-table-column label="版本" width="110" class-name="font-mono">
      <template #default="{ row }"
        >v{{ row.version }} / 共 {{ row.version_count_in_group }}</template
      >
    </el-table-column>
    <el-table-column label="更新时间" width="160" class-name="font-mono">
      <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="90">
      <template #default="{ row }">
        <el-button link type="primary" @click.stop="emit('open', row.id)">查看</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
