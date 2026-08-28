const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

const DIFFICULTY_TEXT = { junior: '初级', middle: '中级', senior: '高级' }
const ANNOT_TEXT = {
  shadow: '阴影标注',
  light_source: '光源标注',
  reflection: '反射标注',
  exposure: '曝光标注',
  filter: '滤镜处理'
}

Page({
  data: {
    task: null,
    loading: true,
    error: ''
  },

  onLoad(options) {
    this.taskId = options.id
    if (!tokenManager.getToken()) {
      wx.navigateTo({ url: '/pages/login/login' })
      return
    }
    this._load()
  },

  onPullDownRefresh() {
    this._load().then(() => wx.stopPullDownRefresh())
  },

  async _load() {
    this.setData({ loading: true, error: '' })
    try {
      const t = await request.get(`/api/tasks/${this.taskId}`)
      t.difficulty_text = DIFFICULTY_TEXT[t.difficulty] || ''
      t.annot_text = ANNOT_TEXT[t.annot_type] || t.annot_type || ''
      t.remain = t.total_people - t.claimed_count
      t.can_claim = t.status === 'open' && !t.my_status
      t.require_level_text = DIFFICULTY_TEXT[t.require_level] || ''
      t.cert_level_text = t.my_cert ? (DIFFICULTY_TEXT[t.my_cert.level] || '') : ''
      t.forbidden_text = (t.forbidden_items && t.forbidden_items.length) ? t.forbidden_items.join('、') : ''
      this.setData({ task: t, loading: false })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  async onClaim() {
    try {
      await request.post(`/api/tasks/${this.taskId}/claim`)
      wx.showToast({ title: '领取成功', icon: 'success' })
      this._load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '领取失败', icon: 'none' })
    }
  }
})
