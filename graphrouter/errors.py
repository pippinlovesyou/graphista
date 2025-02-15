"""
Custom exceptions for the GraphRouter library.
"""
from typing import Dict, Optional

class GraphRouterError(Exception):
    """Base exception for all GraphRouter errors."""
    pass

class ConnectionError(GraphRouterError):
    """Raised when there are issues connecting to the database."""
    pass

class QueryError(GraphRouterError):
    """Raised when there are issues with query execution."""
    pass

class QueryValidationError(GraphRouterError):
    """Raised when there are validation errors in query construction."""
    pass

class OntologyError(GraphRouterError):
    """Base class for ontology-related errors."""
    def __init__(self, message: str, available_options: Optional[dict] = None):
        self.available_options = available_options
        super().__init__(message)

class InvalidNodeTypeError(OntologyError):
    """Raised when an invalid node type is used."""
    pass

class InvalidPropertyError(OntologyError):
    """Raised when invalid properties are provided."""
    pass

class TransactionError(GraphRouterError):
    """Raised when there are issues with transaction operations."""
    pass