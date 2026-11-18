# 发布源说明

本目录（Mac 上的 `dsh-core/projects/tryon-oss`）是 TRY-ON 公开发布副本的**唯一发布源**。2026-11-18 决定（D-007）。

## 为什么

Windows 侧 `F:\Harness\build_tryon_oss.ps1` 会**删除目标目录、从 `C:\Users\Administrator\Documents\ChatGPT\TRY-ON` 工作副本整目录重建**。2026-11-18 在 Mac 侧做了一轮发布前整理（移出内部文档与截图、修 `install.sh`、模板改名、补 CONTRIBUTING/run.sh）。重跑构建会把这一轮全部覆盖。

## 规则

1. **不要**在 Windows 上重跑 `build_tryon_oss.ps1` 覆盖本目录；
2. 改发布物：直接在 Mac 本目录改 → 跑测试 → 提交；
3. 上游业务代码（`local/`、`web/`）有更新时：人工 diff 后合入，不要整目录覆盖；
4. 内部材料（`AGENTS.md`、三份路线/状态文档、完整截图）在 `../tryon-internal/`，不进仓库。

## 本轮相对 Windows 副本的差异

| 项 | 处理 |
|---|---|
| `AGENTS.md` | 移出到 `tryon-internal/` |
| `docs/产品理念与已确认决策.md`、`docs/产品审视与下一阶段计划.md`、`docs/当前状态与依赖.md` | 移出到 `tryon-internal/docs/` |
| `docs/ui/` 32 张截图 | 移出到 `tryon-internal/ui/`，仓库只留 `docs/screenshots/` 4 张已核验图 |
| `deploy/nginx-hk.conf` | 改名 `nginx-site.conf`（去地域后缀） |
| `deploy/install.sh` | 用户检查 `www` → `www-data`，与 service 一致 |
| `deploy/部署说明.md` | 去掉「宝塔」，`www` 改 `www-data` |
| 新增 | `CONTRIBUTING.md`、`run.sh`、`.editorconfig`、本文件 |
| README | 增加截图区与命名说明 |
| 版本库 | 重建 git（Syncthing 只同步了空的 `.git/`，Windows 侧提交历史未过来） |

## 验证

- `python -m unittest discover -s tests -t .` → 10/10 通过（macOS 3.12 + Pillow 12.3）
- `GET /` 200、`GET /api/me` 200（访客模式）
- 全仓扫描无密钥、无手机号/邮箱、无生产域名
