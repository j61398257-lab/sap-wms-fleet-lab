# SAP 到车队的任务管理学习环境

这条环境用来看清一笔搬运任务怎么从 SAP 下达到仓库，再交给车队执行，最后把结果写回去。车辆不会真的动，openTCS 的 Loopback 驱动会按路线走完并回报状态。

仓库里有两套链路，由下面这一条命令一起启动。完整版用真实的 SAP CAP、OpenWMS 和 openTCS。简化版在 `python/` 目录，用 Python 标准库写成五个小服务，放在同一个容器里跑。架构和任务 `1000000001` 的逐步对应见 [架构.md](架构.md)。完整版的 SAP 按 EWM 标准接口 `API_WAREHOUSE_ORDER_TASK_2` 模拟，学习这个接口见 [SAP标准接口.md](SAP标准接口.md)。

`docs/figures/` 里有五张图，每张都有中英文两版的 PDF、SVG 和 600 dpi PNG，由 `make_figures.py` 生成：

| 图 | 内容 | 在哪篇文档里讲 |
| --- | --- | --- |
| `fig1_interfaces` | 系统与接口总览、23 个接口清单 | [SAP标准接口.md](SAP标准接口.md) |
| `fig2_sequence` | 任务 1000000001 的调用时序 | [SAP标准接口.md](SAP标准接口.md) |
| `fig3_confirm` | 确认请求的校验链、仓库任务和仓库单的状态 | [SAP标准接口.md](SAP标准接口.md) |
| `fig4_architecture` | 分层架构原理、单号和状态的换算 | [架构.md](架构.md) |
| `fig5_run_state` | 一次真实运行中各系统状态随时间的变化，数据在 `run_trace.json` | [架构.md](架构.md) |

`board_snapshot.png` 是同一次运行结束时调度板的截图。

## 运行

只需要 Docker Desktop，不用装 Java、Node 或 Python。

1. 安装并启动 Docker Desktop。电脑要是 64 位 x86，ARM 版 Windows 不行，OpenWMS 镜像只有 amd64。内存 8 GB 够用，磁盘留 5 GB 以上。
2. 下载代码，不用登录 GitHub。在 PowerShell 里执行：

   ```powershell
   curl.exe -L -o sap-wms-fleet-lab.zip https://github.com/j61398257-lab/sap-wms-fleet-lab/archive/refs/heads/main.zip
   tar -xf sap-wms-fleet-lab.zip
   cd sap-wms-fleet-lab-main
   ```

   也可以在仓库页面点 **Code → Download ZIP**，解压后进入 `sap-wms-fleet-lab-main`。
3. 启动全部容器，包含完整版和 Python 简化版：

   ```powershell
   docker compose up --build -d
   ```

   第一次要下载镜像并构建，视网速大约 5 到 10 分钟，其中最慢的是从 GitHub 下载 87 MB 的 openTCS。以后再启动只要几十秒。
4. 打开 <http://localhost:8080>。这一页是架构图，每个框里的文字是该服务此刻的真实结果，不是画上去的示例。两条链路的任务 `1000000001` 都显示「已确认」，库区平面上两块牌子都停在拣选位，才算跑通。完整版大约一分钟，Python 大约 5 秒，页面每 2 秒自己刷新。

停掉用 `docker compose down`。数据都在内存里，再次 `docker compose up -d` 会从预制任务重新跑。

## 不在本机构建

第 3 步要访问 Docker Hub、Debian 软件源和 GitHub 三处。连不上 Docker Hub 时，可以改用 GitHub 预先构建好的镜像，有两种取法，启动命令相同。

**在线拉取。** 8 个镜像都放在 GitHub 的镜像仓库 `ghcr.io/j61398257-lab/sap-wms-fleet-lab`，不用登录。在仓库目录执行：

```powershell
docker compose -f compose.yaml -f compose.ghcr.yaml up -d
```

