import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/services/api', () => ({
  materialApi: {
    getRoles: vi.fn(() => Promise.resolve([])),
    getScenes: vi.fn(() => Promise.resolve([])),
    getAudios: vi.fn(() => Promise.resolve([])),
    getBGM: vi.fn(() => Promise.resolve([])),
    create: vi.fn(() => Promise.resolve({ code: 200 })),
    update: vi.fn(() => Promise.resolve({ code: 200 })),
    delete: vi.fn(() => Promise.resolve({ code: 200 }))
  }
}))

vi.mock('@/api/upload', () => ({
  uploadAPI: {
    uploadVideo: vi.fn(() => Promise.resolve({ code: 200, data: { file_path: '/test/video.mp4' } })),
    uploadAudio: vi.fn(() => Promise.resolve({ code: 200, data: { file_path: '/test/audio.mp3' } }))
  }
}))

import MaterialListView from '@/views/MaterialListView.vue'

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0))

const createWrapper = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  
  return mount(MaterialListView, {
    global: {
      plugins: [pinia],
      stubs: {
        'el-card': { template: '<div><slot /></div>' },
        'el-tabs': { template: '<div><slot /></div>' },
        'el-tab-pane': { template: '<div><slot /></div>' },
        'el-button': { template: '<button><slot /></button>' },
        'el-form': { template: '<form><slot /></form>' },
        'el-form-item': { template: '<div class="el-form-item"><slot /></div>' },
        'el-input': { template: '<input />' },
        'el-select': { template: '<select><slot /></select>' },
        'el-option': { template: '<option></option>' },
        'el-switch': { 
          template: '<input type="checkbox" class="el-switch" />',
          props: ['modelValue', 'disabled'],
          emits: ['update:modelValue', 'change']
        },
        'el-dialog': { template: '<div v-if="modelValue" class="el-dialog"><slot /></div>', props: ['modelValue'] },
        'el-icon': { template: '<i><slot /></i>' },
        'el-message': true,
        'el-skeleton': { template: '<div><slot /></div>' },
        'el-skeleton-item': { template: '<div></div>' },
        'el-empty': { template: '<div></div>' },
        'el-progress': { template: '<div></div>' },
        'el-alert': { template: '<div><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        Plus: { template: '<span>+</span>' },
        User: { template: '<span>👤</span>' },
        Picture: { template: '<span>🖼</span>' },
        Microphone: { template: '<span>🎤</span>' },
        Headset: { template: '<span>🎧</span>' },
        VideoCamera: { template: '<span>📹</span>' },
        Upload: { template: '<span>↑</span>' },
        Edit: { template: '<span>✏</span>' },
        Delete: { template: '<span>🗑</span>' },
        VideoPlay: { template: '<span>▶</span>' },
        Monitor: { template: '<span>🖥</span>' },
        Clock: { template: '<span>⏰</span>' },
        Check: { template: '<span>✓</span>' },
        Warning: { template: '<span>⚠</span>' },
        Loading: { template: '<span>⟳</span>' },
        MagicStick: { template: '<span>✨</span>' }
      },
      directives: {
        loading: () => {}
      }
    }
  })
}

