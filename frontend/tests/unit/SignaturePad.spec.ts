import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
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
    const btn = w.findAll('.el-button').find((b) => b.text() === '确认签名')
    await btn!.trigger('click')
    const ev = w.emitted('confirm')
    expect(ev).toBeTruthy()
    const file = ev![0][0] as File
    expect(file.type).toBe('image/png')
    expect(file.name).toBe('signature.png')
  })
})
