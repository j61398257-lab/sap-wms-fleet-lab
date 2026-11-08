const cds = require('@sap/cds')
const crypto = require('crypto')

const SERVICE = '/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001'
const NAMESPACE = 'com.sap.gateway.srvd_a2x.api_warehouse_order_task_2.v0001'
const token = crypto.randomBytes(18).toString('base64url')

cds.on('bootstrap', (app) => {
  app.use(SERVICE, (req, res, next) => {
    // 真实网关把令牌和会话 cookie 绑定，这里只校验令牌本身
    if (String(req.headers['x-csrf-token'] || '').toLowerCase() === 'fetch') {
      res.set('x-csrf-token', token)
      if (req.method === 'HEAD') return res.status(200).end()
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      if (req.headers['x-csrf-token'] !== token) {
        return res.status(403).set('x-csrf-token', 'Required').type('text/plain').send('CSRF token validation failed')
      }
      if (/^\/WarehouseTask\(.+\)\//.test(req.url) && !req.headers['if-match']) {
        return res.status(428).json({ error: { code: '428', message: '修改仓库任务必须带 If-Match 头' } })
      }
    }
    req.url = req.url.replace(/\/SAP__self\./g, `/${NAMESPACE}.`)
    next()
  })
})

module.exports = cds.server
