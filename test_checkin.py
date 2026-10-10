import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).with_name("checkin.py")


def response(body, status=200):
    return types.SimpleNamespace(status_code=status, json=lambda: body)


def mismatch(device):
    return response({"code": 4, "reason": "device-mismatch", "loginDevice": device})


class DeviceMatchingTests(unittest.TestCase):
    def setUp(self):
        self.http = types.ModuleType("requests")
        self.http.post = Mock()
        self.http.get = Mock()
        with patch.dict(sys.modules, {"requests": self.http}):
            module = runpy.run_path(str(SCRIPT))
        self.checkin = module["checkin_with_device"]
        self.agents = module["DEVICE_USER_AGENTS"]
        self.headers = {"cookie": "private-test-cookie", "user-agent": self.agents["macOS"]}
        self.payload = {"token": "glados.cloud"}

    def call_checkin(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.checkin("https://glados.cloud/api/user/checkin", self.headers, self.payload)

    def test_matching_session_needs_one_request(self):
        expected = response({"code": 1, "message": "Today's observation logged."})
        self.http.post.return_value = expected
        actual, agent = self.call_checkin()
        self.assertIs(actual, expected)
        self.assertEqual(agent, self.agents["macOS"])
        self.assertEqual(self.http.post.call_count, 1)

    def test_each_supported_device_uses_reported_login_device(self):
        for device in self.agents:
            with self.subTest(device=device):
                self.http.post.reset_mock()
                self.headers["user-agent"] = "initial test device"
                expected = response({"code": 0, "message": "Checkin!"})
                self.http.post.side_effect = [mismatch(device), expected]
                actual, agent = self.call_checkin()
                self.assertIs(actual, expected)
                self.assertEqual(agent, self.agents[device])
                self.assertEqual(self.http.post.call_count, 2)
                self.assertEqual(self.http.post.call_args.kwargs["headers"]["user-agent"], agent)
                self.assertEqual(self.headers["user-agent"], "initial test device")

    def test_unknown_or_missing_device_does_not_guess(self):
        for device in (None, "Unknown", ["Windows"]):
            with self.subTest(device=device):
                self.http.post.reset_mock()
                self.http.post.return_value = mismatch(device)
                self.call_checkin()
                self.assertEqual(self.http.post.call_count, 1)

    def test_other_rejections_are_not_retried(self):
        for body in ({"code": -2, "message": "没有权限"}, {"code": 4}, {"code": 9}):
            with self.subTest(body=body):
                self.http.post.reset_mock()
                self.http.post.return_value = response(body)
                self.call_checkin()
                self.assertEqual(self.http.post.call_count, 1)

    def test_http_failure_is_not_retried(self):
        self.http.post.return_value = response({}, 503)
        self.call_checkin()
        self.assertEqual(self.http.post.call_count, 1)

    def test_repeated_device_mismatch_stops_after_one_retry(self):
        expected = mismatch("Android")
        self.http.post.side_effect = [mismatch("Windows"), expected]
        actual, agent = self.call_checkin()
        self.assertIs(actual, expected)
        self.assertEqual(agent, self.agents["Windows"])
        self.assertEqual(self.http.post.call_count, 2)

    def test_already_matching_agent_is_not_retried(self):
        self.http.post.return_value = mismatch("macOS")
        self.call_checkin()
        self.assertEqual(self.http.post.call_count, 1)

    def test_mixed_accounts_keep_independent_devices_for_all_requests(self):
        calls = []
        expected_devices = {"windows-cookie": "Windows", "mac-cookie": "macOS"}

        def request(url, headers, **kwargs):
            cookie = headers["cookie"]
            agent = headers["user-agent"]
            endpoint = url.rsplit("/", 1)[-1]
            calls.append((cookie, endpoint, agent))
            expected_agent = self.agents[expected_devices[cookie]]
            if endpoint == "checkin" and agent != expected_agent:
                return mismatch(expected_devices[cookie])
            self.assertEqual(agent, expected_agent)
            if endpoint == "checkin":
                return response({"code": 1, "message": "Today's observation logged. Return tomorrow for more points."})
            if endpoint == "status":
                return response({"code": 0, "data": {"leftDays": "100", "email": "test@example.invalid"}})
            if endpoint == "points":
                return response({"points": "500" if cookie == "windows-cookie" else "10"})
            if endpoint == "exchange":
                return response({"code": 0})
            self.fail("Unexpected endpoint")

        self.http.post.side_effect = request
        self.http.get.side_effect = request
        output = io.StringIO()
        env = {"COOKIES": " windows-cookie & mac-cookie ", "PUSHPLUS": "", "USER_AGENT": ""}
        with patch.dict(sys.modules, {"requests": self.http}), patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(SCRIPT), run_name="__main__")
        self.assertEqual(exit_result.exception.code, 0)
        checks = [(cookie, agent) for cookie, endpoint, agent in calls if endpoint == "checkin"]
        self.assertEqual(checks, [
            ("windows-cookie", self.agents["macOS"]),
            ("windows-cookie", self.agents["Windows"]),
            ("mac-cookie", self.agents["macOS"]),
        ])
        self.assertIn(("windows-cookie", "exchange", self.agents["Windows"]), calls)
        self.assertEqual(output.getvalue().count("今日已签到"), 2)
        self.assertNotIn("windows-cookie", output.getvalue())
        self.assertNotIn("mac-cookie", output.getvalue())


if __name__ == "__main__":
    unittest.main()
