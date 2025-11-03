"""
Logging and Monitoring System

Provides comprehensive logging, monitoring, and metrics collection for the AI Agent System.
"""

import asyncio
import logging
import logging.handlers
import json
import time
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path
import traceback
import weakref


class LogLevel(Enum):
    """Log levels."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(Enum):
    """Types of metrics."""
    
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(Enum):
    """Alert severity levels."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """A log entry."""
    
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    extra_data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['level'] = self.level.value
        return data
    
    @classmethod
    def from_log_record(cls, record: logging.LogRecord) -> 'LogEntry':
        """Create from logging record."""
        return cls(
            timestamp=datetime.fromtimestamp(record.created),
            level=LogLevel(record.levelname),
            logger_name=record.name,
            message=record.getMessage(),
            module=record.module,
            function=record.funcName,
            line_number=record.lineno,
            thread_id=record.thread,
            process_id=record.process,
            extra_data=getattr(record, 'extra_data', {}),
            stack_trace=record.exc_info and traceback.format_exception(*record.exc_info)
        )


@dataclass
class Metric:
    """A metric data point."""
    
    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['metric_type'] = self.metric_type.value
        return data


@dataclass
class Alert:
    """An alert."""
    
    id: str
    name: str
    message: str
    severity: AlertSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['severity'] = self.severity.value
        data['resolved_at'] = self.resolved_at.isoformat() if self.resolved_at else None
        return data


class CustomFormatter(logging.Formatter):
    """Custom log formatter with JSON support."""
    
    def __init__(self, format_type: str = "console"):
        self.format_type = format_type
        super().__init__()
    
    def format(self, record):
        log_entry = LogEntry.from_log_record(record)
        
        if self.format_type == "json":
            return json.dumps(log_entry.to_dict())
        else:
            # Console format
            timestamp = log_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            extra_info = ""
            if log_entry.extra_data:
                extra_info = f" | {json.dumps(log_entry.extra_data)}"
            
            return f"[{timestamp}] {record.levelname} | {record.name} | {record.funcName}:{record.lineno} | {record.getMessage()}{extra_info}"


class MetricsCollector:
    """Collects and manages metrics."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self._metrics: Dict[str, List[Metric]] = defaultdict(list)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Callbacks for metric updates
        self._callbacks: List[Callable] = []
    
    def increment(self, name: str, value: float = 1, tags: Dict[str, str] = None) -> None:
        """Increment a counter metric."""
        with self._lock:
            self._counters[name] += value
            self._metrics[name].append(Metric(
                name=name,
                value=self._counters[name],
                metric_type=MetricType.COUNTER,
                tags=tags or {}
            ))
            self._notify_callbacks(name, MetricType.COUNTER)
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Set a gauge metric."""
        with self._lock:
            self._gauges[name] = value
            self._metrics[name].append(Metric(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                tags=tags or {}
            ))
            self._notify_callbacks(name, MetricType.GAUGE)
    
    def histogram(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record a histogram metric."""
        with self._lock:
            self._histograms[name].append(value)
            
            # Keep only recent values
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]
            
            self._metrics[name].append(Metric(
                name=name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                tags=tags or {}
            ))
            self._notify_callbacks(name, MetricType.HISTOGRAM)
    
    def timer(self, name: str, duration: float, tags: Dict[str, str] = None) -> None:
        """Record a timer metric."""
        with self._lock:
            self._timers[name].append(duration)
            
            # Keep only recent values
            if len(self._timers[name]) > 1000:
                self._timers[name] = self._timers[name][-1000:]
            
            self._metrics[name].append(Metric(
                name=name,
                value=duration,
                metric_type=MetricType.TIMER,
                tags=tags or {}
            ))
            self._notify_callbacks(name, MetricType.TIMER)
    
    def get_counter(self, name: str) -> float:
        """Get current counter value."""
        with self._lock:
            return self._counters.get(name, 0.0)
    
    def get_gauge(self, name: str) -> float:
        """Get current gauge value."""
        with self._lock:
            return self._gauges.get(name, 0.0)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics."""
        with self._lock:
            values = self._histograms.get(name, [])
            if not values:
                return {}
            
            sorted_values = sorted(values)
            return {
                'count': len(values),
                'min': sorted_values[0],
                'max': sorted_values[-1],
                'mean': sum(values) / len(values),
                'median': sorted_values[len(values) // 2],
                'p95': sorted_values[int(len(sorted_values) * 0.95)],
                'p99': sorted_values[int(len(sorted_values) * 0.99)]
            }
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get timer statistics."""
        return self.get_histogram_stats(name)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        with self._lock:
            summary = {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms
                },
                'timers': {
                    name: self.get_timer_stats(name)
                    for name in self._timers
                }
            }
            return summary
    
    def register_callback(self, callback: Callable) -> None:
        """Register a callback for metric updates."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, metric_name: str, metric_type: MetricType) -> None:
        """Notify callbacks of metric updates."""
        for callback in self._callbacks:
            try:
                callback(metric_name, metric_type)
            except Exception as e:
                # Log but don't break the callback chain
                logging.getLogger("metrics").error(f"Error in metric callback: {e}")


class SystemMonitor:
    """Monitors system resources."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._interval = 10  # seconds
    
    async def start(self, interval: int = 10) -> None:
        """Start system monitoring."""
        if self._running:
            return
        
        self._interval = interval
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """Stop system monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Collect system metrics
                await self._collect_system_metrics()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.getLogger("system_monitor").error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self._interval)
    
    async def _collect_system_metrics(self) -> None:
        """Collect system resource metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            self.metrics_collector.gauge("system.cpu.usage", cpu_percent)
            self.metrics_collector.gauge("system.cpu.count", cpu_count)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            self.metrics_collector.gauge("system.memory.used_percent", memory.percent)
            self.metrics_collector.gauge("system.memory.available", memory.available)
            self.metrics_collector.gauge("system.memory.total", memory.total)
            self.metrics_collector.gauge("system.swap.used_percent", swap.percent)
            self.metrics_collector.gauge("system.swap.total", swap.total)
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            self.metrics_collector.gauge("system.disk.used_percent", 
                                       (disk_usage.used / disk_usage.total) * 100)
            self.metrics_collector.gauge("system.disk.free", disk_usage.free)
            self.metrics_collector.gauge("system.disk.total", disk_usage.total)
            
            # Network metrics
            net_io = psutil.net_io_counters()
            if net_io:
                self.metrics_collector.gauge("system.network.bytes_sent", net_io.bytes_sent)
                self.metrics_collector.gauge("system.network.bytes_recv", net_io.bytes_recv)
                self.metrics_collector.gauge("system.network.packets_sent", net_io.packets_sent)
                self.metrics_collector.gauge("system.network.packets_recv", net_io.packets_recv)
            
            # Process metrics
            process = psutil.Process()
            self.metrics_collector.gauge("system.process.memory_info.rss", process.memory_info().rss)
            self.metrics_collector.gauge("system.process.cpu_percent", process.cpu_percent())
            
            # Thread count
            self.metrics_collector.gauge("system.process.num_threads", process.num_threads())
            
        except Exception as e:
            logging.getLogger("system_monitor").error(f"Error collecting system metrics: {e}")


