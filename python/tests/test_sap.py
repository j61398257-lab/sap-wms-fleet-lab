import unittest

from chain import sap, web


class SapRulesTest(unittest.TestCase):
    def setUp(self):
        self.server = web.serve(sap.Sap().routes())
        self.addCleanup(self.server.stop)
        self.task_url = self.server.url + '/tasks/1000000001'

    def test_action_with_stale_etag_is_rejected(self):
        with self.assertRaises(web.HttpError) as caught:
            web.call('POST', self.task_url + '/handover',
                     {'externalRef': 'TO-0001', 'fleetOrder': 'SAP-1000000001'},
                     {'If-Match': 'W/"0"'})
        self.assertEqual(caught.exception.status, 412)

    def test_action_not_allowed_in_current_state_is_rejected(self):
        _, headers = web.call('GET', self.task_url)
        with self.assertRaises(web.HttpError) as caught:
            web.call('POST', self.task_url + '/confirm', {'actualQty': 1}, {'If-Match': headers['ETag']})
        self.assertEqual(caught.exception.status, 409)


if __name__ == '__main__':
    unittest.main()
