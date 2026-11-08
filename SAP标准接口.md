# 在本机学习 SAP EWM 标准接口

完整版里的 SAP（端口 4004）模拟的是 S/4HANA 扩展仓库管理（EWM）对外发布的标准接口 **Warehouse Order and Task**，技术名 `API_WAREHOUSE_ORDER_TASK_2`，协议 OData V4。外部 WMS、WCS、AGV 调度系统接 EWM 时最常用的就是它：读出仓库任务，执行完调用确认动作。

不需要公司的测试系统。`docker compose up --build -d` 之后，下面每一步都能在本机 PowerShell 里执行。

## 和真实接口一样的地方

下表中的名字都对照过 SAP 公开资料（SAP 社区文章、SAP 知识库文章 3454353，以及一份针对真实 S/4HANA 的请求样例）：

| 项目 | 值 |
| --- | --- |
| 服务路径 | `/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001/` |
| 命名空间 | `com.sap.gateway.srvd_a2x.api_warehouse_order_task_2.v0001`，URL 里可以写别名 `SAP__self` |
| 实体 | `WarehouseOrder`（仓库单）、`WarehouseTask`（仓库任务） |
| 仓库任务主键 | `EWMWarehouse`、`WarehouseTask`、`WarehouseTaskItem` |
| 仓库单到任务的导航 | `_WarehouseTask` |
| 确认动作 | `SAP__self.ConfirmWarehouseTaskExact`，参数 `DirectWhseTaskConfIsAllowed` |
| 取消动作 | `SAP__self.CancelWarehouseTask` |
| 写操作前 | 先 `HEAD` 带 `X-CSRF-Token: Fetch` 取令牌，再带 `If-Match: <ETag>` |
| 不带直接确认、也没分配资源时 | 400，`/SCWM/ODATA_API/006 Log on to resource first` |
| 字段 | `WarehouseOrder`、`WarehouseTaskStatus`、`SourceStorageBin`、`DestinationStorageBin`、`AlternativeUnit`、`ActualQuantityInAltvUnit`、`SourceHandlingUnit`、`WhseTaskCrtnUTCDateTime` |

状态码沿用 EWM：空字符串是未清，`C` 已确认，`A` 已取消。仓库单下的任务全部确认后，仓库单自动变为 `C`，接口里没有单独确认仓库单的动作。

## 模拟时的取舍

