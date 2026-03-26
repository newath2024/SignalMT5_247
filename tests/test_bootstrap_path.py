import unittest
from unittest.mock import MagicMock, patch

from app.controller import AppController
from app.startup import build_application_controller


class FakeLifecycle:
    def __init__(self):
        self.config = type("Cfg", (), {"app": type("App", (), {"name": "Liquidity Sniper"})()})()
        self.runtime = type(
            "Runtime",
            (),
            {
                "logger": type("Logger", (), {"log_file": "logs/app.log"})(),
                "runtime_state": object(),
                "engine": object(),
            },
        )()

    def current_ob_fvg_mode(self):
        return "medium"

    def set_ob_fvg_mode(self, mode: str, persist: bool = True):
        return True, mode

    def shutdown(self):
        return None


class BootstrapPathTests(unittest.TestCase):
    @patch("app.startup.AppController")
    @patch("app.startup.AppLifecycle")
    @patch("app.startup.build_app_runtime")
    @patch("app.startup.load_app_config")
    def test_build_application_controller_uses_canonical_path(
        self,
        load_app_config_mock,
        build_app_runtime_mock,
        lifecycle_cls_mock,
        controller_cls_mock,
    ):
        config = object()
        runtime = object()
        lifecycle = MagicMock()
        load_app_config_mock.return_value = config
        build_app_runtime_mock.return_value = runtime
        lifecycle_cls_mock.return_value = lifecycle

        build_application_controller()

        load_app_config_mock.assert_called_once_with()
        build_app_runtime_mock.assert_called_once_with(config)
        lifecycle_cls_mock.assert_called_once_with(config=config, runtime=runtime)
        lifecycle.startup.assert_called_once_with()
        controller_cls_mock.assert_called_once_with(lifecycle)

    @patch("app.startup.AppController")
    @patch("app.startup.AppLifecycle")
    @patch("app.startup.build_app_runtime")
    @patch("app.startup.load_app_config")
    def test_build_application_controller_can_skip_lifecycle_startup(
        self,
        load_app_config_mock,
        build_app_runtime_mock,
        lifecycle_cls_mock,
        controller_cls_mock,
    ):
        config = object()
        runtime = object()
        lifecycle = MagicMock()
        load_app_config_mock.return_value = config
        build_app_runtime_mock.return_value = runtime
        lifecycle_cls_mock.return_value = lifecycle

        build_application_controller(start_lifecycle=False)

        load_app_config_mock.assert_called_once_with()
        build_app_runtime_mock.assert_called_once_with(config)
        lifecycle_cls_mock.assert_called_once_with(config=config, runtime=runtime)
        lifecycle.startup.assert_not_called()
        controller_cls_mock.assert_called_once_with(lifecycle)

    def test_app_controller_is_injected_facade(self):
        lifecycle = FakeLifecycle()

        controller = AppController(lifecycle)

        self.assertIs(controller.lifecycle, lifecycle)
        self.assertIs(controller.config, lifecycle.config)
        self.assertIs(controller.logger, lifecycle.runtime.logger)
        self.assertIs(controller.runtime_state, lifecycle.runtime.runtime_state)


if __name__ == "__main__":
    unittest.main()
