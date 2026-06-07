<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits<{ (e: 'confirm', file: File): void }>()
const canvasRef = ref<HTMLCanvasElement | null>(null)
let drawing = false
let dirty = false
let ctx: CanvasRenderingContext2D | null = null

onMounted(() => {
  const c = canvasRef.value
  if (!c) return
  ctx = c.getContext('2d')
  if (ctx) {
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#222'
  }
})

function pos(e: MouseEvent): [number, number] {
  const r = canvasRef.value!.getBoundingClientRect()
  return [e.clientX - r.left, e.clientY - r.top]
}
function start(e: MouseEvent): void {
  if (!ctx) return
  drawing = true
  dirty = true
  const [x, y] = pos(e)
  ctx.beginPath()
  ctx.moveTo(x, y)
}
function move(e: MouseEvent): void {
  if (!drawing || !ctx) return
  const [x, y] = pos(e)
  ctx.lineTo(x, y)
  ctx.stroke()
}
function stop(): void {
  drawing = false
}
function clear(): void {
  const c = canvasRef.value
  if (c && ctx) ctx.clearRect(0, 0, c.width, c.height)
  dirty = false
}
function confirm(): void {
  if (!dirty) {
    ElMessage.warning('请先签名')
    return
  }
  const c = canvasRef.value
  if (!c) return
  c.toBlob((blob) => {
    if (blob) emit('confirm', new File([blob], 'signature.png', { type: 'image/png' }))
  }, 'image/png')
}
</script>

<template>
  <div class="sign-pad">
    <canvas
      ref="canvasRef"
      width="320"
      height="140"
      class="sign-canvas"
      @mousedown="start"
      @mousemove="move"
      @mouseup="stop"
      @mouseleave="stop"
    />
    <div class="sign-actions">
      <el-button size="small" @click="clear">清除</el-button>
      <el-button size="small" type="primary" @click="confirm">确认签名</el-button>
    </div>
  </div>
</template>

<style scoped>
.sign-canvas {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  touch-action: none;
  background: #fff;
}
.sign-actions {
  margin-top: 6px;
  display: flex;
  gap: 8px;
}
</style>
