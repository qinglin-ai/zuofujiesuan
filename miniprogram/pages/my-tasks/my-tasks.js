const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

const TABS = [
  { key: 'all', label: '全部' },
  { key: 'claimed', label: '已领取' },
  { key: 'submitted', label: '已提交' },
  { key: 'passed', label: '已通过' },
  { key: 'rejected', label: '未通过' }
]

Page({
  data: {
    tabs: TABS,
    activeTab: 'all',
    list: [],
    filtered: [],
    loading: true,
    error: ''
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
      const list = await request.get('/api/tasks/mine')
      this.setData({ list })
      this._filter()
      this.setData({ loading: false })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.key })
    this._filter()
  },

  _filter() {
    const activeTab = this.data.activeTab
    const filtered = activeTab === 'all' ? this.data.list : this.data.list.filter((a) => a.status === activeTab)
    this.setData({ filtered })
  },

  async onSubmit(e) {
    const { taskId, assignmentId } = e.currentTarget.dataset
    const res = await wx.showModal({ title: '提交作业', content: '确认提交？提交后需等待核验。', confirmColor: '#1989fa' })
    if (!res.confirm) return
    try {
      await request.post(`/api/tasks/${taskId}/assignments/${assignmentId}/submit`)
      wx.showToast({ title: '提交成功', icon: 'success' })
      this._load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '提交失败', icon: 'none' })
    }
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${e.currentTarget.dataset.taskId}` })
  }
})
