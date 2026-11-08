"""在一次真实运行中约每 0.2 s 采样两条链路的状态，写入 run_trace.json。

用法：先 docker compose down，再启动本脚本，脚本会自己执行 docker compose up -d，
两条链路的任务都确认后再多记 3 s。时间零点是执行 up 的时刻。
"""
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'run_trace.json'
EWM = 'http://localhost:4004/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001'
TASK = "WarehouseTask(EWMWarehouse='E001',WarehouseTask='1000000001',WarehouseTaskItem='0')"
ORDER = "WarehouseOrder(EWMWarehouse='E001',WarehouseOrder='2000000001')"
PALLET = '00000000000000004711'
TU = 'application/vnd.openwms.transport-unit-v1+json'
opener = build_opener(ProxyHandler({}))


def get(url, accept='application/json'):
    try:
        with opener.open(Request(url, headers={'Accept': accept}), timeout=0.6) as response:
            return json.loads(response.read().decode('utf-8') or 'null'), time.time()
    except Exception:
        return None, time.time()


def urls(pkey):
    items = {
        'full.sap': f'{EWM}/{TASK}',
        'full.order': f'{EWM}/{ORDER}',
        'full.bridge': 'http://localhost:8090/status',
        'full.commonUp': 'http://localhost:8120/actuator/info',
        'full.tmsUp': 'http://localhost:8131/actuator/info',
        'full.tcsUp': 'http://localhost:55200/v1/kernel/version',
        'full.pallet': (f'http://localhost:8120/v1/transport-units?bk={PALLET}', TU),
        'full.fleet': 'http://localhost:55200/v1/transportOrders/SAP-1000000001',
        'full.vehicle': 'http://localhost:55200/v1/vehicles/Vehicle-01',
        'py.sap': 'http://localhost:9004/tasks',
        'py.wms': 'http://localhost:9120/transport-orders',
        'py.pallet': f'http://localhost:9120/transport-units/{PALLET}',
        'py.fleet': 'http://localhost:9200/transport-orders',
        'py.vehicles': 'http://localhost:9200/vehicles',
        'py.vehicle': 'http://localhost:9300/state',
        'py.bridge': 'http://localhost:9090/status',
    }
    if pkey:
        items['full.wms'] = f'http://localhost:8131/v1/transport-orders/{pkey}'
    return items


def fetch(pool, items):
    def one(item):
        key, target = item
        url, accept = target if isinstance(target, tuple) else (target, 'application/json')
        return key, get(url, accept)
    return dict(pool.map(one, items.items()))


def value(raw, key):
    return (raw.get(key) or (None, 0))[0]


def stamp(raw, prefix):
    times = [t for key, (_, t) in raw.items() if key.startswith(prefix)]
    return max(times)


def reduce_full(raw):
    sap, order, wms, pallet, fleet, vehicle = (value(raw, f'full.{k}') or {} for k in
                                               ('sap', 'order', 'wms', 'pallet', 'fleet', 'vehicle'))
    actual = pallet.get('actualLocation')
    return {
        'sapUp': value(raw, 'full.sap') is not None,
        'commonUp': value(raw, 'full.commonUp') is not None,
        'tmsUp': value(raw, 'full.tmsUp') is not None,
        'tcsUp': value(raw, 'full.tcsUp') is not None,
        'sap': sap.get('WarehouseTaskStatus'),
        'order': order.get('WarehouseOrderStatus'),
        'wms': wms.get('state'),
        'pallet': actual.get('locationId') if isinstance(actual, dict) else None,
        'fleet': fleet.get('state'),
        'destinations': [d.get('state') for d in fleet.get('destinations') or []],
        'position': vehicle.get('currentPosition'),
        'vehicle': vehicle.get('state'),
    }


def reduce_python(raw):
    tasks = value(raw, 'py.sap')
    task = next((t for t in tasks if t.get('taskNo') == '1000000001'), {}) if isinstance(tasks, list) else {}
    orders = value(raw, 'py.wms')
    fleet_orders = value(raw, 'py.fleet')
    fleet = next((o for o in fleet_orders if o.get('name') == 'SAP-1000000001'), {}) if isinstance(fleet_orders, list) else {}
    vehicles = value(raw, 'py.vehicles')
    car = next((v for v in vehicles if v.get('name') == 'Vehicle-01'), {}) if isinstance(vehicles, list) else {}
    own = value(raw, 'py.vehicle') or {}
    return {
        'sapUp': tasks is not None,
        'sap': task.get('status'),
        'wms': orders[-1].get('state') if isinstance(orders, list) and orders else None,
        'pallet': (value(raw, 'py.pallet') or {}).get('location'),
        'fleet': fleet.get('state'),
        'destinations': [d.get('state') for d in fleet.get('destinations') or []],
        'position': own.get('position') or car.get('position'),
        'vehicle': car.get('state'),
    }


def main():
    samples = []
    journals = {}
    links = {}
    done_at = None
    with ThreadPoolExecutor(max_workers=20) as pool:
        start = time.time()
        subprocess.Popen(['docker', 'compose', 'up', '-d'], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while time.time() - start < 300:
            began = time.time()
            raw = fetch(pool, urls((links.get('1000000001') or {}).get('wms')))
            full_bridge = value(raw, 'full.bridge')
            if full_bridge:
                links = full_bridge.get('links') or {}
                journals['full'] = full_bridge.get('journal')
            py_bridge = value(raw, 'py.bridge')
            if py_bridge:
                journals['python'] = py_bridge.get('journal')
            sample = {
                'full': {'t': stamp(raw, 'full.') - start, **reduce_full(raw)},
                'python': {'t': stamp(raw, 'py.') - start, **reduce_python(raw)},
            }
            samples.append(sample)
            if done_at is None and sample['full']['sap'] == 'C' and sample['python']['sap'] == 'CONFIRMED':
                done_at = time.time()
            if done_at and time.time() - done_at > 3:
                break
            time.sleep(max(0.0, 0.2 - (time.time() - began)))
    meta = {'startedAt': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start)), 'interval': 0.2}
    OUT.write_text(json.dumps({'meta': meta, 'samples': samples, 'journals': journals}, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print(f'{len(samples)} samples, {samples[-1]["full"]["t"]:.1f} s -> {OUT}')


if __name__ == '__main__':
    main()
