import threading

from .web import HttpError, find, log


class Sap:
    def __init__(self):
        self.lock = threading.Lock()
        self.tasks = {
            '1000000001': {
                'taskNo': '1000000001', 'warehouse': 'E001', 'orderNo': '4500000001',
                'product': 'MAT-100', 'qty': 1, 'uom': 'EA',
                'srcBin': 'IPNT-01', 'dstBin': 'PICK-01', 'status': 'RELEASED',
                'actualQty': None, 'externalRef': None, 'fleetOrder': None, 'version': 1,
            },
        }

    def routes(self):
        return [
            ('GET', r'/tasks', self.list_tasks),
            ('GET', r'/tasks/([^/]+)', self.get_task),
            ('POST', r'/tasks/([^/]+)/handover', self.handover),
            ('POST', r'/tasks/([^/]+)/confirm', self.confirm),
        ]

    def list_tasks(self, request):
        status = request.query.get('status')
        with self.lock:
            return [dict(task) for task in self.tasks.values() if status in (None, task['status'])]

    def get_task(self, request, task_no):
        with self.lock:
            task = dict(find(self.tasks, task_no, '任务'))
        return 200, task, {'ETag': _etag(task)}

    def handover(self, request, task_no):
        return self._act(request, task_no, 'RELEASED', 'IN_PROCESS',
                         externalRef=request.body.get('externalRef'),
                         fleetOrder=request.body.get('fleetOrder'))

    def confirm(self, request, task_no):
        return self._act(request, task_no, 'IN_PROCESS', 'CONFIRMED',
                         actualQty=request.body.get('actualQty'))

    def _act(self, request, task_no, allowed, status, **changes):
        with self.lock:
            task = find(self.tasks, task_no, '任务')
            if request.headers.get('If-Match') != _etag(task):
                raise HttpError(412, f'任务 {task_no} 已经被改过，先重新读取拿到新的 ETag')
            if task['status'] != allowed:
                raise HttpError(409, f'任务 {task_no} 当前是 {task["status"]}，不能做这个动作')
            before = task['status']
            task.update(changes, status=status, version=task['version'] + 1)
            task = dict(task)
        log('SAP', f'任务 {task_no}：{before} -> {status}')
        return 200, task, {'ETag': _etag(task)}


def _etag(task):
    return f'W/"{task["version"]}"'
