const http = require('http')
const fs = require('fs')
const path = require('path')

const sap = process.env.SAP_URL || 'http://sap:4004'
const ewm = `${sap}/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001`
const wmsCommon = process.env.WMS_COMMON_URL || 'http://openwms-common:8120'
const wmsTms = process.env.WMS_TMS_URL || 'http://openwms-tms:8131'
const fleet = process.env.FLEET_URL || 'http://opentcs:55200'
const tuBarcode = process.env.TU_BARCODE || '00000000000000004711'
const vehicleName = process.env.VEHICLE_NAME || 'Vehicle-01'
const pollMs = Number(process.env.POLL_MS || 2000)

const bins = {
  'IPNT-01': { openwms: 'FGIN/IPNT/0001/0000/0000', opentcs: 'Inbound' },
  'PICK-01': { openwms: 'FGIN/PICK/WORK/0001/0000', opentcs: 'Pick-01' }
}

const journal = []
const inflight = new Set()
// 标准接口里没有存外部单号的字段，任务和仓库单、车队单的对照由桥接自己保存
const links = {}
const parked = new Set()
let csrfToken = null

function note(message, extra) {
  const line = { at: new Date().toISOString(), message, ...(extra ? { extra } : {}) }
  journal.push(line)
  if (journal.length > 200) journal.shift()
  console.log(`${line.at} ${message}${extra ? ' ' + JSON.stringify(extra) : ''}`)
}

async function req(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {})
    }
  })
  const text = await response.text()
  let body = null
  if (text) {
    try { body = JSON.parse(text) } catch { body = text }
  }
  if (!response.ok) {
    const error = new Error(`${options.method || 'GET'} ${url} -> ${response.status} ${typeof body === 'string' ? body : JSON.stringify(body)}`)
    error.status = response.status
    error.body = body
    error.headers = response.headers
    throw error
  }
  return { status: response.status, body, headers: response.headers }
}

async function waitUntil(label, probe, timeoutMs = 180000) {
  const started = Date.now()
  let last = ''
  while (Date.now() - started < timeoutMs) {
    try {
      await probe()
      note(`${label} 已就绪`)
      return
    } catch (error) {
      last = error.message
      await sleep(pollMs)
    }
  }
  throw new Error(`${label} 在 ${timeoutMs}ms 内没有就绪：${last}`)
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function ensureFleet() {
  const model = JSON.parse(fs.readFileSync(path.join(__dirname, 'plant-model.json'), 'utf8'))
  let current = null
  try {
    current = (await req(`${fleet}/v1/plantModel`)).body
  } catch (error) {
    note('读取工厂模型失败，准备上传', { error: error.message })
  }
  const names = new Set((current && current.locations || []).map((item) => item.name))
  if (!names.has('Inbound') || !names.has('Pick-01')) {
    await req(`${fleet}/v1/plantModel`, { method: 'PUT', body: JSON.stringify(model) })
    note('已上传 openTCS 工厂模型')
  }
  const adapter = 'org.opentcs.virtualvehicle.LoopbackCommunicationAdapterDescription'
  await req(`${fleet}/v1/vehicles/${vehicleName}/commAdapter/attachment?newValue=${encodeURIComponent(adapter)}`, { method: 'PUT' })
  await req(`${fleet}/v1/vehicles/${vehicleName}/commAdapter/enabled?newValue=true`, { method: 'PUT' })
  await req(`${fleet}/v1/vehicles/${vehicleName}/integrationLevel?newValue=TO_BE_UTILIZED`, { method: 'PUT' })
  note('Loopback 车辆已启用并可以接单', { vehicle: vehicleName })
}

function taskPath(task) {
  return `WarehouseTask(EWMWarehouse='${task.EWMWarehouse}',WarehouseTask='${task.WarehouseTask}',WarehouseTaskItem='${task.WarehouseTaskItem}')`
}

async function sapTasks(filter) {
  const url = `${ewm}/WarehouseTask?$filter=${encodeURIComponent(filter)}`
  const { body } = await req(url)
  return body.value || []
}

async function sapOne(task) {
  const { body, headers } = await req(`${ewm}/${taskPath(task)}`)
  if (!body['@odata.etag']) body['@odata.etag'] = headers.get('etag')
  return body
}

async function fetchCsrf() {
  const response = await fetch(`${ewm}/`, { method: 'HEAD', headers: { 'X-CSRF-Token': 'Fetch' } })
  csrfToken = response.headers.get('x-csrf-token')
  if (!csrfToken) throw new Error(`SAP 没有返回 CSRF 令牌：${response.status}`)
}

async function sapAction(task, action, payload) {
  const fresh = await sapOne(task)
  if (!csrfToken) await fetchCsrf()
  const send = () => req(`${ewm}/${taskPath(task)}/SAP__self.${action}`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken, 'If-Match': fresh['@odata.etag'] },
    body: JSON.stringify(payload || {})
  })
  try {
    return (await send()).body
  } catch (error) {
    if (error.status !== 403 || error.headers.get('x-csrf-token') !== 'Required') throw error
    await fetchCsrf()
    return (await send()).body
  }
}

