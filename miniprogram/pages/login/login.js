const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

Page({
  data: { loading: false, error: '' },

  async onLogin() {
    this.setData({ loading: true, error: '' })
    try {
      // 微信登录获取 code
      const { code } = await this._wxLogin()
      // 用 code 换取后端签发的 token
      const data = await request.post('/api/auth/login', { code }, { needAuth: false })
      tokenManager.setToken(data.token)
      getApp().globalData.userInfo = data.user
      wx.navigateBack({})

    } catch (e) {
      this.setData({ error: (e && e.message) || '登录失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  _wxLogin() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => res.code ? resolve(res) : reject({ message: 'wx.login 失败' }),
        fail: reject
      })
    })
  }
})