const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

const TYPE_TEXT = { notice: '公告', flow: '流程', project: '项目动态', faq: 'FAQ' }

function enrich(list) {
  return (list || []).map((n) => ({
    ...n,
    type_label: TYPE_TEXT[n.type] || n.type,
    create_time_short: n.create_time ? n.create_time.slice(0, 10) : '',
  }))
}

Page({
  data: {
    loading: true,
    error: '',
    all: [],
    filtered: [],
    activeType: '',
  },

  onShow() {
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
      const list = await request.get('/api/notices')
      const all = enrich(list)
      this._apply(all, this.data.activeType)
      this.setData({ loading: false })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  _apply(all, type) {
    const filtered = type ? all.filter((n) => n.type === type) : all
    this.setData({ all, filtered, activeType: type })
  },

  switchType(e) {
    this._apply(this.data.all, e.currentTarget.dataset.type)
  },

  onOpen() {
    // 列表即展示全文，无需跳详情；点击做轻反馈
    wx.showToast({ title: '已阅', icon: 'none', duration: 700 })
  },
})