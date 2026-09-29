const request = require('../../utils/request')
const tokenManager = require('../../utils/token')
const { maskPhone, maskName } = require('../../utils/mask')

const APPROVAL_TEXT = { pending: '待审批', approved: '已通过', rejected: '已驳回' }

// 开发环境判定：仅开发版展示连通性诊断，试用/正式版不展示
function isDevBuild() {
  try {
    const info = wx.getAccountInfoSync()
    return info && info.miniProgram && info.miniProgram.envVersion === 'develop'
  } catch (e) {
    return true
  }
}

Page({
  data: {
    logged: false,
    user: null,
    // 实名信息：是否已绑定 / 是否允许编辑 / 展示用派生字段
    bound: false,
    canEditProfile: true,
    maskPhone: '',
    maskName: '',
    avatarName: '',
    approvalText: '',
    avatarUrl: '',
    avatarChar: '兼',
    form: { nickname: '', phone: '', real_name: '' },
    agreed: false,
    // 收款银行卡（由「我的资金」页迁入）
    hasBank: false,
    bankTail: '',
    showBankForm: false,
    bank: { bankName: '', cardNo: '', cardHolder: '' },
    agreedBank: false,
    ping: null,
    dbOk: null,
    devMode: false
  },

  onLoad() {
    this.setData({ devMode: isDevBuild() })
  },

  onShow() {
    const token = tokenManager.getToken()
    this.setData({ logged: !!token })
    if (token) {
      this._loadProfile()
    } else {
      this.setData({ user: null, bound: false, canEditProfile: true, hasBank: false, bankTail: '' })
    }
  },

  /** 拉取本人资料（实名 + 银行卡），用户页展示与回显 */
  async _loadProfile() {
    try {
      const [user, wallet] = await Promise.all([
        request.get('/api/auth/me'),
        request.get('/api/wallet/me').catch(() => null)
      ])
      const baseUrl = getApp().globalData.backendBaseUrl
      const bound = !!user.phone
      const bank = (wallet && wallet.bank_info) || null
      this.setData({
        user,
        bound,
        // 已审批通过后实名信息锁定，仅「被驳回」可重新提交
        canEditProfile: !bound || user.approval_status === 'rejected',
        maskPhone: maskPhone(user.phone),
        maskName: maskName(user.real_name),
        avatarName: user.nickname || maskName(user.real_name) || '未设置昵称',
        approvalText: APPROVAL_TEXT[user.approval_status] || user.approval_status,
        avatarUrl: user.avatar
          ? (user.avatar.indexOf('http') === 0 ? user.avatar : baseUrl + user.avatar)
          : '',
        avatarChar: (user.nickname || user.real_name || '兼').slice(0, 1),
        form: {
          nickname: user.nickname || '',
          phone: user.phone || '',
          real_name: user.real_name || ''
        },
        hasBank: !!(wallet && wallet.has_bank),
        bankTail: bank && bank.cardNo
          ? `${bank.bankName || ''} ···${String(bank.cardNo).slice(-4)}（${maskName(bank.cardHolder)}）`
          : ''
      })
    } catch (e) {
      // 401 时 request 已清 token
      this.setData({ logged: false, user: null, bound: false, canEditProfile: true })
    }
  },

  onFormInput(e) {
    this.setData({ ['form.' + e.currentTarget.dataset.key]: e.detail.value })
  },

  toggleAgree() {
    this.setData({ agreed: !this.data.agreed })
  },

  /** 头像：chooseAvatar 返回本地临时路径，须先上传到服务端再入库 */
  onChooseAvatar(e) {
    const filePath = e.detail.avatarUrl
    if (!filePath) return
    const baseUrl = getApp().globalData.backendBaseUrl
    const token = tokenManager.getToken()
    wx.showLoading({ title: '上传中' })
    wx.uploadFile({
      url: baseUrl + '/api/users/avatar',
      filePath,
      name: 'file',
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: (res) => {
        let body = {}
        try {
          body = JSON.parse(res.data)
        } catch (err) {
          body = {}
        }
        if (res.statusCode === 200 && body.code === 0) {
          this.setData({ avatarUrl: baseUrl + body.data.avatar })
          wx.showToast({ title: '头像已更新', icon: 'success' })
        } else {
          wx.showToast({ title: body.message || '头像上传失败', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '头像上传失败', icon: 'none' }),
      complete: () => wx.hideLoading()
    })
  },

  /** 实名信息绑定（复用 /api/users/register，仅首次绑定 / 驳回后重提） */
  async onBindProfile() {
    const { nickname, phone, real_name } = this.data.form
    if (!phone || !real_name) {
      wx.showToast({ title: '请填写手机号与真实姓名', icon: 'none' })
      return
    }
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      wx.showToast({ title: '手机号格式不正确', icon: 'none' })
      return
    }
    // 合规要求：先取得用户对《用户服务协议》《隐私政策》的授权同意，再收集个人信息
    if (!this.data.agreed) {
      wx.showToast({ title: '请先阅读并同意协议与隐私政策', icon: 'none' })
      return
    }
    try {
      await request.post('/api/users/register', { phone, real_name, nickname })
      wx.showToast({ title: '已提交，待审批', icon: 'success' })
      this._loadProfile()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '提交失败', icon: 'none' })
    }
  },

  onBankInput(e) {
    this.setData({ ['bank.' + e.currentTarget.dataset.key]: e.detail.value })
  },

  toggleAgreeBank() {
    this.setData({ agreedBank: !this.data.agreedBank })
  },

  onShowBankForm() {
    this.setData({ showBankForm: true })
  },

  async onBindBank() {
    const { bankName, cardNo, cardHolder } = this.data.bank
    if (!bankName || !cardNo || !cardHolder) {
      wx.showToast({ title: '请填写完整开户行/卡号/持卡人', icon: 'none' })
      return
    }
    // 国内银行卡号 16~19 位数字（借记卡多为 16/17/19 位，信用卡 16 位）
    if (!/^\d{16,19}$/.test(cardNo)) {
      wx.showToast({ title: '银行卡号应为 16~19 位数字', icon: 'none' })
      return
    }
    if (!this.data.agreedBank) {
      wx.showToast({ title: '请先阅读并同意协议与隐私政策', icon: 'none' })
      return
    }
    try {
      await request.post('/api/wallet/bank', { ...this.data.bank, agree: true })
      wx.showToast({ title: '绑定成功', icon: 'success' })
      this.setData({ showBankForm: false, agreedBank: false })
      this._loadProfile()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '绑定失败', icon: 'none' })
    }
  },

  async onHealth() {
    try {
      const data = await request.get('/api/health/ping', {}, { needAuth: false })
      this.setData({ ping: data })
      this.setData({ dbOk: await this._checkDb() })
    } catch (e) {
      this.setData({ ping: e })
    }
  },

  async _checkDb() {
    try {
      await request.get('/api/health/db', {}, { needAuth: false })
      return true
    } catch (e) {
      return false
    }
  },

  onLogout() {
    tokenManager.clearToken()
    this.setData({
      logged: false,
      user: null,
      bound: false,
      canEditProfile: true,
      hasBank: false,
      bankTail: '',
      showBankForm: false
    })
  },

  goCertify() {
    wx.navigateTo({ url: '/pages/certify/certify' })
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  goAgreement() {
    wx.navigateTo({ url: '/pages/agreement/agreement' })
  },

  goPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' })
  }
})