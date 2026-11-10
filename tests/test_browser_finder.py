import os
import socket
import unittest
from unittest.mock import Mock, patch

from core.browser_finder import get_browser_executable, launch_browser_with_cdp


class BrowserFinderTests(unittest.TestCase):
    def test_mac_user_install_preferred_before_fallback(self):
        with patch('core.browser_finder.sys.platform', 'darwin'), patch(
                'core.browser_finder.Path.is_file', lambda p: str(p).endswith(
                    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge')):
            self.assertIn('Microsoft Edge.app', get_browser_executable('edge'))

    def test_windows_user_install(self):
        with patch('core.browser_finder.sys.platform', 'win32'), patch.dict(
                os.environ, {'LOCALAPPDATA': '/users/me/local'}), patch(
                'core.browser_finder.Path.is_file', lambda p: str(p) ==
                '/users/me/local/BraveSoftware/Brave-Browser/Application/brave.exe'):
            self.assertEqual(get_browser_executable('brave'),
                             '/users/me/local/BraveSoftware/Brave-Browser/Application/brave.exe')

    def test_unknown_preference_rejected(self):
        with self.assertRaises(ValueError):
            get_browser_executable('unknown')

    def test_launch_uses_owned_profile_local_binding_and_polls(self):
        with patch('core.browser_finder.get_browser_executable', return_value='/browser'), patch(
                'core.browser_finder.socket.socket') as sock, patch(
                'core.browser_finder.subprocess.Popen') as popen, patch(
                'core.browser_finder.requests.get') as http, patch(
                'core.browser_finder.Path.mkdir'):
            sock.return_value.__enter__.return_value.connect_ex.return_value = 1
            popen.return_value.poll.return_value = None
            http.return_value.json.return_value = {'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/browser/a'}
            process = launch_browser_with_cdp()
            self.assertIs(process, popen.return_value)
            args = popen.call_args.args[0]
            self.assertIn('--remote-debugging-address=127.0.0.1', args)
            self.assertIn('--remote-debugging-port=9222', args)
            profile = next(a for a in args if a.startswith('--user-data-dir='))
            self.assertIn('JitterGPS', profile)
            self.assertNotIn('Google/Chrome', profile)
            self.assertIn('timeout', http.call_args.kwargs)

    def test_real_free_port_is_not_falsely_reported_occupied(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        with patch('core.browser_finder.get_browser_executable', return_value='/browser'), patch(
                'core.browser_finder.subprocess.Popen') as popen, patch(
                'core.browser_finder.requests.get') as http, patch(
                'core.browser_finder.Path.mkdir'):
            popen.return_value.poll.return_value = None
            http.return_value.json.return_value = {'webSocketDebuggerUrl': 'ws://127.0.0.1/test'}
            self.assertIs(launch_browser_with_cdp(port=port), popen.return_value)

    def test_occupied_port_refused_before_process_launch(self):
        with patch('core.browser_finder.socket.socket') as sock, patch(
                'core.browser_finder.subprocess.Popen') as popen:
            sock.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaises(RuntimeError):
                launch_browser_with_cdp()
            popen.assert_not_called()

    def test_readiness_timeout_terminates_only_new_process(self):
        with patch('core.browser_finder.get_browser_executable', return_value='/browser'), patch(
                'core.browser_finder.socket.socket') as sock, patch(
                'core.browser_finder.subprocess.Popen') as popen, patch(
                'core.browser_finder.requests.get') as http, patch(
                'core.browser_finder.Path.mkdir'), patch(
                'core.browser_finder.time.monotonic', side_effect=[0, 0, 11]), patch(
                'core.browser_finder.time.sleep'):
            sock.return_value.__enter__.return_value.connect_ex.return_value = 1
            popen.return_value.poll.return_value = None
            http.side_effect = OSError('not ready')
            with self.assertRaises(TimeoutError):
                launch_browser_with_cdp()
            popen.return_value.terminate.assert_called_once()
