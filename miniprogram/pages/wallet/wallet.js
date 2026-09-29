const request = require('../../utils/request')
const tokenManager = require('../../utils/token')
const { maskName } = require('../../utils/mask')

const WD_STATUS = { pending: '转账中', paid: '已到账', rejected: '已拒绝' }
const WD_TRANSFER_TEXT = {
  WAIT_USER_CONFIRM: '待收款确认',
  TRANSFERING: '转账中',
  PROCESSING: '转账中',
  SUCCESS: '已到账',
  FAIL: '转账失败',
  CANCELLED: '已取消',
}

Page({
  data: {
    loading: true,
    error: '',
    info: { available_balance: '0', total_income: '0', total_withdrawn: '0', has_bank: false, bank_info: null, bank_tail: '' },
    rule: { daily_limit: 1, today_used: 0, today_remaining: 1 },
    withdrawAmount: '',
    canWithdraw: false,
    activeTab: 'commission',
    commissions: [],
    withdrawals: [],
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
      const info = await request.get('/api/wallet/me')
      const commissions = await request.get('/api/wallet/commissions')
      const wds = await request.get('/api/wallet/withdrawals')
      const bank_tail = info.bank_info && info.bank_info.cardNo
        ? `${info.bank_info.bankName || ''} ···${String(info.bank_info.cardNo).slice(-4)}（${maskName(info.bank_info.cardHolder)}）`
        : ''
      const withdrawals = wds.map((w) => {
        let status_text = WD_STATUS[w.status] || w.status
        // 转账中细化展示：待收款确认 = 转账已发起、需用户在微信「微信支付」转账消息中点击确认收款（非本小程序内操作）
        if (w.status === 'pending' && w.transfer_status && WD_TRANSFER_TEXT[w.transfer_status]) {
          status_text = WD_TRANSFER_TEXT[w.transfer_status]
        }
        // CANCELLED 换单重试耗尽：余额已退回可提现余额
        if (w.status === 'rejected' && w.balance_refunded) {
          status_text = '已取消（余额已退回）'
        }
        return { ...w, status_text, fail_reason: w.fail_reason || '' }
      })
      const rule = info.withdraw_rule || { daily_limit: 1, today_used: 0, today_remaining: 1 }
      this.setData({
        info: { ...info, bank_tail },
        rule,
        commissions,
        withdrawals,
        canWithdraw: info.has_bank && Number(info.available_balance) > 0 && rule.today_remaining > 0,
        loading: false,
      })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.key })
  },

  /** 绑卡已迁至「用户」页（tabBar 页，须用 switchTab） */
  goBindBank() {
    wx.switchTab({ url: '/pages/index/index' })
  },

  onAmountInput(e) {
    this.setData({ withdrawAmount: e.detail.value })
  },

  async onWithdraw() {
    const amount = Number(this.data.withdrawAmount)
    if (!amount || amount <= 0) {
      wx.showToast({ title: '请输入有效金额', icon: 'none' })
      return
    }
    if (amount > Number(this.data.info.available_balance)) {
      wx.showToast({ title: '超出可提现额度', icon: 'none' })
      return
    }
    if (this.data.rule.today_remaining <= 0) {
      wx.showToast({ title: `今日提现次数已用完（每日最多 ${this.data.rule.daily_limit} 次）`, icon: 'none' })
      return
    }
    const res = await wx.showModal({ title: '确认提现', content: `申请提现 ￥${amount}？`, confirmColor: '#1989fa' })
    if (!res.confirm) return
    try {
      await request.post('/api/wallet/withdrawals', { amount: this.data.withdrawAmount })
      wx.showToast({ title: '提现已受理，转账中', icon: 'success' })
      this.setData({ withdrawAmount: '' })
      this._load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '提现失败', icon: 'none' })
    }
  },
})