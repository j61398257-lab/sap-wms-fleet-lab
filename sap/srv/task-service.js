const cds = require('@sap/cds')

module.exports = (srv) => {
  const { Tasks } = srv.entities

  async function one(req) {
    const id = req.params[0].ID ?? req.params[0]
    const task = await SELECT.one.from(Tasks).where({ ID: id })
    if (!task) req.reject(404, '任务不存在')
    return task
  }

  function allow(req, task, states) {
    if (!states.includes(task.status)) {
      req.reject(409, `任务 ${task.taskNo} 当前是 ${task.status}，不能做这个动作`)
    }
  }

  async function save(id, data) {
    await UPDATE(Tasks).set({ ...data, modifiedAt: new Date() }).where({ ID: id })
    return SELECT.one.from(Tasks).where({ ID: id })
  }

  srv.on('release', async (req) => {
    const task = await one(req)
    allow(req, task, ['CREATED'])
    return save(task.ID, { status: 'RELEASED' })
  })

  srv.on('handover', async (req) => {
    const task = await one(req)
    allow(req, task, ['RELEASED'])
    return save(task.ID, {
      status: 'IN_PROCESS',
      externalRef: req.data.externalRef,
      fleetOrder: req.data.fleetOrder,
    })
  })

  srv.on('confirm', async (req) => {
    const task = await one(req)
    allow(req, task, ['IN_PROCESS'])
    return save(task.ID, {
      status: 'CONFIRMED',
      actualQty: req.data.actualQty ?? task.qty,
      cancelRequested: false,
    })
  })

  srv.on('reportException', async (req) => {
    const task = await one(req)
    allow(req, task, ['RELEASED', 'IN_PROCESS'])
    return save(task.ID, {
      status: 'EXCEPTION',
      exceptionCode: req.data.code,
      exceptionText: req.data.text,
    })
  })

  srv.on('requestCancel', async (req) => {
    const task = await one(req)
    allow(req, task, ['CREATED', 'RELEASED', 'IN_PROCESS'])
    return save(task.ID, { cancelRequested: true })
  })

  srv.on('acceptCancel', async (req) => {
    const task = await one(req)
    if (!task.cancelRequested) req.reject(409, `任务 ${task.taskNo} 没有取消请求`)
    allow(req, task, ['CREATED', 'RELEASED', 'IN_PROCESS'])
    return save(task.ID, { status: 'CANCELLED' })
  })
}
