# SAP 到车队的任务管理学习环境

这条环境用来看清一笔搬运任务怎么从 SAP 下达到仓库，再交给车队执行，最后把结果写回去。车辆不会真的动，openTCS 的 Loopback 驱动会按路线走完并回报状态。

仓库里有两套链路，由下面这一条命令一起启动。完整版用真实的 SAP CAP、OpenWMS 和 openTCS。简化版在 `python/` 目录，用 Python 标准库写成五个小服务，放在同一个容器里跑。架构和任务 `1000000001` 的逐步对应见 [架构.md](架构.md)。

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

   第一次要下载镜像并构建，需要几分钟。
4. 打开 <http://localhost:8080>。这一页是架构图，每个框里的文字是该服务此刻的真实结果，不是画上去的示例。两条链路的任务 `1000000001` 都显示「已确认」，库区平面上两块牌子都停在拣选位，才算跑通。完整版大约一分钟，Python 大约 5 秒，页面每 2 秒自己刷新。

停掉用 `docker compose down`。数据都在内存里，再次 `docker compose up -d` 会从预制任务重新跑。

## 再下一笔任务

任务 `1000000002` 初始是 `CREATED`。下达时要带上它当前的 ETag：

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:4004/odata/v4/task/Tasks(7b1e8c2a-0000-4000-8000-000000000002)/TaskService.release' -ContentType 'application/json' -Headers @{ 'If-Match' = 'W/"2026-11-07T00:00:00.000Z"' } -Body '{}'
```

桥接只接手 `RELEASED` 的任务，大约二十秒后这笔也会变成 `CONFIRMED`。

## 链路

1. SAP CAP 里有一笔已下达的搬运任务，状态是 `RELEASED`。
2. 桥接把它对应的托盘先放到源仓位，再向 OpenWMS 创建运输单。
3. 桥接向 openTCS 下一张运输单：到入库位装货，再到拣选位卸货。
4. Loopback 车辆跑完后，桥接把 OpenWMS 运输单改为完成，并确认 SAP 任务。

状态对应关系：

| SAP | OpenWMS | openTCS |
| --- | --- | --- |
| RELEASED | 创建运输单 | |
| IN_PROCESS | STARTED | BEING_PROCESSED |
| CONFIRMED | FINISHED | FINISHED |
| CANCELLED | CANCELED | FAILED（撤回之后） |
| EXCEPTION | ONFAILURE | FAILED 或 UNROUTABLE |

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
| SAP CAP | `chain/sap.py`：任务带版本号，动作要带 If-Match，版本不对返回 412，状态不对返回 409 |
| OpenWMS Common + TMS | `chain/wms.py`：托盘和运输单，运输单完成时托盘移到目标库位 |
| openTCS 内核 | `chain/fleet.py`：运输订单分配给空闲车辆，按路线拆成一段段行驶任务下发 |
| Loopback 驱动 | `chain/vehicle.py`：沿路线每走一步、每做完一个动作就向车队回报 |
| `bridge/index.js` | `chain/bridge.py`：轮询 `RELEASED` 任务，依次在 WMS、车队下单，最后回写 SAP |

只想看 Python 源码、不启动完整版时，在 `python` 目录执行 `python -m chain`（需要 Python 3.10 以上）。这和根目录那条命令二选一。测试在 `python` 目录里执行 `python -m unittest -b`。

## 注意

- 仓库里只有自己写的源码，`@sap/cds` 在构建时从 npm 下载，下载的人各自接受 SAP 开发者许可，所以仓库可以公开。不要提交 `node_modules`，也不要把打好的 `sap` 镜像推到公开镜像仓库或附在 Release 里：这个许可不允许把 SAP 的软件转给第三方。
- 第一次构建要访问 Docker Hub、npm 和 GitHub（下载 openTCS 7.5.0）。拉镜像卡住时，在 Docker Desktop 的设置里配置代理或镜像加速。
- 端口 `4004`、`8080`、`8090`、`8120`、`8131`、`55200`、`9004`、`9090`、`9120`、`9200`、`9300` 不能被别的程序占用。调度板是 `8080`。
- Docker 的虚拟磁盘默认在 C 盘。C 盘空间不多时，先在 Docker Desktop 的 **Settings → Resources → Advanced** 里把磁盘位置改到 D 盘。
