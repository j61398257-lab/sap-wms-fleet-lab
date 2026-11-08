"""生成接口总览、调用时序和确认校验三张图，输出 PDF、SVG 和 600 dpi PNG。

用法：python make_figures.py [zh|en]，不带参数时两种语言都生成。
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

OUT = Path(__file__).resolve().parent
LANG = 'zh'

SANS = ['Arial', 'Microsoft YaHei']
MONO = ['Consolas', 'Microsoft YaHei']
plt.rcParams.update({
    'font.family': SANS,
    'font.size': 6.5,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
    'axes.unicode_minus': False,
})

# Okabe-Ito 色板，色弱读者也能区分
SAP = '#0072B2'
BRIDGE = '#E69F00'
WMS = '#009E73'
TCS = '#D55E00'
CAR = '#CC79A7'
INK = '#222222'
GREY = '#6B6B6B'
LINE = '#9A9A9A'
BAD = '#B2182B'


def T(zh, en):
    return zh if LANG == 'zh' else en


def tint(color, amount):
    color = color.lstrip('#')
    rgb = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
    mixed = [round(c + (255 - c) * amount) for c in rgb]
    return '#' + ''.join(f'{c:02x}' for c in mixed)


def canvas(width, height):
    fig = plt.figure(figsize=(width / 25.4, height / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis('off')
    return fig, ax


def box(ax, x, y, w, h, fc='white', ec=INK, lw=0.6, ls='-', r=1.0, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}',
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def arrow(ax, x1, y1, x2, y2, color=INK, dashed=False, lw=0.6, z=3, rad=0.0, head=5):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=head,
                                 color=color, lw=lw, ls=(0, (3, 2)) if dashed else '-',
                                 shrinkA=0, shrinkB=0, zorder=z,
                                 connectionstyle=f'arc3,rad={rad}'))


def text(ax, x, y, s, size=6.5, color=INK, ha='left', va='center', weight='normal', mono=False,
         bg=None, z=5, style='normal', rotation=0):
    kwargs = {}
    if bg:
        kwargs['bbox'] = dict(fc=bg, ec='none', pad=0.6)
    ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, fontweight=weight, zorder=z,
            family=MONO if mono else SANS, fontstyle=style, rotation=rotation,
            linespacing=1.25, **kwargs)


def panel(ax, x, y, letter):
    text(ax, x, y, letter, size=9, weight='bold', va='top')


def save(fig, name):
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(OUT / f'{name}_{LANG}.{ext}', dpi=600 if ext == 'png' else None)
    plt.close(fig)


# ---------------------------------------------------------------- 图 1

def system(ax, x, y, w, h, color, title, subtitle, lines=()):
    box(ax, x, y, w, h, fc=tint(color, 0.9), ec=color, lw=0.8)
    ax.add_patch(Rectangle((x + 0.4, y + 0.4), 1.4, h - 0.8, fc=color, ec='none', zorder=3))
    text(ax, x + 3.2, y + 3.2, title, size=7, weight='bold')
    text(ax, x + 3.2, y + 6.6, subtitle, size=5.8, color=GREY)
    for i, line in enumerate(lines):
        text(ax, x + 3.2, y + 10.6 + i * 3.4, line, size=6)


def figure_interfaces():
    W, H = 180, 211
    fig, ax = canvas(W, H)

    panel(ax, 1.5, 2, 'a')
    # SAP
    box(ax, 4, 7, 50, 64, fc=tint(SAP, 0.9), ec=SAP, lw=0.8)
    ax.add_patch(Rectangle((4.4, 7.4), 1.4, 63.2, fc=SAP, ec='none', zorder=3))
    text(ax, 7.2, 10.4, 'SAP S/4HANA EWM', size=7, weight='bold')
    text(ax, 7.2, 13.8, T('本项目由 SAP CAP 模拟 · :4004', 'mocked with SAP CAP · :4004'), size=5.8, color=GREY)
    text(ax, 7.2, 18.4, 'API_WAREHOUSE_ORDER_TASK_2', size=6.2, weight='bold', mono=True)
    text(ax, 7.2, 21.6, T('OData V4 · 服务定义 srvd_a2x · 版本 0001', 'OData V4 · srvd_a2x · version 0001'), size=5.8, color=GREY)
    box(ax, 8, 25, 42, 12, fc='white', ec=SAP, lw=0.5, r=0.6)
    text(ax, 10, 28, 'WarehouseOrder', size=6.2, weight='bold', mono=True)
    text(ax, 10, 31.4, 'key EWMWarehouse, WarehouseOrder', size=5.4, mono=True, color=GREY)
    text(ax, 10, 34.4, 'WarehouseOrderStatus', size=5.4, mono=True, color=GREY)
    ax.plot([29, 29], [37, 42], color=SAP, lw=0.5, zorder=3)
    text(ax, 30.2, 39.5, '_WarehouseTask  1 : n', size=5.4, mono=True, color=SAP)
    box(ax, 8, 42, 42, 25, fc='white', ec=SAP, lw=0.5, r=0.6)
    text(ax, 10, 45, 'WarehouseTask', size=6.2, weight='bold', mono=True)
    text(ax, 10, 48.4, 'key EWMWarehouse, WarehouseTask,', size=5.4, mono=True, color=GREY)
    text(ax, 10, 51.2, '    WarehouseTaskItem', size=5.4, mono=True, color=GREY)
    text(ax, 10, 54.2, 'WarehouseTaskStatus, Product, …Bin', size=5.4, mono=True, color=GREY)
    ax.plot([10, 48], [56.6, 56.6], color=tint(SAP, 0.5), lw=0.4, zorder=3)
    text(ax, 10, 59.4, 'ConfirmWarehouseTaskExact()', size=5.4, mono=True, color=SAP)
    text(ax, 10, 62.6, 'CancelWarehouseTask()', size=5.4, mono=True, color=SAP)

    # 桥接
    system(ax, 74, 22, 36, 30, BRIDGE, T('桥接 bridge', 'Bridge'), 'Node.js · :8090',
           [T('轮询未清任务', 'polls open tasks'), T('换算仓位名', 'maps bin names'),
            T('记录任务 ↔ 外部单号', 'keeps task ↔ order links'), T('完成后回 SAP 确认', 'confirms back to SAP')])

    # 右侧三个系统
    system(ax, 132, 4, 44, 15, WMS, 'OpenWMS Common', ':8120',
           [T('库位 Location · 托盘 TransportUnit', 'Location · TransportUnit')])
    system(ax, 132, 23, 44, 15, WMS, 'OpenWMS TMS', T(':8131 · 经 common-compat 查库位组', ':8131 · via common-compat'),
           [T('运输单 TransportOrder', 'TransportOrder')])
    system(ax, 132, 42, 44, 15, TCS, T('openTCS 7.5 内核', 'openTCS 7.5 kernel'), T(':55200 · Web API', ':55200 · Web API'),
           [T('运输订单 · 路线 · 派车', 'transport orders · routing')])
    system(ax, 132, 61, 44, 10, CAR, 'Vehicle-01', T('Loopback 虚拟驱动', 'Loopback virtual driver'))

    def link(x1, y1, x2, y2, color, label, side=-1.6, lx=None, ly=None, ha='center'):
        arrow(ax, x1, y1, x2, y2, color=INK)
        arrow(ax, x2, y2 + 1.4 * (1 if y2 >= y1 else 1), x1, y1 + 1.4, color=GREY, dashed=True)
        text(ax, lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2 + side,
             label, size=6, ha=ha, color=color, weight='bold', bg='white')

    link(74, 34, 54, 34, SAP, 'S1–S5', lx=64, ly=31.2)
    text(ax, 64, 39.2, 'OData V4', size=5.6, ha='center', color=GREY)
    link(110, 26, 132, 12, WMS, 'C1–C4', lx=121, ly=15.6)
    link(110, 33, 132, 30, WMS, 'T1–T4', lx=121, ly=29)
    link(110, 42, 132, 49, TCS, 'F1–F6', lx=121, ly=48.6)
    text(ax, 121, 54.4, 'REST · JSON', size=5.6, ha='center', color=GREY)
    arrow(ax, 151, 57, 151, 61, color=INK)
    arrow(ax, 157, 61, 157, 57, color=GREY, dashed=True)
    text(ax, 158.5, 59, T('进程内驱动接口', 'in-process driver API'), size=5.4, color=GREY)

    # SAP 侧调用和观测
    box(ax, 4, 75, 50, 7, fc='white', ec=GREY, lw=0.5, ls=(0, (2, 1.5)))
    text(ax, 29, 78.5, T('SAP 用户 / 练习脚本：S6 取消、S7 新建', 'SAP user / exercise: S6 cancel, S7 create'),
         size=5.8, ha='center', color=GREY)
    arrow(ax, 29, 75, 29, 71, color=GREY)
    box(ax, 74, 62, 36, 9, fc='white', ec=GREY, lw=0.5, ls=(0, (2, 1.5)))
    text(ax, 92, 65.2, T('调度板 board · :8080', 'Status board · :8080'), size=6, ha='center')
    text(ax, 92, 68.6, T('只读：B1 及各系统查询接口', 'read-only: B1 and GET endpoints'), size=5.4, ha='center', color=GREY)
    arrow(ax, 92, 62, 92, 52, color=GREY, dashed=True)

    # 图例
    lx, ly = 116, 77.5
    arrow(ax, lx, ly, lx + 7, ly)
    text(ax, lx + 8.5, ly, T('请求', 'request'), size=5.8)
    arrow(ax, lx + 19, ly, lx + 26, ly, color=GREY, dashed=True)
    text(ax, lx + 27.5, ly, T('响应 / 回报', 'response / report'), size=5.8)
    text(ax, lx, ly + 3.6, T('编号与 b 表、图 2 中的消息一致', 'IDs match table b and Fig. 2'), size=5.4, color=GREY)

    # ---- b 接口清单
    top = 88
    panel(ax, 1.5, top - 1, 'b')
    cols = [(4, T('编号', 'ID')), (12, T('方法', 'Method')), (24, T('路径', 'Path')),
            (113, T('作用', 'Purpose')), (157, T('阶段', 'Phase'))]
    y = top + 3
    for cx, name in cols:
        text(ax, cx, y, name, size=6.2, weight='bold')
    ax.plot([4, 176], [y + 2.2, y + 2.2], color=INK, lw=0.8)
    ax.plot([4, 176], [top, top], color=INK, lw=0.8)
    y += 2.2

    groups = [
        (SAP, T('SAP EWM · {EWM} = /sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001',
                'SAP EWM · {EWM} = /sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001'),
         T("(…) = (EWMWarehouse='E001',WarehouseTask='1000000001',WarehouseTaskItem='0')；写操作需 X-CSRF-Token 与 If-Match",
           "(…) = (EWMWarehouse='E001',WarehouseTask='1000000001',WarehouseTaskItem='0'); writes need X-CSRF-Token and If-Match"),
         [('S1', 'GET', '{EWM}/$metadata', T('就绪探测，读元数据', 'readiness, metadata'), '①'),
          ('S2', 'GET', "{EWM}/WarehouseTask?$filter=WarehouseTaskStatus eq ''", T('轮询未清仓库任务', 'poll open warehouse tasks'), '②'),
          ('S3', 'GET', '{EWM}/WarehouseTask(…)', T('读任务状态与 ETag', 'read status and ETag'), '⑤ ⑥'),
          ('S4', 'HEAD', '{EWM}/        X-CSRF-Token: Fetch', T('取 CSRF 令牌', 'fetch CSRF token'), '⑥'),
          ('S5', 'POST', '{EWM}/WarehouseTask(…)/SAP__self.ConfirmWarehouseTaskExact', T('确认仓库任务', 'confirm warehouse task'), '⑥'),
          ('S6', 'POST', '{EWM}/WarehouseTask(…)/SAP__self.CancelWarehouseTask', T('取消仓库任务', 'cancel warehouse task'), T('SAP 侧', 'SAP side')),
          ('S7', 'POST', '{EWM}/WarehouseTask', T('新建仓库任务', 'create warehouse task'), T('SAP 侧', 'SAP side'))]),
        (WMS, 'OpenWMS Common · http://openwms-common:8120', None,
         [('C1', 'GET', '/actuator/info', T('就绪探测', 'readiness'), '①'),
          ('C2', 'GET POST', '/v1/locations?locationId=…', T('查询 / 创建库位', 'find / create location'), '①'),
          ('C3', 'GET POST', '/v1/transport-units?bk=…[&actualLocation=…&tut=PALLET]', T('查询 / 创建托盘', 'find / create pallet'), '①'),
          ('C4', 'PATCH', '/v1/transport-units?bk=…&newLocation=…', T('移动托盘', 'move pallet'), '③ ⑥')]),
        (WMS, 'OpenWMS TMS · http://openwms-tms:8131', None,
         [('T1', 'GET', '/actuator/info', T('就绪探测', 'readiness'), '①'),
          ('T2', 'POST', '/v1/transport-orders', T('创建运输单，返回 201 + Location', 'create order, 201 + Location'), '③'),
          ('T3', 'GET', '/v1/transport-orders/{pKey}', T('读运输单状态', 'read order state'), '③ ⑥'),
          ('T4', 'POST', '/v1/transport-orders/{pKey}?state=STARTED|FINISHED|ONFAILURE|CANCELED', T('改运输单状态', 'change order state'), '③ ⑥')]),
        (TCS, 'openTCS · http://opentcs:55200', None,
         [('F1', 'GET', '/v1/kernel/version', T('就绪探测', 'readiness'), '①'),
          ('F2', 'GET PUT', '/v1/plantModel', T('读取 / 上传工厂模型', 'read / upload plant model'), '①'),
          ('F3', 'PUT', '/v1/vehicles/Vehicle-01/commAdapter/{attachment,enabled}, …/integrationLevel',
           T('挂 Loopback 驱动并允许接单', 'attach Loopback, allow orders'), '①'),
          ('F4', 'POST', '/v1/transportOrders/SAP-{WarehouseTask}', T('下运输订单：装货 → 卸货', 'create order: load → unload'), '④'),
          ('F5', 'GET', '/v1/transportOrders/SAP-{WarehouseTask}', T('读订单状态', 'read order state'), '⑤'),
          ('F6', 'POST', '/v1/transportOrders/SAP-{WarehouseTask}/withdrawal?immediate=false', T('撤回订单', 'withdraw order'), T('取消', 'cancel'))]),
        (BRIDGE, T('桥接 · http://bridge:8090', 'Bridge · http://bridge:8090'), None,
         [('B1', 'GET', '/status   /health', T('进度、对照 links、日志', 'progress, links, journal'), T('观测', 'observe'))]),
    ]
    row = 3.9
    for color, title, note, rows in groups:
        height = row * (2 if note else 1)
        ax.add_patch(Rectangle((4, y), 172, height, fc=tint(color, 0.88), ec='none', zorder=1))
        ax.add_patch(Rectangle((4, y), 1.0, height, fc=color, ec='none', zorder=2))
        text(ax, 6.4, y + row / 2, title, size=5.8, weight='bold', mono=title.startswith('SAP'))
        if note:
            text(ax, 6.4, y + row * 1.5, note, size=5.4, color=GREY, mono=True)
        y += height
        for i, (rid, method, path, purpose, phase) in enumerate(rows):
            text(ax, 4.6, y + row / 2, rid, size=6, weight='bold', color=color)
            text(ax, 12, y + row / 2, method, size=5.8, mono=True)
            text(ax, 24, y + row / 2, path, size=5.6, mono=True)
            text(ax, 113, y + row / 2, purpose, size=6)
            text(ax, 157, y + row / 2, phase, size=6)
            y += row
            ax.plot([4, 176], [y, y], color='#DDDDDD', lw=0.3, zorder=1)
    ax.plot([4, 176], [y, y], color=INK, lw=0.8)
    text(ax, 4, y + 3.4, T('阶段：① 初始化  ② 查询任务  ③ 仓库下单  ④ 车队下单  ⑤ 执行监控  ⑥ 回写确认（与图 2 对应）。'
                           '车辆与 openTCS 之间是进程内驱动接口，没有 HTTP 端点。',
                           'Phases: ① init  ② query  ③ WMS order  ④ fleet order  ⑤ monitor  ⑥ confirm (see Fig. 2). '
                           'Vehicle and kernel talk through an in-process driver API, not HTTP.'),
         size=5.6, color=GREY)
    save(fig, 'fig1_interfaces')


# ---------------------------------------------------------------- 图 2

def figure_sequence():
    W = 180
    lanes = {
        'sap': (30, SAP, 'SAP EWM', ':4004'),
        'br': (84, BRIDGE, T('桥接', 'Bridge'), ':8090'),
        'com': (108, WMS, 'OpenWMS', 'Common :8120'),
        'tms': (129, WMS, 'OpenWMS', 'TMS :8131'),
        'tcs': (150, TCS, 'openTCS', ':55200'),
        'car': (168, CAR, 'Vehicle-01', 'Loopback'),
    }
    X = {k: v[0] for k, v in lanes.items()}

    # (类型, 参数...)；msg: 起点, 终点, 主标签, 细节, 是否响应
    steps = [
        ('phase', '①', T('初始化', 'init'), T('启动时', 'startup')),
        ('ref', T('ref  初始化（桥接启动时一次）：S1 · C1–C3 · T1 · F1–F3    建库位与托盘、上传工厂模型、启用 Loopback 车辆',
                  'ref  initialisation (once at start-up): S1 · C1–C3 · T1 · F1–F3    locations, pallet, plant model, Loopback vehicle')),
        ('phase', '②', T('查询', 'query'), 't = 0 s'),
        ('msg', 'br', 'sap', "S2  GET WarehouseTask?$filter=WarehouseTaskStatus eq ''", T('每 2 s 一次', 'every 2 s'), False),
        ('msg', 'sap', 'br', T('200  value: [1000000001]，仓库单 2000000001', '200  value: [1000000001], order 2000000001'), None, True),
        ('phase', '③', T('仓库下单', 'WMS order'), '0.63 s'),
        ('msg', 'br', 'com', 'C4  PATCH transport-units?bk=…4711&newLocation=IPNT', T('托盘放到源库位 FGIN/IPNT/0001/0000/0000', 'pallet to source location'), False),
        ('msg', 'br', 'tms', 'T2  POST transport-orders', '{barcode, targetLocation: FGIN/PICK/WORK/0001/0000}', False),
        ('msg', 'tms', 'br', '201  Location: …/transport-orders/3fc573cf-…', None, True),
        ('msg', 'br', 'tms', 'T3  GET  +  T4  POST …?state=STARTED', None, False),
        ('phase', '④', T('车队下单', 'fleet order'), '0.72 s'),
        ('msg', 'br', 'tcs', 'F4  POST transportOrders/SAP-1000000001', T('目的地：Inbound 装货 → Pick-01 卸货，指定 Vehicle-01', 'Inbound load → Pick-01 unload, Vehicle-01'), False),
        ('msg', 'tcs', 'br', '200  DISPATCHABLE', None, True),
        ('msg', 'tcs', 'car', T('派车，逐段下发', 'dispatch'), 'Park → Inbound → Pick', False),
        ('phase', '⑤', T('执行监控', 'monitor'), '0.7–16.9 s'),
        ('loop_start', T('loop  [每 2 s，直到车队订单 FINISHED]', 'loop  [every 2 s until FINISHED]')),
        ('msg', 'car', 'tcs', T('回报位置与动作完成', 'position / operation reports'), None, True),
        ('msg', 'br', 'sap', 'S3  GET WarehouseTask(…)', T('看 SAP 是否已取消', 'cancelled in SAP?'), False),
        ('msg', 'sap', 'br', "200  WarehouseTaskStatus = ''", None, True),
        ('msg', 'br', 'tcs', 'F5  GET transportOrders/SAP-1000000001', None, False),
        ('msg', 'tcs', 'br', '200  BEING_PROCESSED  …  FINISHED', None, True),
        ('opt_start', T("opt  [WarehouseTaskStatus = 'A'，SAP 已取消]", "opt  [WarehouseTaskStatus = 'A']")),
        ('msg', 'br', 'tcs', 'F6  POST …/withdrawal?immediate=false', None, False, GREY),
        ('msg', 'br', 'tms', 'T4  POST …?state=CANCELED', None, False, GREY),
        ('opt_end',),
        ('loop_end',),
        ('phase', '⑥', T('回写确认', 'confirm'), '16.9 s'),
        ('msg', 'br', 'tms', 'T3  GET  +  T4  POST …?state=FINISHED', None, False),
        ('msg', 'br', 'com', 'C4  PATCH …&newLocation=PICK', T('托盘到目标库位', 'pallet to target'), False),
        ('msg', 'br', 'sap', 'S3  GET WarehouseTask(…)', None, False),
        ('msg', 'sap', 'br', '200  ETag: W/"2026-11-07T00:00:00.000Z"', None, True),
        ('msg', 'br', 'sap', 'S4  HEAD /   X-CSRF-Token: Fetch', None, False),
        ('msg', 'sap', 'br', '200  x-csrf-token: <token>', None, True),
        ('msg', 'br', 'sap', 'S5  POST …/SAP__self.ConfirmWarehouseTaskExact',
         'If-Match · X-CSRF-Token · {"DirectWhseTaskConfIsAllowed": true}', False),
        ('msg', 'sap', 'br', "200  WarehouseTaskStatus = 'C'", T("仓库单 2000000001 自动变为 'C'", "order 2000000001 auto-completes to 'C'"), True),
    ]

    # 先算总高度
    def height_of(step):
        kind = step[0]
        if kind == 'msg':
            return 6.6 if step[4] else 4.6
        return {'phase': 1.6, 'ref': 8.0, 'loop_start': 5.0, 'loop_end': 2.2, 'opt_start': 5.0, 'opt_end': 1.6}[kind]

    head = 18
    H = head + 4 + sum(height_of(s) for s in steps) + 10
    fig, ax = canvas(W, H)

    for key, (x, color, name, port) in lanes.items():
        box(ax, x - 10.5, 3, 21, 11, fc=tint(color, 0.85), ec=color, lw=0.8)
        text(ax, x, 6.6, name, size=6.6, weight='bold', ha='center')
        text(ax, x, 10.4, port, size=5.6, ha='center', color=GREY)
        ax.plot([x, x], [14, H - 8], color=LINE, lw=0.5, ls=(0, (2, 2)), zorder=0)

    y = head + 2
    phase_start = None
    phase_info = None
    bands = []
    frames = []
    for step in steps:
        kind = step[0]
        if kind == 'phase':
            if phase_info:
                bands.append((phase_start, y, phase_info))
            phase_start, phase_info = y, step[1:]
            y += height_of(step)
        elif kind == 'ref':
            box(ax, 17, y, 160, 6, fc='white', ec=GREY, lw=0.5, r=0.4, z=4)
            text(ax, 19, y + 3, step[1], size=5.8, color=INK, z=6)
            y += height_of(step)
        elif kind in ('loop_start', 'opt_start'):
            frames.append((kind, y, step[1]))
            y += height_of(step)
        elif kind in ('loop_end', 'opt_end'):
            start_kind, y0, label = frames.pop()
            inset = 0 if start_kind == 'loop_start' else 4
            x0, x1 = 17 + inset + (55 if start_kind == 'opt_start' else 0), 178 - inset
            yb = y + (0.6 if start_kind == 'opt_start' else 0)
            ax.add_patch(Rectangle((x0, y0 + 1), x1 - x0, yb - y0 - 1, fc='none', ec=INK if start_kind == 'loop_start' else GREY,
                                   lw=0.55, zorder=4))
            w = len(label) * 1.05 + 4
            ax.add_patch(Polygon([(x0, y0 + 1), (x0 + w, y0 + 1), (x0 + w, y0 + 3.6), (x0 + w - 1.4, y0 + 5), (x0, y0 + 5)],
                                 closed=True, fc='white', ec=INK if start_kind == 'loop_start' else GREY, lw=0.55, zorder=5))
            text(ax, x0 + 1.2, y0 + 3, label, size=5.6, weight='bold', z=6,
                 color=INK if start_kind == 'loop_start' else GREY)
            y += height_of(step)
        else:
            src, dst, label, detail, reply = step[1:6]
            color = step[6] if len(step) > 6 else INK
            yy = y + 3.2
            x1, x2 = X[src], X[dst]
            arrow(ax, x1, yy, x2, yy, color=GREY if reply else color, dashed=reply)
            other = X[dst] if src == 'br' else X[src]
            if other > X['br']:
                anchor, ha = X['br'] + 1.5, 'left'
            else:
                anchor, ha = X['br'] - 1.5, 'right'
            if src == 'car' or dst == 'car':
                anchor, ha = (min(x1, x2) + max(x1, x2)) / 2, 'center'
            text(ax, anchor, yy - 1.5, label, size=5.9, ha=ha, color=GREY if reply and color == INK else color,
                 mono=True, bg='white')
            if detail:
                text(ax, anchor, yy + 1.9, detail, size=5.3, ha=ha, color=GREY, bg='white')
            y += height_of(step)
    bands.append((phase_start, y, phase_info))

    for i, (y0, y1, (num, name, when)) in enumerate(bands):
        ax.add_patch(Rectangle((1, y0), 177, y1 - y0, fc='#F4F4F4' if i % 2 else 'white', ec='none', zorder=-1))
        text(ax, 2, y0 + 2.6, f'{num} {name}', size=6, weight='bold')
        text(ax, 2, y0 + 5.6, when, size=5.4, color=GREY)

    text(ax, 2, H - 4.2, T('实线为请求，虚线为响应或回报。时间取自 2026-11-08 19:39 的一次运行，以桥接接手任务为 0 s，'
                          '从接手到 SAP 确认共 16.9 s。编号与图 1 一致。',
                          'Solid: request; dashed: response/report. Times from the run on 2026-11-08 19:39, '
                          '0 s = task taken by the bridge; confirmation after 16.9 s. IDs as in Fig. 1.'),
         size=5.6, color=GREY)
    save(fig, 'fig2_sequence')


# ---------------------------------------------------------------- 图 3

def figure_confirm():
    W, H = 180, 92
    fig, ax = canvas(W, H)
    panel(ax, 1.5, 2, 'a')
    text(ax, 6, 4.6, T('一次确认请求依次经过的校验', 'Checks applied to one confirm request'), size=7, weight='bold')

    box(ax, 18, 9, 62, 7, fc=tint(BRIDGE, 0.85), ec=BRIDGE, lw=0.7)
    text(ax, 49, 12.5, 'POST …/WarehouseTask(…)/SAP__self.ConfirmWarehouseTaskExact', size=5.5, ha='center', mono=True)

    checks = [
        (T('网关', 'gateway'), T('X-CSRF-Token 正确？', 'valid X-CSRF-Token?'), '403  x-csrf-token: Required'),
        (T('网关', 'gateway'), T('带了 If-Match？', 'If-Match present?'), '428  Precondition Required'),
        ('OData', T('ETag 是最新的？', 'ETag current?'), '412  Precondition Failed'),
        (T('业务', 'business'), T('DirectWhseTaskConfIsAllowed = true\n或仓库单已分配资源？', 'DirectWhseTaskConfIsAllowed = true\nor resource assigned?'),
         '400  /SCWM/ODATA_API/006\nLog on to resource first'),
        (T('业务', 'business'), T("WarehouseTaskStatus = '' ？", "WarehouseTaskStatus = '' ?"), T('400  只有未清任务可确认', '400  task not open')),
    ]
    y = 20
    prev = 16
    layer_spans = {}
    for layer, question, reject in checks:
        tall = '\n' in question
        h = 9 if tall else 6.4
        arrow(ax, 49, prev, 49, y)
        box(ax, 26, y, 46, h, fc='white', ec=INK, lw=0.6, r=0.6)
        text(ax, 49, y + h / 2, question, size=5.8, ha='center')
        arrow(ax, 72, y + h / 2, 82, y + h / 2, color=BAD)
        text(ax, 77, y + h / 2 - 1.4, T('否', 'no'), size=5.4, ha='center', color=BAD)
        box(ax, 82, y + h / 2 - (3.9 if '\n' in reject else 2.6), 34, 7.8 if '\n' in reject else 5.2,
            fc=tint(BAD, 0.9), ec=BAD, lw=0.5, r=0.5)
        text(ax, 84, y + h / 2, reject, size=5.4, mono=True, color=BAD)
        text(ax, 50.5, y - 1.8, T('是', 'yes'), size=5.4, color=GREY) if prev != 16 else None
        span = layer_spans.setdefault(layer, [y, y + h])
        span[1] = y + h
        prev = y + h
        y += h + 4
    arrow(ax, 49, prev, 49, y)
    text(ax, 50.5, y - 1.8, T('是', 'yes'), size=5.4, color=GREY)
    box(ax, 26, y, 46, 6.4, fc=tint(WMS, 0.85), ec=WMS, lw=0.7, r=0.6)
    text(ax, 49, y + 3.2, "200  WarehouseTaskStatus = 'C'", size=5.8, ha='center', mono=True)

    for layer, (y0, y1) in layer_spans.items():
        ax.plot([20, 20], [y0, y1], color=GREY, lw=0.8)
        ax.plot([20, 21.2], [y0, y0], color=GREY, lw=0.8)
        ax.plot([20, 21.2], [y1, y1], color=GREY, lw=0.8)
        text(ax, 18.6, (y0 + y1) / 2, layer, size=5.4, ha='right', color=GREY)
    text(ax, 6, H - 3, T('网关：sap/server.js；OData：CAP 按 @odata.etag 校验；业务：sap/srv/warehouse-order.js',
                         'gateway: sap/server.js; OData: CAP @odata.etag check; business: sap/srv/warehouse-order.js'),
         size=5.4, color=GREY)

    # ---- b 状态机
    panel(ax, 121, 2, 'b')
    text(ax, 126, 4.6, T('状态', 'States'), size=7, weight='bold')

    def state(x, y, label, code, color):
        box(ax, x, y, 18, 8, fc=tint(color, 0.85), ec=color, lw=0.7, r=2.5)
        text(ax, x + 9, y + 2.9, label, size=6, ha='center', weight='bold')
        text(ax, x + 9, y + 5.8, code, size=5.6, ha='center', mono=True)

    text(ax, 126, 12, 'WarehouseTask', size=6.2, weight='bold', mono=True)
    ax.add_patch(plt.Circle((128, 24), 1.1, color=INK, zorder=4))
    arrow(ax, 129.1, 24, 134, 24)
    text(ax, 131.5, 27.4, 'S7', size=5.2, ha='center', color=GREY)
    state(134, 20, T('未清', 'open'), "''", SAP)
    state(160, 14, T('已确认', 'confirmed'), "'C'", WMS)
    state(160, 28, T('已取消', 'cancelled'), "'A'", GREY)
    arrow(ax, 152, 22, 160, 18)
    arrow(ax, 152, 26, 160, 32)
    text(ax, 156, 16.4, 'S5', size=5.6, ha='center', weight='bold', color=SAP)
    text(ax, 156, 33.6, 'S6', size=5.6, ha='center', weight='bold', color=SAP)

    text(ax, 126, 46, 'WarehouseOrder', size=6.2, weight='bold', mono=True)
    state(134, 54, T('未清', 'open'), "''", SAP)
    state(160, 48, T('已完成', 'completed'), "'C'", WMS)
    state(160, 62, T('已取消', 'cancelled'), "'A'", GREY)
    arrow(ax, 152, 56, 160, 52, dashed=True)
    arrow(ax, 152, 60, 160, 66, dashed=True)
    text(ax, 126, 74.5, T("自动：所有任务都已结束且至少一个为 'C' → 'C'；", "automatic: all tasks closed, any 'C' → 'C';"), size=5.4, color=GREY)
    text(ax, 126, 77.8, T("所有任务都是 'A' → 'A'。接口没有确认仓库单的动作。", "all tasks 'A' → 'A'. No API to confirm an order."), size=5.4, color=GREY)
    text(ax, 126, 82.4, T('实线：接口调用触发；虚线：随任务自动变化', 'solid: API call; dashed: automatic'), size=5.4, color=GREY)
    save(fig, 'fig3_confirm')


def main():
    global LANG
    langs = sys.argv[1:] or ['zh', 'en']
    for lang in langs:
        LANG = lang
        figure_interfaces()
        figure_sequence()
        figure_confirm()
        print(f'{lang}: {OUT}')


if __name__ == '__main__':
    main()