class AlertManager:
    """Manages alerts."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._alerts: Dict[str, Alert] = {}
        self._rules: List[Callable] = []
        self._lock = threading.RLock()
        
        # Register metric callback
        self.metrics_collector.register_callback(self._check_alert_rules)
    
    def create_alert(
        self,
        name: str,
        message: str,
        severity: AlertSeverity,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new alert."""
        alert_id = f"{name}_{int(time.time())}"
        
        with self._lock:
            alert = Alert(
                id=alert_id,
                name=name,
                message=message,
                severity=severity,
                metadata=metadata or {}
            )
            self._alerts[alert_id] = alert
        
        # Log the alert
        logging.getLogger("alerts").warning(f"Alert created: {name} - {message}")
        
        return alert_id
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        with self._lock:
            if alert_id in self._alerts:
                alert = self._alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now()
                
                # Log the resolution
                logging.getLogger("alerts").info(f"Alert resolved: {alert.name}")
                return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        with self._lock:
            return [alert for alert in self._alerts.values() if not alert.resolved]
    
    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        with self._lock:
            return list(self._alerts.values())
    
    def register_rule(self, rule: Callable[[str, MetricType], List[AlertSeverity]]) -> None:
        """Register an alert rule."""
        self._rules.append(rule)
    
    def _check_alert_rules(self, metric_name: str, metric_type: MetricType) -> None:
        """Check alert rules when metrics are updated."""
        for rule in self._rules:
            try:
                severities = rule(metric_name, metric_type)
                for severity in severities:
                    self.create_alert(
                        name=f"Metric Alert: {metric_name}",
                        message=f"Alert triggered for metric {metric_name} of type {metric_type.value}",
                        severity=severity,
                        metadata={'metric_name': metric_name, 'metric_type': metric_type.value}
                    )
            except Exception as e:
                logging.getLogger("alert_manager").error(f"Error in alert rule: {e}")


