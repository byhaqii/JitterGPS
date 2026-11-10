import json
import unittest
from unittest.mock import Mock, patch

from core.cdp_client import CDPClient


class CDPClientTests(unittest.TestCase):
    def setUp(self):
        self.http = patch('core.cdp_client.requests.get').start()
        self.connect = patch('core.cdp_client.connect').start()
        self.addCleanup(patch.stopall)
        self.http.return_value.json.return_value = [
            {'type': 'page', 'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/a'},
            {'type': 'service_worker', 'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/worker/b'}]
        self.socket = self.connect.return_value
        self.client = CDPClient()

    def test_acknowledged_commands_reuse_connection_and_match_ids(self):
        self.socket.recv.side_effect = [json.dumps({'method': 'event'}),
                                        json.dumps({'id': 999, 'result': {}}),
                                        json.dumps({'id': 1, 'result': {}}),
                                        json.dumps({'id': 2, 'result': {}})]
        self.assertEqual(self.client.apply(1, 2), (1, []))
        self.assertEqual(self.client.clear_geolocation_override(), (1, []))
        self.assertEqual(self.connect.call_count, 1)
        messages = [json.loads(call.args[0]) for call in self.socket.send.call_args_list]
        self.assertEqual(messages[0]['params'], {'latitude': 1.0, 'longitude': 2.0, 'accuracy': 10.0})
        self.assertEqual(messages[1]['method'], 'Emulation.clearGeolocationOverride')
        self.assertGreater(messages[1]['id'], messages[0]['id'])
        self.assertIn('timeout', self.socket.recv.call_args.kwargs)
        self.assertIn('timeout', self.http.call_args.kwargs)

    def test_clear_protocol_failure_is_reported_not_counted(self):
        self.socket.recv.return_value = json.dumps({'id': 1, 'error': {'message': 'denied'}})
        count, errors = self.client.clear_geolocation_override()
        self.assertEqual(count, 0)
        self.assertIn('denied', errors[0])

    def test_closed_socket_removed_and_reconnected_on_next_apply(self):
        self.socket.recv.side_effect = TimeoutError('closed')
        count, errors = self.client.apply(1, 2)
        self.assertEqual(count, 0)
        self.assertTrue(errors)
        self.socket.close.assert_called_once()
        self.socket.recv.side_effect = None
        self.socket.recv.return_value = json.dumps({'id': 2, 'result': {}})
        self.assertEqual(self.client.apply(1, 2), (1, []))
        self.assertEqual(self.connect.call_count, 2)

    def test_stale_targets_closed_and_cleanup_errors_reported(self):
        self.socket.recv.return_value = json.dumps({'id': 1, 'result': {}})
        self.client.apply(1, 2)
        self.http.return_value.json.return_value = []
        self.socket.close.side_effect = OSError('cleanup failed')
        count, errors = self.client.clear_geolocation_override()
        self.assertEqual(count, 0)
        self.assertIn('cleanup failed', errors[0])
        self.client.close()

    def test_http_failure_returned_as_error(self):
        self.http.side_effect = OSError('offline')
        count, errors = self.client.apply(1, 2)
        self.assertEqual(count, 0)
        self.assertIn('offline', errors[0])

    def test_invalid_input_rejected_without_network(self):
        for args in [(float('nan'), 2), (91, 2), (1, 181), (1, 2, -1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.client.apply(*args)
        self.http.assert_not_called()
