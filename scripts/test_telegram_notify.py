import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock
import urllib.request

import telegram_notify as notify


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.env = {'JUNIT_DIRECTORY': str(self.path), 'TEST_OUTCOME': 'success',
                    'JOB_STATUS': 'success', 'GITHUB_REPOSITORY': 'owner/project',
                    'GITHUB_REF_NAME': 'master', 'GITHUB_SHA': '1234567890abcdef',
                    'GITHUB_RUN_ID': '42'}

    def write(self, text, name='TEST-first.xml'):
        (self.path / name).write_text(text, encoding='utf-8')

    def test_nested_suites_and_multiple_files(self):
        self.write('<testsuites tests="4"><testsuite tests="4"><testsuite><testcase/>'
                   '<testcase><failure/></testcase><testcase><error/></testcase>'
                   '<testcase><skipped/></testcase></testsuite></testsuite></testsuites>')
        self.write('<testsuite><testcase/></testsuite>', 'TEST-second.xml')
        self.assertEqual(notify.read_results(self.path),
                         ({'passed': 2, 'failed': 1, 'errors': 1, 'skipped': 1}, None))
        self.assertIn('Tests failed', notify.build_message(self.env))

    def test_success_message(self):
        self.write('<testsuite><testcase/></testsuite>')
        message = notify.build_message(self.env)
        for value in ('Tests passed', 'passed=1', 'owner/project', 'GitHub Actions',
                      'master', '1234567890ab', 'https://github.com/owner/project/actions/runs/42'):
            self.assertIn(value, message)

    def test_failed_execution_with_passing_xml(self):
        self.write('<testsuite><testcase/></testsuite>')
        self.env['TEST_OUTCOME'] = 'failure'
        self.assertIn('Tests failed', notify.build_message(self.env))

    def test_all_skipped(self):
        self.write('<testsuite><testcase><skipped/></testcase></testsuite>')
        self.assertIn('All tests skipped', notify.build_message(self.env))

    def test_successful_delivery(self):
        self.env.update(TELEGRAM_BOT_TOKEN='fake-token', TELEGRAM_CHAT_ID='fake-chat')
        sender = Mock(return_value=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(notify.main(self.env, sender), 0)
        self.assertIn('notification sent', output.getvalue())
        sender.assert_called_once()

    def test_missing_malformed_and_empty_results(self):
        self.assertIn('results unavailable', notify.build_message(self.env))
        for xml in ('<broken', '<wrong/>'):
            self.write(xml)
            self.assertIn('invalid or unreadable', notify.build_message(self.env))
        self.write('<testsuite/>')
        self.assertIn('No tests reported', notify.build_message(self.env))

    def test_build_failure_ignores_old_results(self):
        self.write('<testsuite><testcase/></testsuite>')
        self.env.update(TEST_OUTCOME='skipped', JOB_STATUS='failure')
        self.assertIn('Tests did not run', notify.build_message(self.env))
        self.assertNotIn('passed=1', notify.build_message(self.env))

    def test_missing_secrets_and_cancelled_run(self):
        sender = Mock()
        for secrets in ({}, {'TELEGRAM_BOT_TOKEN': 'fake-token'},
                        {'TELEGRAM_CHAT_ID': 'fake-chat'},
                        {'JOB_STATUS': 'cancelled', 'TELEGRAM_BOT_TOKEN': 'fake-token',
                         'TELEGRAM_CHAT_ID': 'fake-chat'}):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(notify.main(self.env | secrets, sender), 0)
        sender.assert_not_called()

    def test_notification_failure_preserves_job_result_without_leaking_secrets(self):
        self.env.update(TELEGRAM_BOT_TOKEN='fake-token', TELEGRAM_CHAT_ID='fake-chat')
        for status in ('success', 'failure'):
            self.env['JOB_STATUS'] = status
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(notify.main(self.env, Mock(return_value=False)), 0)
            self.assertEqual(self.env['JOB_STATUS'], status)
            self.assertIn('::warning::', output.getvalue())
            self.assertNotIn('fake-token', output.getvalue())
            self.assertNotIn('fake-chat', output.getvalue())


class HttpTests(unittest.TestCase):
    def test_real_socket_timeout(self):
        release = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                release.wait(2)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def opener(request, timeout):
                return urllib.request.urlopen(urllib.request.Request(
                    f'http://127.0.0.1:{server.server_port}/sendMessage',
                    data=request.data, method='POST'), timeout=timeout)

            self.assertFalse(notify.send_message('fake-token', 'fake-chat', 'message',
                                                timeout=0.05, opener=opener))
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join()

    def test_http_responses_and_timeout(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(self.server.response_status)
                self.end_headers()
                self.wfile.write(self.server.response_body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def opener(request, timeout):
                self.assertEqual(request.full_url, 'https://api.telegram.org/botfake-token/sendMessage')
                local_request = urllib.request.Request(
                    f'http://127.0.0.1:{server.server_port}/sendMessage', data=request.data,
                    headers=dict(request.header_items()), method=request.method)
                return urllib.request.urlopen(local_request, timeout=timeout)

            for status, body, expected in ((200, b'{"ok":true}', True),
                                          (200, b'{"ok":false}', False),
                                          (500, b'{"ok":true}', False),
                                          (200, b'broken', False),
                                          (200, b'[]', False)):
                server.response_status, server.response_body = status, body
                self.assertEqual(notify.send_message('fake-token', 'fake-chat', 'message', opener=opener), expected)
            self.assertEqual(received[0], {'chat_id': 'fake-chat', 'text': 'message'})
            timeout_opener = Mock(side_effect=TimeoutError('fake-token fake-chat'))
            self.assertFalse(notify.send_message('fake-token', 'fake-chat', 'message',
                                                timeout=0.01, opener=timeout_opener))
            self.assertEqual(timeout_opener.call_args.kwargs['timeout'], 0.01)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
