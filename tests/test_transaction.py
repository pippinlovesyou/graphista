
import pytest
from graphrouter.transaction import Transaction, TransactionStatus, TransactionError

def test_transaction_initialization():
    tx = Transaction()
    assert tx.status == TransactionStatus.ACTIVE

def test_transaction_commit():
    tx = Transaction()
    operations_called = []
    
    def op1():
        operations_called.append("op1")
        
    def rollback1():
        operations_called.append("rollback1")
        
    tx.add_operation(op1, rollback1)
    tx.commit()
    
    assert tx.status == TransactionStatus.COMMITTED
    assert operations_called == ["op1"]

def test_transaction_rollback():
    tx = Transaction()
    operations_called = []
    
    def op1():
        operations_called.append("op1")
        raise Exception("Operation failed")
        
    def rollback1():
        operations_called.append("rollback1")
        
    tx.add_operation(op1, rollback1)
    
    with pytest.raises(TransactionError):
        tx.commit()
        
    assert tx.status == TransactionStatus.ROLLED_BACK
    assert operations_called == ["op1", "rollback1"]

def test_invalid_transaction_operations():
    tx = Transaction()
    tx.commit()
    
    with pytest.raises(TransactionError):
        tx.add_operation(lambda: None, lambda: None)
        
    with pytest.raises(TransactionError):
        tx.commit()
        
    with pytest.raises(TransactionError):
        tx.rollback()