class LoggingMonitor:
    """Central logging and monitoring system."""
    
    def __init__(self, log_dir: str = None, config: Dict[str, Any] = None):
        """Initialize logging monitor."""
        self.config = config or {}
        self.log_dir = Path(log_dir) if log_dir else Path.home() / ".webops" / "agents" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Components
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager(self.metrics_collector)
        self.system_monitor = SystemMonitor(self.metrics_collector)
        
        # Log handlers
        self._handlers: Dict[str, logging.Handler] = {}
        
        # Performance tracking
        self._performance_counters: Dict[str, float] = defaultdict(float)
        
        # Health status
        self._health_status = {"status": "healthy", "last_check": datetime.now()}
        
        # Logging
        self.logger = logging.getLogger("logging_monitor")
        
        # Setup default alert rules
        self._setup_default_alert_rules()
    
    def setup_logging(self, level: str = "INFO", format_type: str = "console") -> None:
        """Setup logging configuration."""
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(CustomFormatter(format_type))
        self._handlers['console'] = console_handler
        
        # File handler (rotating)
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "agent.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(CustomFormatter("json"))
        self._handlers['file'] = file_handler
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "errors.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(CustomFormatter("json"))
        self._handlers['error'] = error_handler
        
        # Add handlers to root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        
        # Setup performance logger
        self._setup_performance_logging()
        
        self.logger.info(f"Logging setup complete - level: {level}, format: {format_type}")
    
    def _setup_performance_logging(self) -> None:
        """Setup performance-specific logging."""
        # Create performance logger
        perf_logger = logging.getLogger("performance")
        perf_logger.setLevel(logging.INFO)
        
        # Performance file handler
        perf_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "performance.log",
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(CustomFormatter("json"))
        perf_logger.addHandler(perf_handler)
        self._handlers['performance'] = perf_handler
    
    async def start_monitoring(self, system_monitoring: bool = True, interval: int = 10) -> None:
        """Start monitoring services."""
        if system_monitoring:
            await self.system_monitor.start(interval)
        
        self.logger.info("Monitoring services started")
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring services."""
        await self.system_monitor.stop()
        self.logger.info("Monitoring services stopped")
    
    def track_performance(self, operation_name: str) -> 'PerformanceTracker':
        """Track performance of an operation."""
        return PerformanceTracker(self.metrics_collector, operation_name)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        return {
            'metrics': self.metrics_collector.get_metrics_summary(),
            'active_alerts': [alert.to_dict() for alert in self.alert_manager.get_active_alerts()],
            'health_status': self._health_status
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        self._health_status["last_check"] = datetime.now()
        
        # Check system metrics
        cpu_usage = self.metrics_collector.get_gauge("system.cpu.usage")
        memory_usage = self.metrics_collector.get_gauge("system.memory.used_percent")
        
        if cpu_usage > 90:
            self._health_status["status"] = "critical"
            self._health_status["issues"] = ["High CPU usage"]
        elif memory_usage > 90:
            self._health_status["status"] = "warning"
            self._health_status["issues"] = ["High memory usage"]
        elif self.alert_manager.get_active_alerts():
            self._health_status["status"] = "warning"
            self._health_status["issues"] = ["Active alerts"]
        else:
            self._health_status["status"] = "healthy"
            self._health_status["issues"] = []
        
        return self._health_status
    
    def create_custom_alert(
        self,
        name: str,
        message: str,
        severity: AlertSeverity,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a custom alert."""
        return self.alert_manager.create_alert(name, message, severity, metadata)
    
    def increment_metric(self, name: str, value: float = 1, tags: Dict[str, str] = None) -> None:
        """Increment a metric counter."""
        self.metrics_collector.increment(name, value, tags)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Set a gauge metric."""
        self.metrics_collector.gauge(name, value, tags)
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record a histogram metric."""
        self.metrics_collector.histogram(name, value, tags)
    
    def _setup_default_alert_rules(self) -> None:
        """Setup default alert rules."""
        
        def cpu_alert_rule(metric_name: str, metric_type: MetricType) -> List[AlertSeverity]:
            if metric_name == "system.cpu.usage" and metric_type == MetricType.GAUGE:
                value = self.metrics_collector.get_gauge(metric_name)
                if value > 95:
                    return [AlertSeverity.CRITICAL]
                elif value > 85:
                    return [AlertSeverity.WARNING]
            return []
        
        def memory_alert_rule(metric_name: str, metric_type: MetricType) -> List[AlertSeverity]:
            if metric_name == "system.memory.used_percent" and metric_type == MetricType.GAUGE:
                value = self.metrics_collector.get_gauge(metric_name)
                if value > 95:
                    return [AlertSeverity.CRITICAL]
                elif value > 85:
                    return [AlertSeverity.WARNING]
            return []
        
        # Register default rules
        self.alert_manager.register_rule(cpu_alert_rule)
        self.alert_manager.register_rule(memory_alert_rule)


