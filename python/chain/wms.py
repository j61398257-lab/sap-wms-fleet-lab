import threading

from .web import HttpError, find, log

LOCATIONS = ('FGIN/IPNT/0001/0000/0000', 'FGIN/PICK/WORK/0001/0000')
NEXT_STATE = {'CREATED': 'STARTED', 'STARTED': 'FINISHED'}


class Wms:
    def __init__(self):
        self.lock = threading.Lock()
        self.units = {
            '00000000000000004711': {
                'barcode': '00000000000000004711', 'type': 'PALLET',
                'location': 'FGIN/IPNT/0001/0000/0000',
            },
        }
        self.orders = {}

    def routes(self):
        return [
            ('GET', r'/transport-units/([^/]+)', self.get_unit),
            ('GET', r'/transport-orders', self.list_orders),
            ('POST', r'/transport-orders', self.create_order),
            ('GET', r'/transport-orders/([^/]+)', self.get_order),
            ('POST', r'/transport-orders/([^/]+)/state', self.change_state),
        ]

    def get_unit(self, request, barcode):
        with self.lock:
            return dict(find(self.units, barcode, '托盘'))

    def list_orders(self, request):
        with self.lock:
            return [dict(order) for order in self.orders.values()]

    def get_order(self, request, order_id):
        with self.lock:
            return dict(find(self.orders, order_id, '运输单'))

    def create_order(self, request):
        barcode, target = request.body['barcode'], request.body['targetLocation']
        with self.lock:
            unit = find(self.units, barcode, '托盘')
            if target not in LOCATIONS:
                raise HttpError(400, f'没有库位 {target}')
            order_id = f'TO-{len(self.orders) + 1:04d}'
            order = {'id': order_id, 'barcode': barcode, 'sourceLocation': unit['location'],
                     'targetLocation': target, 'state': 'CREATED'}
            self.orders[order_id] = order
            order = dict(order)
        log('WMS', f'运输单 {order_id} 已创建：托盘 {barcode}，{order["sourceLocation"]} -> {target}')
        return 201, order

    def change_state(self, request, order_id):
        state = request.body['state']
        with self.lock:
            order = find(self.orders, order_id, '运输单')
            before = order['state']
            if NEXT_STATE.get(before) != state:
                raise HttpError(409, f'运输单 {order_id} 当前是 {before}，不能改成 {state}')
            order['state'] = state
            if state == 'FINISHED':
                self.units[order['barcode']]['location'] = order['targetLocation']
            order = dict(order)
        arrived = f'，托盘到达 {order["targetLocation"]}' if state == 'FINISHED' else ''
        log('WMS', f'运输单 {order_id}：{before} -> {state}{arrived}')
        return order