`compose.ghcr.yaml` 把每个服务换成 `ghcr.io` 上的镜像，本机不再构建，大约下载 650 MB。

**离线导入。** 在 [Releases](https://github.com/j61398257-lab/sap-wms-fleet-lab/releases/latest) 页面下载 `sap-wms-fleet-lab-images.tar.gz`（约 640 MB），这是同样 8 个镜像打成的一个文件。可以在能上网的电脑下载后拷过来，放进仓库目录，执行：

```powershell
docker load -i sap-wms-fleet-lab-images.tar.gz
docker compose -f compose.yaml -f compose.ghcr.yaml up -d
```

镜像已经在本机，所以不会再联网。之后的启动、停止都在后面加同样的 `-f` 参数，例如 `docker compose -f compose.yaml -f compose.ghcr.yaml down`。

这两种镜像由 `.github/workflows/images.yml` 生成：每次推送 main 会重新发布 `ghcr.io` 上的镜像，推送 `v` 开头的标签会额外生成离线镜像包。改了本地代码想看效果时，还是用第 3 步的 `docker compose up --build -d`。

## 再下一笔任务

完整版的 SAP 模拟的是 S/4HANA EWM 的标准接口 `API_WAREHOUSE_ORDER_TASK_2`，路径、实体名、字段名、确认动作和真实系统一样。用标准接口新建一个仓库任务，要先取 CSRF 令牌：

```powershell
$svc = 'http://localhost:4004/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001'
$token = (Invoke-WebRequest -Method Head -Uri "$svc/" -Headers @{ 'X-CSRF-Token' = 'Fetch' } -UseBasicParsing).Headers['x-csrf-token']
Invoke-RestMethod -Method Post -Uri "$svc/WarehouseTask" -ContentType 'application/json' -Headers @{ 'X-CSRF-Token' = $token } -Body '{"EWMWarehouse":"E001","WarehouseProcessType":"9999","Product":"MAT-200","TargetQuantityInAltvUnit":2,"AlternativeUnit":"EA","SourceStorageBin":"IPNT-01","DestinationStorageBin":"PICK-01"}'
```

桥接只接手未清（`WarehouseTaskStatus` 为空）的任务，大约二十秒后这笔会变成 `C`。每一步请求的含义、怎么取消、会遇到哪些错误，见 [SAP标准接口.md](SAP标准接口.md)。

## 链路

1. SAP 里有一个未清的仓库任务 `1000000001`，属于仓库单 `2000000001`。
2. 桥接把对应的托盘先放到源仓位，再向 OpenWMS 创建运输单。
3. 桥接向 openTCS 下一张运输单：到入库位装货，再到拣选位卸货。
4. Loopback 车辆跑完后，桥接把 OpenWMS 运输单改为完成，并在 SAP 调用 `ConfirmWarehouseTaskExact` 确认仓库任务。仓库单下的任务都确认后，仓库单自动变成 `C`。

标准接口没有「交接」和「回写外部单号」，执行期间 SAP 一直是未清。SAP 任务对应哪张 OpenWMS 运输单、哪张 openTCS 订单，记在桥接里，<http://localhost:8090/status> 的 `links` 能看到。

状态对应关系：

| SAP 仓库任务 | OpenWMS | openTCS |
| --- | --- | --- |
| 未清 `''` | 创建运输单，STARTED | BEING_PROCESSED |
| 已确认 `C` | FINISHED | FINISHED |
| 已取消 `A`（在 SAP 里取消） | CANCELED | FAILED（撤回之后） |
| 仍是未清，桥接停手 | ONFAILURE | FAILED 或 UNROUTABLE |

源仓位 `IPNT-01` 对应 OpenWMS 的 `FGIN/IPNT/0001/0000/0000`，目标仓位 `PICK-01` 对应 `FGIN/PICK/WORK/0001/0000`。

`common-compat` 夹在 OpenWMS 的两个服务之间。TMS 2.0 查库位组时只认单个对象，Common 3.0 不带名字时返回数组，它把数组取成一个对象。

## Python 简化版

`python/` 目录用 Python 标准库把同一条链路写成五个小服务，只演示正常完成。上面的 `docker compose up --build -d` 已经把它放进 `python-chain` 容器，不要再在本机执行 `python -m chain`，端口会冲突。接口是简化过的，路径和字段不等于真实的 OData、OpenWMS、openTCS 接口。

容器日志里按时间打印每个系统的状态变化：

```powershell
docker compose logs python-chain
```

大约 5 秒后出现「任务 1000000001 搬运完成，结果已回写 SAP」。运行中可以在浏览器打开：

| 系统 | 地址 |
| --- | --- |
| SAP 任务 | <http://localhost:9004/tasks> |
| WMS 运输单 | <http://localhost:9120/transport-orders> |
| 车队运输订单 | <http://localhost:9200/transport-orders> |
| 车辆 | <http://localhost:9300/state> |
| 桥接日志 | <http://localhost:9090/status> |

和完整版的对应关系：

| 完整版 | 简化版 |
| --- | --- |
| SAP CAP（EWM 标准接口形状） | `chain/sap.py`：自定义的任务接口，不是 EWM 标准形状。任务带版本号，动作要带 If-Match，版本不对返回 412，状态不对返回 409 |
| OpenWMS Common + TMS | `chain/wms.py`：托盘和运输单，运输单完成时托盘移到目标库位 |
| openTCS 内核 | `chain/fleet.py`：运输订单分配给空闲车辆，按路线拆成一段段行驶任务下发 |
| Loopback 驱动 | `chain/vehicle.py`：沿路线每走一步、每做完一个动作就向车队回报 |
| `bridge/index.js` | `chain/bridge.py`：轮询已下达的任务，依次在 WMS、车队下单，最后回写 SAP |

不用 Docker、直接在本机跑 Python 版（需要 Python 3.10 以上，只用标准库）：

```powershell
docker compose down
cd python
python -m chain
```

这和根目录那条 Docker 命令二选一，容器开着时端口会冲突，所以先 `docker compose down`。几秒后日志里出现「任务 1000000001 搬运完成，结果已回写 SAP」，按 Ctrl+C 停止。测试在 `python` 目录里执行 `python -m unittest -b`，它用临时端口，容器开着也能跑。

## 重新生成图

`docs/figures` 里的图已经生成好，直接打开就能看。改了代码想重新出图时，需要 Python 3.10 以上和 matplotlib：

```powershell
pip install matplotlib
docker compose down
python docs/figures/record_run.py
cd docs/figures
python make_figures.py
```

`record_run.py` 会自己执行 `docker compose up -d`，在两条链路都确认后停止采样，把数据写进 `run_trace.json`。`make_figures.py` 读这份数据，生成中英文两版共十张图。只改了文字、不需要重新采样时，跳过前两行命令即可。

## 注意

- 仓库里只有自己写的源码，`@sap/cds` 在构建时从 npm 下载，下载的人各自接受 SAP 开发者许可，所以仓库可以公开。不要提交 `node_modules`，也不要把打好的 `sap` 镜像推到公开镜像仓库或附在 Release 里：这个许可不允许把 SAP 的软件转给第三方。
- 第一次构建要访问 Docker Hub、npm 和 GitHub（下载 openTCS 7.5.0）。拉镜像卡住时，在 Docker Desktop 的设置里配置代理或镜像加速。
- 端口 `4004`、`8080`、`8090`、`8120`、`8131`、`55200`、`9004`、`9090`、`9120`、`9200`、`9300` 不能被别的程序占用。调度板是 `8080`。
- Docker 的虚拟磁盘默认在 C 盘。C 盘空间不多时，先在 Docker Desktop 的 **Settings → Resources → Advanced** 里把磁盘位置改到 D 盘。
