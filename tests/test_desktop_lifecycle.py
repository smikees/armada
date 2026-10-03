"""Focused checks for provider onboarding, native support, and app-owned jobs."""
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from armada import app, codex_usage, schedsvc
from armada.webui.provider_settings import connections


class DesktopLifecycleTests(unittest.TestCase):
    def test_alexander_prefers_right_and_falls_back_to_left(self):
        self.assertEqual(app._alexander_bounds((100, 50, 900, 900), (0, 0, 1920, 1040))["x"], 1010)
        result = app._alexander_bounds((900, 500, 1000, 700), (0, 0, 1920, 1040))
        self.assertEqual((result["x"], result["y"]), (370, 320))

    def test_alexander_supports_negative_monitor_origins_and_small_working_areas(self):
        result = app._alexander_bounds((-1800, 80, 1100, 800), (-1920, 0, 1920, 1040))
        self.assertEqual(result["x"], -690)
        result = app._alexander_bounds((20, 20, 400, 500), (0, 0, 480, 600))
        self.assertEqual(result, dict(x=0, y=0, width=480, height=600))

    def test_wizard_explains_paid_or_api_access_and_has_optional_plan_labels(self):
        html = connections(setup=True)
        self.assertIn("ChatGPT Plus or Pro", html)
        self.assertIn("https://learn.chatgpt.com/docs/pricing", html)
        self.assertIn("Claude Pro or Max", html)
        self.assertIn("free-tier account", html)
        self.assertIn('id="provider-claude-plan"', html)
        self.assertIn('id="provider-codex-plan"', html)
        self.assertIn("Subscription type", html)

    def test_codex_does_not_invent_session_limit(self):
        data = codex_usage._normalize({"rateLimitsByLimitId": {"codex": {
            "planType": "plus", "primary": {"usedPercent": 77, "windowDurationMins": 10080},
            "secondary": None}}})
        self.assertEqual(data["plan"], "plus")
        self.assertEqual([w["label"] for w in data["groups"][0]["windows"]], ["Weekly"])

    def test_scheduler_spawn_is_bound_to_gui_pid(self):
        proc = Mock(pid=321)
        with patch.object(schedsvc, "_last_spawn", 0.0), \
             patch.object(schedsvc, "_stop_marker") as marker, \
             patch.object(schedsvc.subprocess, "Popen", return_value=proc) as popen:
            schedsvc.start()
        marker.return_value.unlink.assert_called_once_with(missing_ok=True)
        command = popen.call_args.args[0]
        self.assertEqual(command[-2:], ["--app-owner", str(os.getpid())])

    def test_alexander_reuses_one_native_window(self):
        events = MagicMock()
        window = Mock(events=events)
        webview = Mock(create_window=Mock(return_value=window))
        with patch.object(app, "_main_window", Mock()), \
             patch.object(app, "_alex_window", None), \
             patch.object(app, "_app_url", "http://127.0.0.1:8756/"), \
             patch.dict("sys.modules", {"webview": webview}), \
             patch.object(app.threading, "Thread"):
            self.assertTrue(app.open_alexander())
            self.assertTrue(app.open_alexander())
        self.assertEqual(webview.create_window.call_count, 1)
        window.show.assert_called_once()
        options = webview.create_window.call_args.kwargs
        self.assertTrue(options["frameless"])
        self.assertTrue(options["transparent"])
        self.assertFalse(options["easy_drag"])  # selecting chat text must not drag the window
        options["js_api"].close_window()
        window.destroy.assert_called_once()

    def test_companion_close_is_bound_to_its_window_even_after_replacement(self):
        original, replacement, main = Mock(), Mock(), Mock()
        api = app._AlexanderCompanionAPI()
        api._window = original
        with patch.object(app, "_alex_window", replacement), patch.object(app, "_main_window", main):
            api.close_window()
            app._clear_alexander(original)
            self.assertIs(app._alex_window, replacement)
        original.destroy.assert_called_once()
        replacement.destroy.assert_not_called()
        main.destroy.assert_not_called()

    def test_companion_region_tracks_actual_client_size_and_dpi(self):
        path, old = Mock(), Mock()
        drawing = Mock(Region=Mock(return_value="new region"))
        geometry = Mock(GraphicsPath=Mock(return_value=path))
        native = Mock(_scale=1.5, InvokeRequired=False, Region=old,
                      ClientSize=Mock(Width=780, Height=1080))
        with patch.object(app.sys, "platform", "win32"), patch.dict("sys.modules", {
                "System": Mock(Action=lambda callback: callback), "System.Drawing": drawing,
                "System.Drawing.Drawing2D": geometry}):
            app._shape_alexander(Mock(native=native))
        geometry.GraphicsPath.assert_called_once_with(geometry.FillMode.Winding)
        path.AddEllipse.assert_called_once_with(12, 12, 144, 144)
        # Bottom-right follows the live 520 x 720 logical viewport, including at 150% DPI.
        self.assertEqual(path.AddArc.call_args_list[2].args, (726, 1026, 42, 42, 0, 90))
        self.assertEqual(native.Region, "new region")
        path.Dispose.assert_called_once()
        old.Dispose.assert_called_once()

    def test_alexander_cards_open_local_pages_in_main_window(self):
        main = Mock()
        with patch.object(app, "_main_window", main), \
             patch.object(app, "_app_url", "http://127.0.0.1:8756/"):
            self.assertFalse(app.show_main(href="https://elsewhere.example"))
            self.assertTrue(app.show_main(href="/settings?tab=app"))
        main.load_url.assert_called_once_with("http://127.0.0.1:8756/settings?tab=app")


if __name__ == "__main__":
    unittest.main()
