const tokenManager = require('./utils/token')

App({
  globalData: {
    userInfo: null,
    backendBaseUrl: 'http://127.0.0.1:5000' // TODO: 生产替换为 HTTPS 域名
  },

  onLaunch() {
    // 启动时若有本地 token 则尝试拉取用户信息
    const token = tokenManager.getToken()
    if (token) {
      // 阶段二仅加载骨架，阶段三接入 /api/auth/me
    }
  }
})