async function ensureLocation(spec) {
  try {
    await req(`${wmsCommon}/v1/locations?locationId=${encodeURIComponent(spec.locationId)}`, {
      headers: { Accept: 'application/vnd.openwms.common.location-v1+json' },
    })
  } catch (error) {
    if (error.status !== 404) throw error
    await req(`${wmsCommon}/v1/locations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/vnd.openwms.common.location-v1+json',
        Accept: 'application/vnd.openwms.common.location-v1+json',
      },
      body: JSON.stringify(spec),
    })
    note('已创建 OpenWMS 库位', { locationId: spec.locationId })
  }
}

async function ensureWms() {
  await ensureLocation({
    locationId: bins['IPNT-01'].openwms,
    plcCode: 'IPNT-01',
    erpCode: 'IPNT-01',
    type: 'FG',
    locationGroupName: 'IPOINT1',
  })
  await ensureLocation({
    locationId: bins['PICK-01'].openwms,
    plcCode: 'PICK-01',
    erpCode: 'PICK-01',
    type: 'FG',
    locationGroupName: 'FGWORKPLACE1',
  })
  try {
    await req(`${wmsCommon}/v1/transport-units?bk=${encodeURIComponent(tuBarcode)}`, {
      headers: { Accept: 'application/vnd.openwms.transport-unit-v1+json' },
    })
  } catch (error) {
    if (error.status !== 404) throw error
    await req(
      `${wmsCommon}/v1/transport-units?bk=${encodeURIComponent(tuBarcode)}&actualLocation=${encodeURIComponent(bins['IPNT-01'].openwms)}&tut=PALLET`,
      { method: 'POST', headers: { Accept: 'application/vnd.openwms.transport-unit-v1+json' } },
    )
    note('已创建托盘', { barcode: tuBarcode })
  }
}

async function moveTu(location) {
  await req(`${wmsCommon}/v1/transport-units?bk=${encodeURIComponent(tuBarcode)}&newLocation=${encodeURIComponent(location)}`, {
    method: 'PATCH',
    headers: { Accept: 'application/vnd.openwms.transport-unit-v1+json' }
  })
}

async function createWmsOrder(target) {
  const response = await fetch(`${wmsTms}/v1/transport-orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ barcode: tuBarcode, targetLocation: target, priority: 'NORMAL' })
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`创建 OpenWMS 运输单失败 ${response.status} ${text}`)
  const location = response.headers.get('location') || ''
  const pKey = location.split('/').filter(Boolean).pop()
  if (!pKey) throw new Error(`OpenWMS 没有返回运输单地址：${location}`)
  return pKey
}

async function wmsState(pKey) {
  const { body } = await req(`${wmsTms}/v1/transport-orders/${pKey}`)
  return body.state || body.transportOrderState || ''
}

async function changeWmsState(pKey, state) {
  const current = await wmsState(pKey)
  if (current === state) return
  await req(`${wmsTms}/v1/transport-orders/${pKey}?state=${state}`, { method: 'POST' })
}

async function createFleetOrder(name, src, dst) {
  await req(`${fleet}/v1/transportOrders/${encodeURIComponent(name)}`, {
    method: 'POST',
    body: JSON.stringify({
      intendedVehicle: vehicleName,
      destinations: [
        { locationName: src.opentcs, operation: 'Load cargo' },
        { locationName: dst.opentcs, operation: 'Unload cargo' }
      ]
    })
  })
}

async function fleetState(name) {
  const { body } = await req(`${fleet}/v1/transportOrders/${encodeURIComponent(name)}`)
  return body.state
}

async function withdrawFleet(name) {
  await req(`${fleet}/v1/transportOrders/${encodeURIComponent(name)}/withdrawal?immediate=false`, { method: 'POST' })
}

function fleetName(task) {
  return `SAP-${task.WarehouseTask}`
}

// 标准接口没有"回写异常"，失败的任务在 SAP 里保持未清，桥接停手等人处理
function park(task, text) {
  parked.add(task.WarehouseTask)
  links[task.WarehouseTask] = { ...links[task.WarehouseTask], problem: text }
  note('任务停手，SAP 里仍是未清，等人处理', { task: task.WarehouseTask, text })
}