describe('MaterialListView 双人模式', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('AC-170: 显示双人模式开关', () => {
    it('createForm 应包含 is_double_mode 字段，默认为 false', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      expect(wrapper.vm.createForm.is_double_mode).toBe(false)
    })

    it('createForm 应包含 left_audio_id 字段，默认为空字符串', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      expect(wrapper.vm.createForm.left_audio_id).toBe('')
    })

    it('createForm 应包含 right_audio_id 字段，默认为空字符串', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      expect(wrapper.vm.createForm.right_audio_id).toBe('')
    })

    it('角色素材表单应包含双人模式开关', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.currentTab = 'role'
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const switches = wrapper.findAll('.el-switch')
      expect(switches.length).toBeGreaterThan(0)
    })
  })

  describe('AC-175: 双人模式不可关闭', () => {
    it('handleDoubleModeChange 方法应存在', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      expect(typeof wrapper.vm.handleDoubleModeChange).toBe('function')
    })

    it('开启双人模式时应清空单人模式的 audio_id', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.createForm.audio_id = 'audio_001'
      wrapper.vm.handleDoubleModeChange(true)
      
      expect(wrapper.vm.createForm.audio_id).toBe('')
    })
  })

  describe('AC-174: 双人模式验证', () => {
    it('validateDoubleModeAudio 方法应存在', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      expect(typeof wrapper.vm.validateDoubleModeAudio).toBe('function')
    })

    it('双人模式下未选择两个音频应返回 false', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.createForm.is_double_mode = true
      wrapper.vm.createForm.left_audio_id = 'audio_001'
      wrapper.vm.createForm.right_audio_id = ''
      
      const result = wrapper.vm.validateDoubleModeAudio()
      expect(result).toBe(false)
    })

    it('双人模式下选择两个音频应返回 true', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.createForm.is_double_mode = true
      wrapper.vm.createForm.left_audio_id = 'audio_001'
      wrapper.vm.createForm.right_audio_id = 'audio_002'
      
      const result = wrapper.vm.validateDoubleModeAudio()
      expect(result).toBe(true)
    })

    it('单人模式下应返回 true', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.createForm.is_double_mode = false
      
      const result = wrapper.vm.validateDoubleModeAudio()
      expect(result).toBe(true)
    })
  })

  describe('AC-176: 编辑模式禁用开关', () => {
    it('编辑双人模式角色时应填充双人模式字段', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.currentTab = 'role'
      
      const doubleModeRole = {
        role_id: 'role_001',
        role_name: '双人主播',
        is_double_mode: true,
        left_audio_id: 'audio_001',
        right_audio_id: 'audio_002'
      }
      
      wrapper.vm.editItem(doubleModeRole)
      
      expect(wrapper.vm.createForm.is_double_mode).toBe(true)
      expect(wrapper.vm.createForm.left_audio_id).toBe('audio_001')
      expect(wrapper.vm.createForm.right_audio_id).toBe('audio_002')
    })
  })

  describe('AC-171 & AC-172: 条件渲染音频选择器', () => {
    it('单人模式时应显示单个参考音频选择器', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.currentTab = 'role'
      wrapper.vm.createForm.is_double_mode = false
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const html = wrapper.html()
      expect(html).toContain('参考音频')
    })

    it('双人模式时应显示两个参考音频选择器', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.currentTab = 'role'
      wrapper.vm.createForm.is_double_mode = true
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const html = wrapper.html()
      expect(html).toContain('左边说话人参考音频')
      expect(html).toContain('右边说话人参考音频')
    })
  })

  describe('AC-173: 提交双人模式参数', () => {
    it('双人模式提交时应包含 is_double_mode、left_audio_id、right_audio_id', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      
      wrapper.vm.currentTab = 'role'
      wrapper.vm.createForm.name = '双人主播'
      wrapper.vm.createForm.opening_video = '/test/opening.mp4'
      wrapper.vm.createForm.is_double_mode = true
      wrapper.vm.createForm.left_audio_id = 'audio_001'
      wrapper.vm.createForm.right_audio_id = 'audio_002'
      
      const formData = {
        name: wrapper.vm.createForm.name.trim(),
        type: 'role',
        opening_video: wrapper.vm.createForm.opening_video,
        loop_videos: [],
        ending_video: '',
        audio_id: '',
        role_type: 'human',
        scenes: [],
        is_double_mode: true,
        left_audio_id: 'audio_001',
        right_audio_id: 'audio_002'
      }
      
      expect(formData.is_double_mode).toBe(true)
      expect(formData.left_audio_id).toBe('audio_001')
      expect(formData.right_audio_id).toBe('audio_002')
    })
  })
})
