"""
Tests for the performance monitoring implementation.
"""
import pytest
from graphrouter.monitoring import PerformanceMonitor

def test_monitor_initialization():
    """Test monitor initialization."""
    monitor = PerformanceMonitor()
    assert len(monitor.metrics) == 0

def test_record_operation():
    """Test recording operation metrics."""
    monitor = PerformanceMonitor()
    
    # Record some test operations
    monitor.record_operation('query', 0.5)
    monitor.record_operation('query', 1.0)
    monitor.record_operation('create_node', 0.3)
    
    # Verify metrics were recorded
    assert len(monitor.metrics['query']) == 2
    assert len(monitor.metrics['create_node']) == 1

def test_get_average_times():
    """Test calculating average operation times."""
    monitor = PerformanceMonitor()
    
    # Record multiple operations
    monitor.record_operation('query', 1.0)
    monitor.record_operation('query', 2.0)
    monitor.record_operation('query', 3.0)
    monitor.record_operation('create_node', 0.5)
    monitor.record_operation('create_node', 1.5)
    
    averages = monitor.get_average_times()
    assert averages['query'] == 2.0  # (1 + 2 + 3) / 3
    assert averages['create_node'] == 1.0  # (0.5 + 1.5) / 2

def test_reset_metrics():
    """Test resetting metrics."""
    monitor = PerformanceMonitor()
    
    # Record some operations
    monitor.record_operation('query', 1.0)
    monitor.record_operation('create_node', 0.5)
    
    # Verify metrics exist
    assert len(monitor.metrics) > 0
    
    # Reset metrics
    monitor.reset()
    
    # Verify metrics were cleared
    assert len(monitor.metrics) == 0
    assert monitor.get_average_times() == {}

def test_multiple_operation_types():
    """Test handling multiple operation types."""
    monitor = PerformanceMonitor()
    
    operations = {
        'query': [0.5, 1.0, 1.5],
        'create_node': [0.2, 0.3],
        'update_node': [0.4],
        'delete_node': [0.6, 0.8]
    }
    
    # Record operations
    for op_type, times in operations.items():
        for time in times:
            monitor.record_operation(op_type, time)
    
    # Verify all operation types were recorded
    averages = monitor.get_average_times()
    assert len(averages) == len(operations)
    assert abs(averages['query'] - 1.0) < 0.001  # (0.5 + 1.0 + 1.5) / 3
    assert abs(averages['create_node'] - 0.25) < 0.001  # (0.2 + 0.3) / 2
    assert abs(averages['update_node'] - 0.4) < 0.001
    assert abs(averages['delete_node'] - 0.7) < 0.001  # (0.6 + 0.8) / 2
