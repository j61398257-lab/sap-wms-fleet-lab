import threading
from datetime import datetime

from .web import call, log

BINS = {
    'IPNT-01': {'wms': 'FGIN/IPNT/0001/0000/0000', 'fleet': 'Inbound'},
    'PICK-01': {'wms': 'FGIN/PICK/WORK/0001/0000', 'fleet': 'Pick-01'},
}
PALLET = '00000000000000004711'
VEHICLE = 'Vehicle-01'


class Bridge:
    def __init__(self, sap_url, wms_url, fleet_url, poll_seconds=1.0):
        self.sap, self.wms, self.fleet = sap_url, wms_url, fleet_url
        self.poll_seconds = poll_seconds
        self.journal = []
        self.taken = set()
        self.stopped = threading.Event()

    def routes(self):
        return [('GET', r'/status', self.status)]

    def status(self, request):
        return {'journal': self.journal[-50:]}

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.stopped.set()

    def _loop(self):
        self._note('开始轮询 SAP 里已下达的搬运任务')
        while not self.stopped.is_set():
            try:
                released, _ = call('GET', f'{self.sap}/tasks?status=RELEASED')
                for task in released:
                    # 每笔任务只接手一次，失败后留在 RELEASED 等人查看，避免重复下单。
                    if task['taskNo'] not in self.taken:
                        self.taken.add(task['taskNo'])
                        self._carry(task)
            except Exception as error:
                self._note(f'这一轮出错：{error}')
            self.stopped.wait(self.poll_seconds)

    def _carry(self, task):
        task_no = task['taskNo']
        source, target = BINS[task['srcBin']], BINS[task['dstBin']]
        self._note(f'接手 SAP 任务 {task_no}：{task["srcBin"]} -> {task["dstBin"]}')
        wms_order, _ = call('POST', f'{self.wms}/transport-orders',
                            {'barcode': PALLET, 'targetLocation': target['wms']})
        self._wms_state(wms_order['id'], 'STARTED')
        fleet_order = f'SAP-{task_no}'
        call('POST', f'{self.fleet}/transport-orders/{fleet_order}', {
            'intendedVehicle': VEHICLE,
            'destinations': [
                {'locationName': source['fleet'], 'operation': 'Load cargo'},
                {'locationName': target['fleet'], 'operation': 'Unload cargo'},
            ],
        })
        self._sap_action(task_no, 'handover', {'externalRef': wms_order['id'], 'fleetOrder': fleet_order})
        self._note(f'等待车队完成运输订单 {fleet_order}')
        while call('GET', f'{self.fleet}/transport-orders/{fleet_order}')[0]['state'] != 'FINISHED':
            if self.stopped.wait(self.poll_seconds):
                return
        self._wms_state(wms_order['id'], 'FINISHED')
        self._sap_action(task_no, 'confirm', {'actualQty': task['qty']})
        self._note(f'任务 {task_no} 搬运完成，结果已回写 SAP')

    def _wms_state(self, order_id, state):
        call('POST', f'{self.wms}/transport-orders/{order_id}/state', {'state': state})

    def _sap_action(self, task_no, action, body):
        _, headers = call('GET', f'{self.sap}/tasks/{task_no}')
        call('POST', f'{self.sap}/tasks/{task_no}/{action}', body, {'If-Match': headers['ETag']})

    def _note(self, message):
        self.journal.append({'at': datetime.now().isoformat(timespec='milliseconds'), 'message': message})
        del self.journal[:-200]
        log('桥接', message)
