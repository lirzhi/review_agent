# 接口解析测试目录

- `test_data/`: 放待测试文件（pdf/doc/docx/txt/md）
- `results/`: 测试输出结果目录
- `run_parse_api_test.py`: 批量调用上传与解析接口，轮询解析进度，并输出分块效果

## 运行示例

```bash
python agent/agent_backend/test/run_parse_api_test.py --base-url http://127.0.0.1:5000
```

执行后会在 `results/` 下生成：
- 每个文档一个 `doc_id.result.json`
- 一份 `summary_*.json` 汇总报告
