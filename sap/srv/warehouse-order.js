const cds = require('@sap/cds')

module.exports = (srv) => {
  const { WarehouseOrder, WarehouseTask } = srv.entities

  async function one(req) {
    const { EWMWarehouse, WarehouseTask: no, WarehouseTaskItem } = req.params[0]
    const task = await SELECT.one.from(WarehouseTask).where({ EWMWarehouse, WarehouseTask: no, WarehouseTaskItem })
    if (!task) req.reject(404, `仓库任务 ${EWMWarehouse}/${no}/${WarehouseTaskItem} 不存在`)
    return task
  }

  function keyOf(task) {
    const { EWMWarehouse, WarehouseTask: no, WarehouseTaskItem } = task
    return { EWMWarehouse, WarehouseTask: no, WarehouseTaskItem }
  }

  async function nextNo(entity, element, first) {
    const row = await SELECT.one.from(entity).columns(`max(${element}) as last`)
    return String(row && row.last ? Number(row.last) + 1 : first)
  }

  // 仓库单下的任务全部结束（确认或取消）时，仓库单自动完成
  async function closeOrderIfDone(task) {
    const tasks = await SELECT.from(WarehouseTask)
      .columns('WarehouseTaskStatus')
      .where({ EWMWarehouse: task.EWMWarehouse, WarehouseOrder: task.WarehouseOrder })
    if (tasks.some((item) => !['C', 'A'].includes(item.WarehouseTaskStatus))) return
    const status = tasks.every((item) => item.WarehouseTaskStatus === 'A') ? 'A' : 'C'
    await UPDATE(WarehouseOrder)
      .set({ WarehouseOrderStatus: status })
      .where({ EWMWarehouse: task.EWMWarehouse, WarehouseOrder: task.WarehouseOrder })
  }

  srv.before('CREATE', WarehouseTask, async (req) => {
    const now = new Date().toISOString()
    const data = req.data
    data.EWMWarehouse ??= 'E001'
    data.WarehouseTask = await nextNo(WarehouseTask, 'WarehouseTask', 1000000001)
    data.WarehouseTaskItem = '0'
    if (!data.WarehouseOrder) {
      data.WarehouseOrder = await nextNo(WarehouseOrder, 'WarehouseOrder', 2000000001)
      await INSERT.into(WarehouseOrder).entries({ EWMWarehouse: data.EWMWarehouse, WarehouseOrder: data.WarehouseOrder })
    }
    data.WarehouseTaskStatus = ''
    data.ActualQuantityInAltvUnit = 0
    data.WhseTaskCrtnUTCDateTime = now
    data.LastChangeUTCDateTime = now
  })

  srv.on('ConfirmWarehouseTaskExact', WarehouseTask, async (req) => {
    const task = await one(req)
    if (task.WarehouseTaskStatus !== '') {
      req.reject(400, `仓库任务 ${task.WarehouseTask} 的状态是 '${task.WarehouseTaskStatus}'，只有未清任务可以确认`)
    }
    const order = await SELECT.one.from(WarehouseOrder)
      .where({ EWMWarehouse: task.EWMWarehouse, WarehouseOrder: task.WarehouseOrder })
    if (!req.data.DirectWhseTaskConfIsAllowed && !(order && order.ExecutingResource)) {
      req.reject({ status: 400, code: '/SCWM/ODATA_API/006', message: 'Log on to resource first' })
    }
    const now = new Date().toISOString()
    await UPDATE(WarehouseTask).set({
      WarehouseTaskStatus: 'C',
      ActualQuantityInAltvUnit: task.TargetQuantityInAltvUnit,
      WarehouseTaskConfUTCDateTime: now,
      LastChangeUTCDateTime: now,
    }).where(keyOf(task))
    await closeOrderIfDone(task)
    return SELECT.one.from(WarehouseTask).where(keyOf(task))
  })

  srv.on('CancelWarehouseTask', WarehouseTask, async (req) => {
    const task = await one(req)
    if (task.WarehouseTaskStatus !== '') {
      req.reject(400, `仓库任务 ${task.WarehouseTask} 的状态是 '${task.WarehouseTaskStatus}'，只有未清任务可以取消`)
    }
    await UPDATE(WarehouseTask)
      .set({ WarehouseTaskStatus: 'A', LastChangeUTCDateTime: new Date().toISOString() })
      .where(keyOf(task))
    await closeOrderIfDone(task)
    return SELECT.one.from(WarehouseTask).where(keyOf(task))
  })
}
