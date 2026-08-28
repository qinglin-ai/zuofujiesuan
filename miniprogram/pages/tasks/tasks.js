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
    tasks: [],
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

  async onPullDownRefresh() {
    await this._load()
    wx.stopPullDownRefresh()
  },

  async _load() {
    this.setData({ loading: true, error: '' })
    try {
      const tasks = await request.get('/api/tasks')
      tasks.forEach((t) => {
        t.difficulty_text = DIFFICULTY_TEXT[t.difficulty] || ''
        t.annot_text = ANNOT_TEXT[t.annot_type] || t.annot_type || ''
        t.remain = t.total_people - t.claimed_count
        t.can_claim = t.status === 'open' && !t.my_status
      })
      this.setData({ tasks, loading: false })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${e.currentTarget.dataset.id}` })
  },

  goMine() {
    wx.navigateTo({ url: '/pages/my-tasks/my-tasks' })
  },

  async onClaim(e) {
    const id = e.currentTarget.dataset.id
    try {
      await request.post(`/api/tasks/${id}/claim`)
      wx.showToast({ title: '领取成功', icon: 'success' })
      this._load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '领取失败', icon: 'none' })
    }
  }
})
