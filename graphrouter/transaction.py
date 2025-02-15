
from typing import Any, Callable, Optional
from enum import Enum
from .errors import TransactionError

class TransactionStatus(Enum):
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

class Transaction:
    def __init__(self):
        self._status = TransactionStatus.ACTIVE
        self._operations: list = []
        self._rollback_operations: list = []
        
    @property
    def status(self) -> TransactionStatus:
        return self._status
        
    def add_operation(self, operation: Callable, rollback: Callable) -> None:
        if self._status != TransactionStatus.ACTIVE:
            raise TransactionError("Cannot add operations to a non-active transaction")
        self._operations.append(operation)
        self._rollback_operations.append(rollback)
        
    def commit(self) -> None:
        if self._status != TransactionStatus.ACTIVE:
            raise TransactionError("Cannot commit a non-active transaction")
            
        try:
            for operation in self._operations:
                operation()
            self._status = TransactionStatus.COMMITTED
        except Exception as e:
            self.rollback()
            raise TransactionError(f"Transaction failed during commit: {str(e)}")
            
    def rollback(self) -> None:
        if self._status != TransactionStatus.ACTIVE:
            raise TransactionError("Cannot rollback a non-active transaction")
            
        try:
            for rollback_op in reversed(self._rollback_operations):
                rollback_op()
            self._status = TransactionStatus.ROLLED_BACK
        except Exception as e:
            self._status = TransactionStatus.FAILED
            raise TransactionError(f"Rollback failed: {str(e)}")
