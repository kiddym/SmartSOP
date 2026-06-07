import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import SignaturePad from '@/components/workorder/SignaturePad.vue'

beforeEach(() => {
  // jsdom 无 canvas API：打桩 getContext / toBlob
  HTMLCanvasElement.prototype.getContext = ((() => ({
    lineWidth: 0,
    lineCap: 'round',
    strokeStyle: '#222',
    beginPath() {},
    moveTo() {},
    lineTo() {},
    stroke() {},
    clearRect() {},
  })) as unknown) as typeof HTMLCanvasElement.prototype.getContext
  HTMLCanvasElement.prototype.toBlob = function (cb: BlobCallback) {
    cb(new Blob(['x'], { type: 'image/png' }))
  }
})

describe('SignaturePad', () => {
  it('确认签名 emit confirm 携带 PNG File', async () => {
    const w = mount(SignaturePad, { global: { plugins: [ElementPlus] } })
    // 先触发 start（设 dirty=true）再确认
    const canvas = w.find('canvas')
    await canvas.trigger('mousedown', { clientX: 10, clientY: 10 })
    const btn = w.findAll('.el-button').find((b) => b.text() === '确认签名')
    await btn!.trigger('click')
    const ev = w.emitted('confirm')
    expect(ev).toBeTruthy()
    const file = ev![0][0] as File
    expect(file.type).toBe('image/png')
    expect(file.name).toBe('signature.png')
  })

  it('未画线点确认不 emit confirm，并弹出警告', async () => {
    const spy = vi.spyOn(ElMessage, 'warning')
    const w = mount(SignaturePad, { global: { plugins: [ElementPlus] } })
    const btn = w.findAll('.el-button').find((b) => b.text() === '确认签名')
    await btn!.trigger('click')
    expect(w.emitted('confirm')).toBeUndefined()
    expect(spy).toHaveBeenCalledWith('请先签名')
  })

  it('清除后再点确认不 emit confirm', async () => {
    const spy = vi.spyOn(ElMessage, 'warning')
    const w = mount(SignaturePad, { global: { plugins: [ElementPlus] } })
    const canvas = w.find('canvas')
    // 先画线（dirty=true）
    await canvas.trigger('mousedown', { clientX: 10, clientY: 10 })
    // 再清除（dirty=false）
    const clearBtn = w.findAll('.el-button').find((b) => b.text() === '清除')
    await clearBtn!.trigger('click')
    // 确认不应 emit
    const confirmBtn = w.findAll('.el-button').find((b) => b.text() === '确认签名')
    await confirmBtn!.trigger('click')
    expect(w.emitted('confirm')).toBeUndefined()
    expect(spy).toHaveBeenCalledWith('请先签名')
  })

  it('画线后点确认 emit confirm', async () => {
    const w = mount(SignaturePad, { global: { plugins: [ElementPlus] } })
    const canvas = w.find('canvas')
    await canvas.trigger('mousedown', { clientX: 5, clientY: 5 })
    await canvas.trigger('mousemove', { clientX: 20, clientY: 20 })
    const confirmBtn = w.findAll('.el-button').find((b) => b.text() === '确认签名')
    await confirmBtn!.trigger('click')
    expect(w.emitted('confirm')).toBeTruthy()
  })
})
