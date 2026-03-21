from core import StructuredLogger, load_app_config
from data import MT5DataGateway
from engine import ScannerEngine
from notifiers import TelegramNotifier
from services import AlertService, ScanService
from storage import SQLiteStore, StateManager
from strategy import StrategyEngine


class AppController:
    def __init__(self):
        self.config = load_app_config()
        self.logger = StructuredLogger()
        self.sqlite = SQLiteStore()
        self.state_manager = StateManager(self.sqlite)
        self.data_gateway = MT5DataGateway(self.logger)
        self.notifier = TelegramNotifier(self.config.telegram, self.logger)
        self.strategy = StrategyEngine(trigger_timeframes=self.config.scanner.ltf_timeframes)
        self.alert_service = AlertService(self.config, self.state_manager, self.notifier, self.logger)
        self.scan_service = ScanService(
            data_gateway=self.data_gateway,
            strategy_engine=self.strategy,
            state_manager=self.state_manager,
            alert_service=self.alert_service,
            logger=self.logger,
        )
        self.engine = ScannerEngine(
            config=self.config,
            data_gateway=self.data_gateway,
            notifier=self.notifier,
            state_manager=self.state_manager,
            scan_service=self.scan_service,
            logger=self.logger,
        )
        self.logger.info(
            f"{self.config.app.name} v{self.config.app.version} started",
            phase="system",
            reason=f"strategy v{self.config.app.strategy_version}",
        )

    def start(self, interval_sec: int | None = None):
        if interval_sec is not None:
            self.engine.set_interval(interval_sec)
        return self.engine.start()

    def stop(self):
        return self.engine.stop()

    def run_once(self):
        return self.engine.run_once()

    def set_interval(self, interval_sec: int):
        self.engine.set_interval(interval_sec)

    def snapshot(self):
        return self.engine.snapshot()
