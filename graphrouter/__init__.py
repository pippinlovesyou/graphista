"""
GraphRouter - A flexible graph database router with multiple backend support.
"""

from .base import GraphDatabase
from .local import LocalGraphDatabase
from .neo4j import Neo4jGraphDatabase
from .falkordb import FalkorDBGraphDatabase
from .ontology import Ontology
from .query import Query
from .errors import (
    GraphRouterError,
    ConnectionError,
    QueryError,
    OntologyError
)

__version__ = "0.1.0"
__all__ = [
    'GraphDatabase',
    'LocalGraphDatabase',
    'Neo4jGraphDatabase',
    'FalkorDBGraphDatabase',
    'Ontology',
    'Query',
    'GraphRouterError',
    'ConnectionError',
    'QueryError',
    'OntologyError'
]