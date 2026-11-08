# SAP 到车队的任务管理学习环境

这条环境用来看清一笔搬运任务怎么从 SAP 下达到仓库，再交给车队执行，最后把结果写回去。车辆不会真的动，openTCS 的 Loopback 驱动会按路线走完并回报状态。

## 运行

只需要 Docker Desktop，不用装 Java 或 Node。

1. 安装并启动 Docker Desktop。电脑要是 64 位 x86，ARM 版 Windows 不行，OpenWMS 镜像只有 amd64。内存 8 GB 够用，磁盘留 5 GB 以上。
2. 在 GitHub 仓库页面点 **Code → Download ZIP** 并解压，或者 `git clone`。
3. 在这个目录里打开 PowerShell，执行：

   ```powershell
   docker compose up --build -d
   ```

   第一次要下载镜像并构建，需要几分钟。
4. 浏览器打开 <http://localhost:8090/status>，出现「搬运完成，状态已回到 SAP」就是跑通了。也可以打开 <http://localhost:4004/odata/v4/task/Tasks>，任务 `1000000001` 的 `status` 是 `CONFIRMED`。

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

## 注意

- 仓库里只有自己写的源码，`@sap/cds` 在构建时从 npm 下载，下载的人各自接受 SAP 开发者许可，所以仓库可以公开。不要提交 `node_modules`，也不要把打好的 `sap` 镜像推到公开镜像仓库或附在 Release 里：这个许可不允许把 SAP 的软件转给第三方。
- 第一次构建要访问 Docker Hub、npm 和 GitHub（下载 openTCS 7.5.0）。拉镜像卡住时，在 Docker Desktop 的设置里配置代理或镜像加速。
- 端口 `4004`、`8090`、`8120`、`8131`、`55200` 不能被别的程序占用。
- Docker 的虚拟磁盘默认在 C 盘。C 盘空间不多时，先在 Docker Desktop 的 **Settings → Resources → Advanced** 里把磁盘位置改到 D 盘。
