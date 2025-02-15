# graphrouter/monitoring.py

"""
Performance monitoring for GraphRouter.
"""
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from statistics import mean, median, stdev
from datetime import datetime, timedelta

class OperationMetrics:
    """Holds metrics for a specific operation type."""
    def __init__(self):
        self.durations: List[float] = []
        self.timestamps: List[datetime] = []
        self.errors: int = 0
        self.last_error: Optional[str] = None

    def add_duration(self, duration: float):
        """Add a new duration measurement."""
        self.durations.append(duration)
        self.timestamps.append(datetime.now())

    def record_error(self, error_msg: str):
        """Record an operation error."""
        self.errors += 1
        self.last_error = error_msg

    def get_stats(self) -> Dict[str, float]:
        """Calculate statistics for this operation."""
        if not self.durations:
            return {
                'count': 0,
                'avg_duration': 0.0,
                'median_duration': 0.0,
                'min_duration': 0.0,
                'max_duration': 0.0,
                'std_dev': 0.0,
                'error_rate': 0.0
            }

        total_ops = len(self.durations)
        return {
            'count': total_ops,
            'avg_duration': mean(self.durations),
            'median_duration': median(self.durations),
            'min_duration': min(self.durations),
            'max_duration': max(self.durations),
            'std_dev': stdev(self.durations) if len(self.durations) > 1 else 0.0,
            'error_rate': self.errors / total_ops if total_ops > 0 else 0.0
        }

    def cleanup_old_metrics(self, cutoff: datetime):
        """Remove metrics older than the cutoff time."""
        if not self.timestamps:
            return

        valid_indices = [i for i, ts in enumerate(self.timestamps) if ts >= cutoff]
        self.durations = [self.durations[i] for i in valid_indices]
        self.timestamps = [self.timestamps[i] for i in valid_indices]

    def __len__(self):
        """Return the number of durations recorded."""
        return len(self.durations)

class PerformanceMonitor:
    def __init__(self, metrics_ttl: int = 3600):
        """Initialize the performance monitor.

        Args:
            metrics_ttl: Time to live for metrics in seconds (default: 1 hour)
        """
        self.metrics: Dict[str, OperationMetrics] = defaultdict(OperationMetrics)
        self.metrics_ttl = metrics_ttl

    def record_operation(self, operation: str, duration: float, error: Optional[str] = None):
        """Record an operation's execution metrics.

        Args:
            operation: Name of the operation
            duration: Execution time in seconds
            error: Error message if the operation failed
        """
        metrics = self.metrics[operation]
        metrics.add_duration(duration)
        if error:
            metrics.record_error(error)

    def get_average_times(self) -> Dict[str, float]:
        """Get average execution time for each operation type."""
        return {
            op: metrics.get_stats()['avg_duration']
            for op, metrics in self.metrics.items()
        }

    def get_detailed_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get detailed metrics for all operations."""
        self._cleanup_old_metrics()
        return {
            op: metrics.get_stats()
            for op, metrics in self.metrics.items()
        }

    def get_operation_stats(self, operation: str) -> Dict[str, float]:
        """Get detailed statistics for a specific operation."""
        if operation not in self.metrics:
            return {}
        return self.metrics[operation].get_stats()

    def _cleanup_old_metrics(self):
        """Remove metrics older than TTL."""
        cutoff = datetime.now() - timedelta(seconds=self.metrics_ttl)
        for metrics in self.metrics.values():
            metrics.cleanup_old_metrics(cutoff)

    def reset(self):
        """Clear all metrics."""
        self.metrics.clear()
