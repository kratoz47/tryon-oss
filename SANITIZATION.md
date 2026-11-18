# 脱敏说明

本仓库由内部项目的工作副本整理而来，用于公开发布。整理日期 2026-11-18。

## 已移除

- 生产部署记录（含服务器地址、SSH 账户、应用目录、密码文件与证书路径）
- 短信登录的运营配置（云厂商签名/模板、RAM 授权策略）
- 内部交接文档（重复了服务器地址与目录结构）
- 内部代码快照清单
- `.secrets/`、`__pycache__/`、`*.pyc`：密钥、账号数据库与字节码，从未进入版本控制

## 已替换

`deploy/` 下的模板中，生产环境的绝对路径、运行用户与域名统一改成了通用 Unix 值，安装逻辑不变。

## 已修复

`tests/test_guest_access.py` 在 Windows 上清理临时目录时因 sqlite 句柄未关闭而报 `PermissionError`，改为 `TemporaryDirectory(ignore_cleanup_errors=True)`。这是测试基建问题，未改动 `local/` 业务代码。

## 发布前整理（2026-11-18 · Mac）

- `AGENTS.md`（内部工作约定）与三份内部路线/状态文档移出仓库，不再随包发布；
- `docs/ui/` 全量界面截图移出，仅保留 4 张确认不含真实用户照片的图（`docs/screenshots/`）；
- 清理 `local/__pycache__/` 与空的 `.git/`（Syncthing 未同步版本库元数据）；
- 修正 `deploy/install.sh` 的用户检查（`www` → `www-data`）与部署文档中的用户名表述；
- 新增 `CONTRIBUTING.md`、`run.sh`、`.editorconfig`。

## 未改动

`local/` 与 `web/` 的代码与原项目工作副本一致；新增 `LICENSE`（MIT）、`.github/workflows/tests.yml`、`tests/__init__.py` 与本 README 体系。
