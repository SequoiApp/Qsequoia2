# Changelog

All notable changes to QSequoia2 will be documented in this file.

## [1.0.10] - 2026-06-23

### Changed
- Complete refactor of ua_checker module :
  - Minimal UI 
  - Coherence check of all descriptive field inside same UG
  - Auto-select & zoom on UA 
- New `QS2_surface_soumise` variable based on `DGD_SOUMIS` & `DGD_BOISE` fields
- Update new aliases to macth new RSequoia2 layer (LIDAR & OCCUPATION)

## [1.0.8] - 2026-04-17

### Added
- Multi-style reading for sequoia layer 

### Changed

### Fixed
- Show a message bar warning when the Add Data module skips an already loaded layer

## [1.1.0] - 2026-06-23

### Added
- add new var QS2_surface_soumise & keep only surface total in forest_data

### Changed
- Renamed the `check` table to `ua_checker`.
- Ported `ua_check` to Python for direct UA verification.
- Complete `ua_check` UI refactor.
- Added methods to list forest plots and sub-plots in `ua_check_utils`.

### Fixed