class PerformanceTracker:
    """Tracks performance of operations."""
    
    def __init__(self, metrics_collector: MetricsCollector, operation_name: str):
        self.metrics_collector = metrics_collector
        self.operation_name = operation_name
        self._start_time = None
        self._tags = {}
    
    def __enter__(self):
        """Start tracking."""
        self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop tracking."""
        if self._start_time:
            duration = time.time() - self._start_time
            self.metrics_collector.timer(f"operation.{self.operation_name}", duration, self._tags)
    
    def add_tag(self, key: str, value: str) -> 'PerformanceTracker':
        """Add a tag to this performance tracking."""
        self._tags[key] = value
        return self


# Global logging monitor instance
_logging_monitor: Optional[LoggingMonitor] = None


def get_logging_monitor() -> LoggingMonitor:
    """Get global logging monitor instance."""
    global _logging_monitor
    if _logging_monitor is None:
        _logging_monitor = LoggingMonitor()
    return _logging_monitor


async def setup_monitoring(
    log_level: str = "INFO",
    format_type: str = "console",
    system_monitoring: bool = True
) -> LoggingMonitor:
    """Setup monitoring system."""
    monitor = get_logging_monitor()
    monitor.setup_logging(log_level, format_type)
    await monitor.start_monitoring(system_monitoring)
    return monitor


# Convenience functions
def log_performance(operation_name: str):
    """Decorator for logging performance of functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            monitor = get_logging_monitor()
            with monitor.track_performance(f"{func.__name__}"):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
        return wrapper
    return decorator


def increment_metric(name: str, value: float = 1, tags: Dict[str, str] = None) -> None:
    """Convenience function to increment a metric."""
    get_logging_monitor().increment_metric(name, value, tags)


def set_gauge(name: str, value: float, tags: Dict[str, str] = None) -> None:
    """Convenience function to set a gauge metric."""
    get_logging_monitor().set_gauge(name, value, tags)


if __name__ == "__main__":
    async def main():
        """Example usage of monitoring system."""
        # Setup monitoring
        monitor = await setup_monitoring(
            log_level="INFO",
            format_type="console",
            system_monitoring=True
        )
        
        # Test logging
        logger = logging.getLogger("test")
        logger.info("Test message", extra={"extra_data": {"key": "value"}})
        
        # Test metrics
        increment_metric("test.counter")
        set_gauge("test.gauge", 42.5)
        
        # Test performance tracking
        with monitor.track_performance("test_operation") as tracker:
            tracker.add_tag("component", "test")
            await asyncio.sleep(0.1)  # Simulate work
        
        # Test alerts
        alert_id = monitor.create_custom_alert(
            name="Test Alert",
            message="This is a test alert",
            severity=AlertSeverity.WARNING
        )
        
        # Get health status
        health = monitor.get_health_status()
        print(f"Health Status: {health}")
        
        # Wait a moment then get metrics
        await asyncio.sleep(1)
        metrics = monitor.get_metrics()
        print(f"Metrics: {json.dumps(metrics, indent=2, default=str)}")
        
        # Stop monitoring
        await monitor.stop_monitoring()
    
    asyncio.run(main())