# Changelog

All notable changes to GraphRouter will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Async support for database operations in Local, Neo4j, and FalkorDB backends
- Advanced query caching mechanism with pattern-based invalidation
- Comprehensive performance monitoring and metrics collection
- Support for batch operations in Neo4j and FalkorDB backends
- Transaction retry logic with timeout handling
- Connection pooling improvements
- Detailed test coverage for cache and monitoring modules

### Changed
- Enhanced error handling in database implementations
- Improved type safety with better type hints
- Optimized query execution with caching integration
- Updated documentation with advanced usage examples

### Fixed
- Neo4j transaction handling in batch operations
- FalkorDB connection management
- Cache invalidation for complex query patterns
- Performance metrics accuracy in monitoring system

## [0.1.0] - 2025-01-28
- Initial release
- Basic functionality for graph database operations
- Support for Neo4j, FalkorDB, and local JSON storage
- Query builder interface
- Basic test coverage

[Unreleased]: https://github.com/graphrouter/graphrouter/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/graphrouter/graphrouter/releases/tag/v0.1.0