async function finishSuccess(task, pKey) {
  await changeWmsState(pKey, 'FINISHED')
  await moveTu(bins[task.DestinationStorageBin].openwms)
  await sapAction(task, 'ConfirmWarehouseTaskExact', { DirectWhseTaskConfIsAllowed: true })
  note('搬运完成，已在 SAP 确认仓库任务', { task: task.WarehouseTask, wms: pKey })
}

async function finishFailure(task, pKey, text) {
  try { await changeWmsState(pKey, 'ONFAILURE') } catch (error) {
    note('OpenWMS 置为失败没有成功', { error: error.message })
  }
  park(task, text)
}

async function finishCancel(task, pKey) {
  try { await changeWmsState(pKey, 'CANCELED') } catch (error) {
    note('OpenWMS 取消没有成功', { error: error.message })
  }
  note('SAP 已取消，下游单据也已撤销', { task: task.WarehouseTask })
}

async function watchFleet(task, pKey, name) {
  const deadline = Date.now() + 180000
  let cancelSent = false
  while (Date.now() < deadline) {
    const fresh = await sapOne(task)
    if (fresh.WarehouseTaskStatus === 'A' && !cancelSent) {
      await withdrawFleet(name)
      cancelSent = true
      note('SAP 取消了仓库任务，已向 openTCS 撤回运输单', { name })
    }
    const state = await fleetState(name)
    if (state === 'FINISHED') {
      if (cancelSent) park(task, 'SAP 取消时车辆已经完成搬运，实物和账面不一致')
      else await finishSuccess(task, pKey)
      return
    }
    if (state === 'FAILED' || state === 'UNROUTABLE') {
      if (cancelSent) await finishCancel(task, pKey)
      else await finishFailure(task, pKey, `openTCS 运输单结束于 ${state}`)
      return
    }
    await sleep(pollMs)
  }
  await finishFailure(task, pKey, '等待 openTCS 超时')
}

async function accept(task) {
  if (inflight.has(task.WarehouseTask) || parked.has(task.WarehouseTask)) return
  const src = bins[task.SourceStorageBin]
  const dst = bins[task.DestinationStorageBin]
  if (!src || !dst) {
    park(task, `没有仓位映射：${task.SourceStorageBin} -> ${task.DestinationStorageBin}`)
    return
  }
  inflight.add(task.WarehouseTask)
  const name = fleetName(task)
  note('接手 SAP 仓库任务', { task: task.WarehouseTask, order: task.WarehouseOrder, src: task.SourceStorageBin, dst: task.DestinationStorageBin })
  try {
    await moveTu(src.openwms)
    const pKey = await createWmsOrder(dst.openwms)
    links[task.WarehouseTask] = { warehouseOrder: task.WarehouseOrder, wms: pKey, fleet: name }
    note('已创建 OpenWMS 运输单', { pKey })
    try { await changeWmsState(pKey, 'STARTED') } catch (error) {
      note('显式启动运输单没有成功，继续使用当前状态', { error: error.message })
    }
    await createFleetOrder(name, src, dst)
    note('已下发 openTCS 运输单', { name })
    await watchFleet(task, pKey, name)
  } catch (error) {
    park(task, error.message.slice(0, 240))
  } finally {
    inflight.delete(task.WarehouseTask)
  }
}

async function loop() {
  const open = await sapTasks(`WarehouseTaskStatus eq ''`)
  for (const task of open) {
    if (inflight.size > 0) break
    await accept(task)
  }
}

function startStatusServer() {
  const server = http.createServer((request, response) => {
    if (request.url === '/health') {
      response.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' })
      response.end('ok')
      return
    }
    response.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
    response.end(JSON.stringify({ inflight: [...inflight], parked: [...parked], links, journal: journal.slice(-40) }, null, 2))
  })
  server.listen(8090, '0.0.0.0')
}

async function main() {
  startStatusServer()
  note('桥接启动，等待上下游')
  await waitUntil('SAP', () => req(`${ewm}/$metadata`))
  await waitUntil('OpenWMS Common', () => req(`${wmsCommon}/actuator/info`))
  await waitUntil('OpenWMS TMS', () => req(`${wmsTms}/actuator/info`))
  await waitUntil('openTCS', () => req(`${fleet}/v1/kernel/version`))
  await ensureWms()
  await ensureFleet()
  note('开始轮询 SAP 未清的仓库任务')
  for (;;) {
    try {
      await loop()
    } catch (error) {
      note('轮询出错，下一轮再试', { error: error.message })
    }
    await sleep(pollMs)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