完整元数据要登录 [SAP Business Accelerator Hub](https://api.sap.com/api/WAREHOUSEORDER_0001/overview) 才能下载，下面几处按 SAP 的命名习惯补齐，接真实系统前要以它的 `$metadata` 为准：

- `WarehouseProcessType`、`Product`、`TargetQuantityInAltvUnit`、`WarehouseTaskConfUTCDateTime`、`WarehouseOrderStatus`、`ExecutingResource` 这几个字段名，以及新建任务时的请求体。
- ETag 来自字段 `LastChangeUTCDateTime`。真实系统的 ETag 由后台生成，不一定对应某个可见字段。
- 只实现了「不改数量直接确认」和「取消」。真实接口还有带数量差异的 `ConfirmWarehouseTaskProduct`、给资源分配仓库单的 `AssignWarehouseOrder`、资源登录等。
- CSRF 令牌只校验值本身。真实网关把令牌和会话 cookie 绑在一起，请求要带上取令牌时拿到的 cookie。
- 没有登录认证。真实系统要用通信用户（Basic）或 OAuth。
- 一个仓库任务对应一个仓库单。

## 一步一步调用

先设好服务地址：

```powershell
$svc = 'http://localhost:4004/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001'
```

### 1. 看服务里有什么

```powershell
Invoke-RestMethod "$svc/"
Invoke-WebRequest "$svc/`$metadata" -UseBasicParsing | Select-Object -ExpandProperty Content
```

第一行列出实体集 `WarehouseOrder`、`WarehouseTask`。第二行是元数据 XML，能看到每个字段的类型和两个绑定动作。接真实系统时，第一件事也是拉这份元数据。

### 2. 查未清的仓库任务

外部系统轮询的就是这一句。桥接每 2 秒查一次：

```powershell
(Invoke-RestMethod "$svc/WarehouseTask?`$filter=WarehouseTaskStatus eq ''").value |
  Format-Table WarehouseTask, WarehouseOrder, Product, SourceStorageBin, DestinationStorageBin
```

刚启动时能看到 `1000000001`。等一分钟桥接跑完，它就不在未清列表里了。

也可以从仓库单进去，这是 SAP 资料里常见的写法：

```powershell
(Invoke-RestMethod "$svc/WarehouseOrder(EWMWarehouse='E001',WarehouseOrder='2000000001')/_WarehouseTask").value
```

### 3. 读单个任务，拿到 ETag

```powershell
$key = "WarehouseTask(EWMWarehouse='E001',WarehouseTask='1000000001',WarehouseTaskItem='0')"
$one = Invoke-WebRequest "$svc/$key" -UseBasicParsing
$one.Headers['ETag']
```

三个主键都要写，`WarehouseTaskItem` 一般是 `'0'`。ETag 形如 `W/"2026-11-07T00:00:00.000Z"`，任务每改一次就变一次。

### 4. 取 CSRF 令牌

```powershell
$token = (Invoke-WebRequest -Method Head -Uri "$svc/" -Headers @{ 'X-CSRF-Token' = 'Fetch' } -UseBasicParsing).Headers['x-csrf-token']
```

SAP 网关对所有写请求都要这个令牌。不带的话返回 403，响应头里是 `x-csrf-token: Required`。

### 5. 新建一个任务

```powershell
$new = Invoke-RestMethod -Method Post -Uri "$svc/WarehouseTask" -ContentType 'application/json' `
  -Headers @{ 'X-CSRF-Token' = $token } `
  -Body '{"EWMWarehouse":"E001","WarehouseProcessType":"9999","Product":"MAT-200","TargetQuantityInAltvUnit":2,"AlternativeUnit":"EA","SourceStorageBin":"IPNT-01","DestinationStorageBin":"PICK-01"}'
$new.WarehouseTask
```

返回 201，任务号和仓库单号由 SAP 分配。桥接会在两秒内接手，二三十秒后它变为 `C`。打开 <http://localhost:8090/status>，`links` 里能看到它对应的 OpenWMS 运输单和 openTCS 订单。

真实系统里，仓库任务通常不是外部系统建的，而是 SAP 用户在交货单上创建，或由后台自动生成。这里开放新建，只是为了方便练习。

### 6. 确认任务

这是外部系统完成搬运后必须调用的一步，桥接就是这么做的。对一个未清任务调用（把任务号换成刚建的、还没被桥接确认的那个）：

```powershell
$key = "WarehouseTask(EWMWarehouse='E001',WarehouseTask='$($new.WarehouseTask)',WarehouseTaskItem='0')"
$etag = (Invoke-WebRequest "$svc/$key" -UseBasicParsing).Headers['ETag']
Invoke-RestMethod -Method Post -Uri "$svc/$key/SAP__self.ConfirmWarehouseTaskExact" -ContentType 'application/json' `
  -Headers @{ 'X-CSRF-Token' = $token; 'If-Match' = $etag } `
  -Body '{"DirectWhseTaskConfIsAllowed":true}'
```

桥接通常会抢先确认，所以手动练这一步时，可以先 `docker compose stop bridge`，练完再 `docker compose start bridge`。

### 7. 故意出错

把第 6 步改一改，就能看到真实系统里最常遇到的四种错误：

| 改法 | 返回 | 说明 |
| --- | --- | --- |
| 去掉 `X-CSRF-Token` | 403，`x-csrf-token: Required` | 先做第 4 步 |
| 去掉 `If-Match` | 428 | 写操作必须带 ETag |
| `If-Match` 用旧的 ETag | 412 | 别人刚改过，重新读一次再确认 |
| Body 换成 `{}` | 400，`Log on to resource first` | 没给仓库单分配资源时，要带 `DirectWhseTaskConfIsAllowed: true` |
| 对已确认的任务再确认 | 400 | 只有未清任务能确认 |

### 8. 在 SAP 里取消

```powershell
$etag = (Invoke-WebRequest "$svc/$key" -UseBasicParsing).Headers['ETag']
Invoke-RestMethod -Method Post -Uri "$svc/$key/SAP__self.CancelWarehouseTask" -ContentType 'application/json' `
  -Headers @{ 'X-CSRF-Token' = $token; 'If-Match' = $etag } -Body '{}'
```

如果车辆正在执行这个任务，桥接下一次查 SAP 时看到状态 `A`，会撤回 openTCS 订单，并把 OpenWMS 运输单置为取消。桥接日志写「SAP 取消了仓库任务，已向 openTCS 撤回运输单」。

## 桥接按什么顺序调用

`bridge/index.js` 里和 SAP 有关的只有这几步，换成真实 EWM 时顺序不变：

1. `GET WarehouseTask?$filter=WarehouseTaskStatus eq ''`，找未清任务。
2. 在 OpenWMS、openTCS 下单，自己记下对照关系。标准接口没有存外部单号的字段。
3. 执行期间反复 `GET` 这个任务，看 SAP 有没有取消。
4. 搬完后 `GET` 拿最新 ETag，`HEAD` 取令牌（有缓存，403 时重取），`POST ...SAP__self.ConfirmWarehouseTaskExact`。
5. 搬运失败时不改 SAP，任务保持未清，桥接停手并在日志里写原因，等人处理。

## 以后接真实系统要换什么

- `SAP_URL` 改成真实主机，`sap-client` 按需要加在查询参数里。
- 加认证：通信用户的 Basic 认证，或 OAuth。
- 取令牌时保存返回的 cookie，后续写请求一起带上。
- 仓位名换成真实系统里的仓位，桥接里的 `bins` 对照表跟着改。
- 用真实系统的 `$metadata` 核对上面「模拟时的取舍」里列的字段。

## 其他相关标准接口

这次只模拟了仓库任务。完整的仓库对接还会用到：

| 接口 | 协议 | 用途 |
| --- | --- | --- |
| `API_OUTBOUND_DELIVERY_SRV` | OData V2 | 拣货确认后过账发货 |
| `API_INBOUND_DELIVERY_SRV` | OData V2 | 上架确认后过账收货 |
| `api_warehouse_resource_2` | OData V4 | 仓库资源（叉车、AGV）登录登出 |
| 经典 WM 的 IDoc `WMTORD` / `WMTOCO` | IDoc | 老系统下发转储单、回传确认 |
