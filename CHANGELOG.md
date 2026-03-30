## [3.11.3] - 2026-03-30

### 🐛 Bug Fixes

- *(build)* Add missing LICENSE.md

### 📚 Documentation

- Fix syntax

### ⚙️ Miscellaneous Tasks

- Replace mypy with ty for type checking
- *(build)* Relax uv_build upper bound to <1.0.0
- Bump version to 3.11.3
## [3.11.2] - 2026-01-20

### 🐛 Bug Fixes

- Update dependencies to address security vulnerabilities

### ⚙️ Miscellaneous Tasks

- Bump version to 3.11.2
## [3.11.1] - 2026-01-20

### 🐛 Bug Fixes

- Drop Python 3.9 support to fix filelock vulnerability

### ⚙️ Miscellaneous Tasks

- Bump version to 3.11.1
## [3.11.0] - 2026-01-13

### 🚀 Features

- Add --ffmpeg-path option

### ⚙️ Miscellaneous Tasks

- Update support to python 3.15
- Test only Python 3.9 and 3.15
- Bump version to 3.11.0

### ◀️ Revert

- Use Python 3.14 instead of 3.15
## [3.10.0] - 2025-11-01

### 🚀 Features

- Add --start-offset and --num-frames options

### 🐛 Bug Fixes

- Resolve mypy type errors
- Configure mypy to ignore dash library type issues

### 📚 Documentation

- Add Visual Information Fidelity wiki link (#73)
- Add antonkesy as a contributor for doc (#74)

### 🧪 Testing

- Increase threshold to account for cross-platform differences

### ⚙️ Miscellaneous Tasks

- Remove gitchangelog files
- Bump version to 3.10.0
## [3.9.0] - 2025-10-22

### 🚀 Features

- Allow multi-clip comparison

### 🐛 Bug Fixes

- Type errors

### ⚙️ Miscellaneous Tasks

- Bump version to 3.9.0
## [3.8.0] - 2025-10-20

### 🚀 Features

- Add optional GUI

### 🧪 Testing

- Update tests for ffmpeg 8.0

### ⚙️ Miscellaneous Tasks

- Bump version to 3.8.0
## [3.7.2] - 2025-10-17

### ⚙️ Miscellaneous Tasks

- Add commitizen for conventional commits
- Fix .pre-commit-config.yaml formatting
- Add python 3.14 support, remove old license classifier
- Bump version to 3.7.2
## [3.7.0] - 2025-08-17

### 🚀 Features

- Add output-file option

### 🧪 Testing

- Add/rename output file tests

### ⚙️ Miscellaneous Tasks

- Fix pytest command
- Extract cached ffmpeg (#71)
## [3.6.1] - 2025-08-15

### 💼 Other

- Prevent pstdev crash on non-finite values (Python 3.13) (#69)
## [3.1.1] - 2022-12-18

### 📚 Documentation

- Update README.md [skip ci]
- Create .all-contributorsrc [skip ci]
- Update README.md [skip ci]
- Update .all-contributorsrc [skip ci]
- Update README.md [skip ci]
- Update .all-contributorsrc [skip ci]
## [0.1.0] - 2019-04-15

### 💼 Other

- Add VMAF
