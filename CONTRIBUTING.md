# 贡献指南

## 本地开发

```bash
python3 -m venv .venv
.venv/bin/pip install -r deploy/requirements.txt
.venv/bin/python local/server.py --port 8765
```

或直接跑 `./run.sh`（会自动建 venv、装依赖、读环境变量）。

## 测试

```bash
python -m unittest discover -s tests -t . -v
```

10 个用例，全部离线，不调用真实模型。改代码后先跑测试。

## 规则

- 不提交密钥、账号库、用户照片：`.secrets/`、`SHIYI_DATA_DIR` 指向的目录都不进版本控制；
- 不新增数据库服务或 Web 框架——后端保持 Python 标准库 + Pillow；
- 新功能带隔离测试（`tests/`），不要用真实付费生图做回归；
- 不把模拟结果描述成真实联调通过。

## 提交

提交信息写清动机和验证方式即可，中英文不限。

## 许可

提交即同意以 MIT 许可发布。
