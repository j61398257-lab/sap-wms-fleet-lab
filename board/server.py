import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

# 这些地址都在本机或编排网络里，走系统代理会连不上。
opener = build_opener(ProxyHandler({}))
ROOT = Path(__file__).resolve().parent
PAGE = (ROOT / 'index.html').read_bytes()

SAP = os.environ.get('SAP_URL', 'http://sap:4004')
BRIDGE = os.environ.get('BRIDGE_URL', 'http://bridge:8090')
WMS_COMMON = os.environ.get('WMS_COMMON_URL', 'http://openwms-common:8120')
WMS_TMS = os.environ.get('WMS_TMS_URL', 'http://openwms-tms:8131')
FLEET = os.environ.get('FLEET_URL', 'http://opentcs:55200')
PY_SAP = os.environ.get('PYTHON_SAP_URL', 'http://python-chain:9004')
PY_WMS = os.environ.get('PYTHON_WMS_URL', 'http://python-chain:9120')
PY_FLEET = os.environ.get('PYTHON_FLEET_URL', 'http://python-chain:9200')
PY_VEHICLE = os.environ.get('PYTHON_VEHICLE_URL', 'http://python-chain:9300')
PY_BRIDGE = os.environ.get('PYTHON_BRIDGE_URL', 'http://python-chain:9090')
PALLET = '00000000000000004711'
TASK = '1000000001'


def fetch(url, headers=None):
    request = Request(url, headers={'Accept': 'application/json', **(headers or {})})
    try:
        with opener.open(request, timeout=4) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        with error:
            raise RuntimeError(f'{error.code} {error.read().decode("utf-8", "replace")[:180]}') from None
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        raise RuntimeError(str(error.reason if isinstance(error, URLError) else error)) from None


def call(label, url, headers=None):
    try:
        return fetch(url, headers)
    except RuntimeError as error:
        return {'error': f'{label}：{error}'}


def last_note(journal):
    if not journal:
        return None
    item = journal[-1]
    return item.get('message')


def full_chain():
    tasks = call('SAP', f'{SAP}/odata/v4/task/Tasks')
    bridge = call('桥接', f'{BRIDGE}/status')
    task = None
    if isinstance(tasks, dict):
        task = next((item for item in tasks.get('value', []) if item.get('taskNo') == TASK), None)
    order_id = task.get('externalRef') if task else None
    fleet_name = (task or {}).get('fleetOrder') or f'SAP-{TASK}'
    wms = call('OpenWMS 运输单', f'{WMS_TMS}/v1/transport-orders/{order_id}') if order_id else {'error': 'SAP 还没有仓库单号'}
    pallet = call('托盘', f'{WMS_COMMON}/v1/transport-units?bk={PALLET}',
                  {'Accept': 'application/vnd.openwms.transport-unit-v1+json'})
    fleet = call('openTCS', f'{FLEET}/v1/transportOrders/{fleet_name}')
    vehicle = call('车辆', f'{FLEET}/v1/vehicles/Vehicle-01')
    location = None
    if isinstance(pallet, dict):
        actual = pallet.get('actualLocation') or {}
        location = actual.get('locationId') if isinstance(actual, dict) else None
    destinations = []
    if isinstance(fleet, dict):
        destinations = [
            {'place': item.get('locationName'), 'operation': item.get('operation'), 'state': item.get('state')}
            for item in fleet.get('destinations') or []
        ]
    return {
        'task': None if not task else {
            'taskNo': task.get('taskNo'),
            'status': task.get('status'),
            'product': task.get('product'),
            'qty': task.get('qty'),
            'actualQty': task.get('actualQty'),
            'srcBin': task.get('srcBin'),
            'dstBin': task.get('dstBin'),
            'externalRef': task.get('externalRef'),
            'fleetOrder': task.get('fleetOrder'),
        },
        'otherTasks': [
            {'taskNo': item.get('taskNo'), 'status': item.get('status')}
            for item in (tasks.get('value') or []) if item.get('taskNo') != TASK
        ] if isinstance(tasks, dict) else [],
        'wms': None if not isinstance(wms, dict) or 'error' in wms else {
            'id': wms.get('persistentKey') or order_id,
            'state': wms.get('state'),
            'source': wms.get('sourceLocation'),
            'target': wms.get('targetLocation'),
        },
        'wmsError': wms.get('error') if isinstance(wms, dict) else None,
        'pallet': {'barcode': PALLET, 'location': location} if location else {'error': pallet.get('error') if isinstance(pallet, dict) else '没有托盘位置'},
        'fleet': None if not isinstance(fleet, dict) or 'error' in fleet else {
            'name': fleet.get('name'),
            'state': fleet.get('state'),
            'vehicle': fleet.get('processingVehicle') or fleet.get('intendedVehicle'),
            'destinations': destinations,
        },
        'fleetError': fleet.get('error') if isinstance(fleet, dict) else None,
        'vehicle': None if not isinstance(vehicle, dict) or 'error' in vehicle else {
            'name': vehicle.get('name') or 'Vehicle-01',
            'position': vehicle.get('currentPosition'),
            'state': vehicle.get('state'),
        },
        'vehicleError': vehicle.get('error') if isinstance(vehicle, dict) else None,
        'bridge': last_note(bridge.get('journal')) if isinstance(bridge, dict) and 'journal' in bridge else None,
        'bridgeError': bridge.get('error') if isinstance(bridge, dict) else None,
        'tasksError': tasks.get('error') if isinstance(tasks, dict) else None,
    }


