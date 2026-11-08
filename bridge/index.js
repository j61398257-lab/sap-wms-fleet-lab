const http = require('http')
const fs = require('fs')
const path = require('path')

const sap = process.env.SAP_URL || 'http://sap:4004'
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

async function sapTasks(filter) {
  const url = `${sap}/odata/v4/task/Tasks?$filter=${encodeURIComponent(filter)}`
  const { body } = await req(url)
  return body.value || []
}

async function sapOne(id) {
  const { body, headers } = await req(`${sap}/odata/v4/task/Tasks(${id})`)
  if (!body['@odata.etag']) body['@odata.etag'] = headers.get('etag')
  return body
}

async function sapAction(task, action, payload) {
  const headers = {}
  if (task['@odata.etag']) headers['If-Match'] = task['@odata.etag']
  await req(`${sap}/odata/v4/task/Tasks(${task.ID})/TaskService.${action}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload || {})
  })
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
  return `SAP-${task.taskNo}`
}

async function finishSuccess(task, pKey) {
  await changeWmsState(pKey, 'FINISHED')
  await moveTu(bins[task.dstBin].openwms)
  const fresh = await sapOne(task.ID)
  await sapAction(fresh, 'confirm', { actualQty: Number(fresh.qty) })
  note('搬运完成，状态已回到 SAP', { taskNo: task.taskNo, wms: pKey })
}

async function finishException(task, pKey, text) {
  try { await changeWmsState(pKey, 'ONFAILURE') } catch (error) {
    note('OpenWMS 置为失败没有成功', { error: error.message })
  }
  const fresh = await sapOne(task.ID)
  await sapAction(fresh, 'reportException', { code: 'FLEET', text })
  note('搬运失败，已回写异常', { taskNo: task.taskNo, text })
}

async function finishCancel(task, pKey) {
  try { await changeWmsState(pKey, 'CANCELED') } catch (error) {
    note('OpenWMS 取消没有成功', { error: error.message })
  }
  const fresh = await sapOne(task.ID)
  await sapAction(fresh, 'acceptCancel', {})
  note('取消已被下游接受', { taskNo: task.taskNo })
}

async function watchFleet(task, pKey, name) {
  const deadline = Date.now() + 180000
  let cancelSent = false
  while (Date.now() < deadline) {
    const [fresh] = await sapTasks(`taskNo eq '${task.taskNo}'`)
    if (fresh && fresh.cancelRequested && !cancelSent) {
      await withdrawFleet(name)
      cancelSent = true
      note('已向 openTCS 撤回运输单', { name })
    }
    const state = await fleetState(name)
    if (state === 'FINISHED') {
      if (cancelSent) await finishException(task, pKey, '取消请求到达时车辆已经完成搬运')
      else await finishSuccess(task, pKey)
      return
    }
    if (state === 'FAILED' || state === 'UNROUTABLE') {
      if (cancelSent) await finishCancel(task, pKey)
      else await finishException(task, pKey, `openTCS 运输单结束于 ${state}`)
      return
    }
    await sleep(pollMs)
  }
  await finishException(task, pKey, '等待 openTCS 超时')
}

async function accept(task) {
  if (inflight.has(task.ID)) return
  const src = bins[task.srcBin]
  const dst = bins[task.dstBin]
  if (!src || !dst) {
    const fresh = await sapOne(task.ID)
    await sapAction(fresh, 'reportException', { code: 'BIN', text: `没有仓位映射：${task.srcBin} -> ${task.dstBin}` })
    return
  }
  inflight.add(task.ID)
  const name = fleetName(task)
  note('接手 SAP 搬运任务', { taskNo: task.taskNo, src: task.srcBin, dst: task.dstBin })
  try {
    if (task.cancelRequested) {
      await sapAction(task, 'acceptCancel', {})
      note('任务在下达后被取消，尚未交给仓库', { taskNo: task.taskNo })
      return
    }
    await moveTu(src.openwms)
    const pKey = await createWmsOrder(dst.openwms)
    note('已创建 OpenWMS 运输单', { pKey })
    try { await changeWmsState(pKey, 'STARTED') } catch (error) {
      note('显式启动运输单没有成功，继续使用当前状态', { error: error.message })
    }
    await createFleetOrder(name, src, dst)
    const fresh = await sapOne(task.ID)
    await sapAction(fresh, 'handover', { externalRef: pKey, fleetOrder: name })
    note('已下发 openTCS 运输单', { name })
    await watchFleet(task, pKey, name)
  } catch (error) {
    note('处理任务失败', { taskNo: task.taskNo, error: error.message })
    try {
      const fresh = await sapOne(task.ID)
      await sapAction(fresh, 'reportException', { code: 'BRIDGE', text: error.message.slice(0, 240) })
    } catch (reportError) {
      note('回写异常也失败了', { error: reportError.message })
    }
  } finally {
    inflight.delete(task.ID)
  }
}

async function loop() {
  const released = await sapTasks(`status eq 'RELEASED'`)
  for (const task of released) {
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
    response.end(JSON.stringify({ inflight: [...inflight], journal: journal.slice(-40) }, null, 2))
  })
  server.listen(8090, '0.0.0.0')
}

async function main() {
  startStatusServer()
  note('桥接启动，等待上下游')
  await waitUntil('SAP', () => req(`${sap}/odata/v4/task/$metadata`))
  await waitUntil('OpenWMS Common', () => req(`${wmsCommon}/actuator/info`))
  await waitUntil('OpenWMS TMS', () => req(`${wmsTms}/actuator/info`))
  await waitUntil('openTCS', () => req(`${fleet}/v1/kernel/version`))
  await ensureWms()
  await ensureFleet()
  note('开始轮询已下达的 SAP 搬运任务')
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
