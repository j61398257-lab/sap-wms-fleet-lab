import time
import unittest

from chain import lab, web


class ChainTest(unittest.TestCase):
    def setUp(self):
        self.lab = lab.start(ports={name: 0 for name in lab.PORTS}, step_seconds=0.02, poll_seconds=0.02)
        self.addCleanup(self.lab.stop)

    def get(self, system, path):
        body, _ = web.call('GET', self.lab.urls[system] + path)
        return body

    def wait_until_confirmed(self, task_no, timeout=10):
        deadline = time.monotonic() + timeout
        while True:
            task = self.get('sap', f'/tasks/{task_no}')
            if task['status'] == 'CONFIRMED':
                return task
            if time.monotonic() > deadline:
                self.fail(f'任务 {task_no} 在 {timeout} 秒内没有确认，停在 {task["status"]}')
            time.sleep(0.05)

    def test_released_task_is_carried_to_pick_and_confirmed(self):
        task = self.wait_until_confirmed('1000000001')
        wms_order = self.get('wms', f'/transport-orders/{task["externalRef"]}')
        pallet = self.get('wms', '/transport-units/00000000000000004711')
        fleet_order = self.get('fleet', f'/transport-orders/{task["fleetOrder"]}')
        vehicle = next(item for item in self.get('fleet', '/vehicles') if item['name'] == 'Vehicle-01')
        self.assertEqual(
            (wms_order['state'], pallet['location'], fleet_order['state'], vehicle['position']),
            ('FINISHED', 'FGIN/PICK/WORK/0001/0000', 'FINISHED', 'Point-Pick'))


if __name__ == '__main__':
    unittest.main()