def python_chain():
    tasks = call('Python SAP', f'{PY_SAP}/tasks')
    orders = call('Python WMS', f'{PY_WMS}/transport-orders')
    pallet = call('Python 托盘', f'{PY_WMS}/transport-units/{PALLET}')
    fleet_orders = call('Python 车队', f'{PY_FLEET}/transport-orders')
    vehicles = call('Python 车辆', f'{PY_FLEET}/vehicles')
    own = call('Python 车辆自身', f'{PY_VEHICLE}/state')
    bridge = call('Python 桥接', f'{PY_BRIDGE}/status')
    task = next((item for item in tasks if item.get('taskNo') == TASK), None) if isinstance(tasks, list) else None
    order = orders[-1] if isinstance(orders, list) and orders else None
    fleet = next((item for item in fleet_orders if item.get('name') == f'SAP-{TASK}'), None) if isinstance(fleet_orders, list) else None
    vehicle = next((item for item in vehicles if item.get('name') == 'Vehicle-01'), None) if isinstance(vehicles, list) else None
    position = None
    if isinstance(own, dict) and 'error' not in own:
        position = own.get('position')
    elif isinstance(vehicle, dict):
        position = vehicle.get('position')
    return {
        'task': None if not task else {
            'taskNo': task.get('taskNo'),
            'status': task.get('status'),
            'product': task.get('product'),
            'qty': task.get('qty'),
            'actualQty': task.get('actualQty'),
            'srcBin': task.get('srcBin'),
            'dstBin': task.get('dstBin'),
            'externalRef': task.get('externalRef'),
            'fleetOrder': task.get('fleetOrder'),
        },
        'tasksError': tasks.get('error') if isinstance(tasks, dict) else None,
        'wms': None if not order else {
            'id': order.get('id'),
            'state': order.get('state'),
            'source': order.get('sourceLocation'),
            'target': order.get('targetLocation'),
        },
        'wmsError': orders.get('error') if isinstance(orders, dict) else None,
        'pallet': {'barcode': PALLET, 'location': pallet.get('location')} if isinstance(pallet, dict) and pallet.get('location') else {'error': pallet.get('error') if isinstance(pallet, dict) else '没有托盘位置'},
        'fleet': None if not fleet else {
            'name': fleet.get('name'),
            'state': fleet.get('state'),
            'vehicle': fleet.get('vehicle'),
            'destinations': [
                {'place': item.get('locationName'), 'operation': item.get('operation'), 'state': item.get('state')}
                for item in fleet.get('destinations') or []
            ],
        },
        'fleetError': fleet_orders.get('error') if isinstance(fleet_orders, dict) else None,
        'vehicle': None if not position else {
            'name': 'Vehicle-01',
            'position': position,
            'state': (vehicle or {}).get('state') or ('IDLE' if not (own or {}).get('driveOrder') else 'EXECUTING'),
        },
        'vehicleError': own.get('error') if isinstance(own, dict) and 'error' in own else None,
        'bridge': last_note(bridge.get('journal')) if isinstance(bridge, dict) and 'journal' in bridge else None,
        'bridgeError': bridge.get('error') if isinstance(bridge, dict) else None,
    }


def snapshot():
    with ThreadPoolExecutor(max_workers=2) as pool:
        full, python = pool.map(lambda fn: fn(), (full_chain, python_chain))
    return {
        'at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'full': full,
        'python': python,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?', 1)[0] == '/api/snapshot':
            body = json.dumps(snapshot(), ensure_ascii=False).encode('utf-8')
            content_type = 'application/json; charset=utf-8'
        elif self.path.split('?', 1)[0] in ('/', '/index.html'):
            body, content_type = PAGE, 'text/html; charset=utf-8'
        else:
            body, content_type = '没有这个地址'.encode('utf-8'), 'text/plain; charset=utf-8'
            self.send_response(404)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(os.environ.get('PORT', '8080'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'调度板 http://0.0.0.0:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
