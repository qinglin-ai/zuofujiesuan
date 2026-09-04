const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

const ANNOT_TEXT = {
  shadow: '阴影标注',
  light_source: '光源标注',
  reflection: '反射标注',
  exposure: '曝光标注',
  filter: '滤镜处理'
}
const ANNOT_LIST = Object.keys(ANNOT_TEXT).map((k) => ({ id: k, label: ANNOT_TEXT[k] }))
const LEVEL_TEXT = { junior: '初级', middle: '中级', senior: '高级' }

Page({
  data: {
    loading: true,
    error: '',
    certs: [],
    annotList: ANNOT_LIST,
    annotLabel: ANNOT_TEXT.shadow,
    taskOptions: [],
    showTaskPicker: true,
    selectedTaskLabel: '',
    form: { task_id: '', annot_type: 'shadow', pass_rate: '', exam_passed: true }
  },

  onLoad(options) {
    this._taskAnnot = {}
    if (options.task_id) {
      // 从任务详情「去认证」跳转：预填任务与标注类型，隐藏任务下拉
      this.setData({ showTaskPicker: false })
      this._loadTask(options.task_id)
    } else {
      this._loadTasks()
    }
  },

  onShow() {
    if (!tokenManager.getToken()) {
      wx.navigateTo({ url: '/pages/login/login' })
      return
    }
    this._loadCerts()
  },

  onPullDownRefresh() {
    this._loadCerts().then(() => wx.stopPullDownRefresh())
  },

  async _loadCerts() {
    try {
      const certs = await request.get('/api/certifications/mine')
      const rows = certs.map((c) => {
        const status_text = c.review_time ? (c.exam_passed ? '已通过' : '未通过') : '待评级'
        return {
          ...c,
          annot_text: ANNOT_TEXT[c.annot_type] || c.annot_type || '',
          level_text: LEVEL_TEXT[c.level] || '',
          status_text,
          review_time: c.review_time ? c.review_time.slice(0, 10) : ''
        }
      })
      this.setData({ certs: rows, loading: false, error: '' })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  async _loadTasks() {
    try {
      const tasks = await request.get('/api/tasks')
      const opts = []
      const map = {}
      tasks.forEach((t) => {
        if (t.status === 'closed') return
        opts.push({ id: t.id, label: `#${t.id} ${t.title}（${ANNOT_TEXT[t.annot_type] || ''}）` })
        map[t.id] = t.annot_type
      })
      this._taskAnnot = map
      this.setData({ taskOptions: opts })
      if (opts.length) {
        const annot = map[opts[0].id]
        this.setData({
          selectedTaskLabel: opts[0].label,
          'form.task_id': opts[0].id,
          'form.annot_type': annot,
          annotLabel: ANNOT_TEXT[annot] || annot || ''
        })
      }
    } catch (e) {
      this.setData({ error: (e && e.message) || '任务加载失败' })
    }
  },

  async _loadTask(id) {
    try {
      const t = await request.get(`/api/tasks/${id}`)
      this.setData({
        selectedTaskLabel: `#${t.id} ${t.title}（${ANNOT_TEXT[t.annot_type] || ''}）`,
        'form.task_id': id,
        'form.annot_type': t.annot_type,
        annotLabel: ANNOT_TEXT[t.annot_type] || t.annot_type || ''
      })
    } catch (e) {
      this.setData({ error: (e && e.message) || '任务加载失败' })
    }
  },

  onTaskChange(e) {
    const opt = this.data.taskOptions[Number(e.detail.value)]
    if (!opt) return
    const annot = this._taskAnnot[opt.id]
    this.setData({
      selectedTaskLabel: opt.label,
      'form.task_id': opt.id,
      'form.annot_type': annot,
      annotLabel: ANNOT_TEXT[annot] || annot || ''
    })
  },

  onAnnotChange(e) {
    const annot = e.detail.value
    this.setData({ 'form.annot_type': annot, annotLabel: ANNOT_TEXT[annot] || annot || '' })
  },

  onRateInput(e) {
    this.setData({ 'form.pass_rate': e.detail.value })
  },

  onExamSwitch(e) {
    this.setData({ 'form.exam_passed': e.detail.value })
  },

  async onSubmit() {
    const f = this.data.form
    if (!f.task_id) {
      wx.showToast({ title: '请选择任务', icon: 'none' })
      return
    }
    const rate = Number(f.pass_rate)
    if (f.pass_rate === '' || isNaN(rate) || rate < 0 || rate > 100) {
      wx.showToast({ title: '请输入 0~100 的考试成绩', icon: 'none' })
      return
    }
    try {
      await request.post('/api/certifications', {
        task_id: f.task_id,
        annot_type: f.annot_type,
        pass_rate: rate,
        exam_passed: f.exam_passed
      })
      wx.showToast({ title: '已提交，待评级', icon: 'success' })
      this.setData({ 'form.pass_rate': '', 'form.exam_passed': true })
      this._loadCerts()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '提交失败', icon: 'none' })
    }
  }
})
