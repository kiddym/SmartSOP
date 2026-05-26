<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ProcedureTable from '@/components/ProcedureTable.vue'
import { fetchProcedureList } from '@/api/procedures'
import type { ProcedureRow } from '@/types/procedure'

const router = useRouter()
const rows = ref<ProcedureRow[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await fetchProcedureList({
      page: page.value,
      page_size: pageSize.value,
      status: 'DRAFT',
      sort: '-updated_at',
    })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(load)

function onPage(p: number): void {
  page.value = p
  void load()
}

function open(id: string): void {
  void router.push(`/procedures/${id}`)
}
</script>

<template>
  <div class="drafts">
    <h2 class="title">草稿箱</h2>
    <ProcedureTable :rows="rows" :loading="loading" @open="open" />
    <el-empty v-if="!loading && rows.length === 0" description="暂无草稿" />
    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      @current-change="onPage"
    />
  </div>
</template>

<style scoped>
.drafts {
  padding: 20px 24px;
}
.title {
  margin: 0 0 16px;
  font-size: 18px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
