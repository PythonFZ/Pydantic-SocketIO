# Change Log

All notable changes to Pydantic-SocketIO will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).



## [0.1.4] - 2026-01-31

### Added

- **Typed Wrapper API**: New `wrap()` function to add fully typed `emit()`, `call()`, and handler registration to any existing socketio instance
  - `wrap(sio)` returns a typed wrapper (`AsyncClientWrapper`, `AsyncServerWrapper`, `SyncClientWrapper`, `SyncServerWrapper`)
  - Automatic event name derivation from model class names (e.g., `Ping` -> `"ping"`)
  - `response_model` parameter in `call()` for typed responses using PEP 747 TypeForm
  - `@tsio.on(Model)` and `@tsio.event` decorators with FastAPI-style validation from type hints
  - `get_event_name()` helper function for deriving event names from BaseModel classes
- **SimpleClient Support**: `wrap()` now supports `SimpleClient` and `AsyncSimpleClient`
  - `SimpleClientWrapper` and `AsyncSimpleClientWrapper` classes
  - Typed `receive()` method with `response_model` parameter for validating incoming events
- Support for union response types (e.g., `Success | Error`) and discriminated unions

### Changed

- **BREAKING**: Minimum Python version is now 3.10 (previously 3.8)
- Added `typing_extensions>=4.13.0` as a core dependency for TypeForm support

### Migration Guide

If you're upgrading from 0.1.x and using Python 3.8 or 3.9, you'll need to upgrade to Python 3.10+. The core API remains backward compatible - only the minimum Python version has changed.



## [0.1.3] - 2025-10-08

### Added

- Support emit event data type validation
- Better type hint for IDE support

### Fixed

- Fix `Annotated` import issue for python 3.8



## [0.1.2] - 2025-06-19

### Fixed

- Check fastapi installation to avoid module not found error.



## [0.1.1] - 2025-03-18

### Added

- `SioDep` as `FastAPISocketIO` dependency injection in FastAPI applications.



## [0.1.0] - 2025-03-16

### Added

Initial features:

- Pydantic enhanced socketio server and client (both sync and async). They should be drop-in replacements for the original socketio server and client.
- Alternatively, monkey patching method `monkey_patch()` for the original socketio server and client.
- Integration with fastapi `FastAPISocketIO`.
