<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Upload } from '@element-plus/icons-vue'
import {
  downloadTemplate,
  importCsv,
  type ImportEntity,
  type ImportResult,
} from '@/api/imports'

// 实体级 CSV 批量导入向导：选实体 → 下模板 → 传 CSV → 提交 → 看结果。
const ENTITIES: { value: ImportEntity; label: string; hint: string }[] = [
  {
    value: 'assets',
    label: '资产',
    hint: '列：name,status,category,location,manufacturer,model,serial_number（category/location 按名称匹配）',
  },
  { value: 'locations', label: '位置', hint: '列：name,address,parent（parent 按名称匹配上级位置）' },
  {
    value: 'parts',
    label: '备件',
    hint: '列：name,description,unit,cost,quantity,min_quantity,category（category 按名称匹配）',
  },
  { value: 'meters', label: '计量点', hint: '列：name,unit,asset,location,category（关联按名称匹配）' },
]

const entity = ref<ImportEntity>('assets')
const file = ref<File | null>(null)
const submitting = ref(false)
const result = ref<ImportResult | null>(null)

const currentHint = computed(() => ENTITIES.find((e) => e.value === entity.value)?.hint ?? '')

function onEntityChange() {
  // 切换实体清空既有选择与结果，避免误导。
  file.value = null
  result.value = null
}

async function onDownloadTemplate() {
  try {
    await downloadTemplate(entity.value)
  } catch {
    ElMessage.error('模板下载失败')
  }
}

// el-upload 手动模式：仅缓存所选文件，不自动上传。
function onFileChange(uploadFile: { raw?: File }) {
  file.value = uploadFile.raw ?? null
  result.value = null
}

function onFileRemove() {
  file.value = null
}

async function onSubmit() {
  if (!file.value) {
    ElMessage.warning('请先选择要导入的 CSV 文件')
    return
  }
  submitting.value = true
  try {
    result.value = await importCsv(entity.value, file.value)
    if (result.value.failed === 0) {
      ElMessage.success(`导入完成：成功 ${result.value.created} 条`)
    } else {
      ElMessage.warning(
        `导入完成：成功 ${result.value.created} 条，失败 ${result.value.failed} 条`,
      )
    }
  } catch {
    ElMessage.error('导入失败，请检查文件格式')
  } finally {
    submitting.value = false
  }
}

// 暴露内部状态/动作供测试驱动（el-upload 文件选择在 jsdom 难以真实触发）。
defineExpose({ entity, file, result, onSubmit, onDownloadTemplate })
</script>

<template>
  <div class="import-view">
    <el-card>
      <template #header>
        <span class="title">数据导入</span>
      </template>

      <el-form label-width="96px">
        <el-form-item label="导入实体">
          <el-radio-group v-model="entity" @change="onEntityChange">
            <el-radio-button v-for="e in ENTITIES" :key="e.value" :value="e.value">
              {{ e.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="模板">
          <el-button :icon="Download" @click="onDownloadTemplate">下载模板 CSV</el-button>
          <span class="hint">{{ currentHint }}</span>
        </el-form-item>

        <el-form-item label="CSV 文件">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".csv"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
          >
            <el-button :icon="Upload">选择 CSV 文件</el-button>
          </el-upload>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="submitting"
            :disabled="!file"
            @click="onSubmit"
          >
            开始导入
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="result" class="result-card">
      <template #header>
        <span class="title">导入结果</span>
      </template>
      <div class="summary">
        <el-tag type="success">成功 {{ result.created }} 条</el-tag>
        <el-tag v-if="result.failed > 0" type="danger">失败 {{ result.failed }} 条</el-tag>
        <el-tag v-else type="info">无失败行</el-tag>
      </div>
      <el-table
        v-if="result.errors.length"
        :data="result.errors"
        class="error-table"
        border
        size="small"
      >
        <el-table-column prop="row" label="行号" width="100" />
        <el-table-column prop="message" label="错误信息" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.import-view {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.title {
  font-weight: 600;
}
.hint {
  margin-left: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.summary {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.error-table {
  width: 100%;
}
</style>
