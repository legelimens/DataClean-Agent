# DataClean-Agent

面向企业表格数据的数据质量检测与自动清洗助手（Agentic Coding Demo）。

## 1. 项目简介
DataClean-Agent 用“多 Agent 协作”方式，把脏 CSV 数据自动处理成可分析数据，适合演示企业数据治理场景：
- 输入：上传或粘贴 CSV（支持非标准表头）
- 处理：画像、质检、策略生成、清洗、验证、报告
- 输出：清洗数据、指标对比、图表、报告、ZIP 打包

## 2. 核心功能
- 支持命令行和网页两种使用方式
- 自动字段映射：非固定表头也能清洗（如 Café Sales 数据）
- 清洗规则覆盖：缺失值、重复值、日期异常、金额异常、年龄异常、手机号异常、城市/状态标准化
- 实时日志：逐步展示各 Agent 执行过程
- 输出中文报告：`md + html + json + png + csv`
- 可选接入 LLM（如千问）增强策略建议，不影响离线规则清洗

## 3. Agent 架构
- `ProfilerAgent`：读取数据并做基础画像
- `QualityAgent`：识别各类数据质量问题
- `StrategyAgent`：生成清洗策略（规则为主，可选 API 增强）
- `CleanerAgent`：执行清洗并产出标准化数据
- `ValidatorAgent`：计算清洗前后指标和质量分数
- `ReportAgent`：生成 Markdown/HTML 报告

## 4. 项目结构
```text
dataclean_agent/
├── README.md
├── requirements.txt
├── main.py
├── web_app.py
├── data/
│   └── dirty_orders.csv
├── outputs/
│   └── .gitkeep
├── web/
│   └── index.html
├── agents/
│   ├── __init__.py
│   ├── profiler_agent.py
│   ├── quality_agent.py
│   ├── strategy_agent.py
│   ├── cleaner_agent.py
│   ├── validator_agent.py
│   └── report_agent.py
├── utils/
│   ├── __init__.py
│   ├── data_generator.py
│   ├── schema_mapper.py
│   ├── llm_client.py
│   ├── metrics.py
│   └── visualization.py
├── tests/
│   ├── test_cleaning.py
│   └── test_web_app.py
└── video_script_by_file_order.md
```

## 5. 安装依赖
```bash
pip install -r requirements.txt
```

## 6. 运行方式
### 6.1 命令行模式
```bash
python main.py
```

### 6.2 网页模式（推荐演示）
```bash
python web_app.py
```

浏览器访问：
```text
http://127.0.0.1:8000
```

## 7. 网页端功能说明
- 上传 CSV 文件或直接粘贴 CSV 文本
- 自动字段映射和映射预览
- 实时滚动日志（显示每个 Agent 在做什么）
- 清洗前后数据表对比
- 指标卡片 + 对比图展示
- 下载单个结果文件或整包 ZIP
- 保留最近 5 次运行历史

输入限制：
- 单次最多 2000 行
- 支持固定订单字段与非标准业务字段

## 8. 输出文件说明
每次运行会生成如下结果（命令行默认在 `outputs/`，网页模式在 `outputs/runs/<job_id>/`）：
- `clean_orders.csv`：清洗后数据
- `quality_metrics.json`：清洗前后指标与质量分
- `data_quality_report.md`：Markdown 报告
- `data_quality_report.html`：HTML 报告（演示友好）
- `quality_comparison.png`：指标对比图
- `input_original.csv`：原始输入副本（网页模式）
- `input_mapped_for_pipeline.csv`：映射后的中间数据（网页模式）
- `schema_mapping.json`：字段映射详情（网页模式）
- `dataclean_outputs.zip`：一键下载包（网页模式）

## 9. 可选 API 接入（千问示例）
默认关闭 API，规则清洗可独立运行。  
如需启用千问增强策略建议：

```powershell
$env:DATACLEAN_ENABLE_LLM="1"
$env:DATACLEAN_PROVIDER="qwen"
$env:DATACLEAN_API_KEY="你的DashScope密钥"
$env:DATACLEAN_API_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:DATACLEAN_MODEL="qwen-plus"
python web_app.py
```

说明：
- API 主要用于生成“补充建议”，不替代核心清洗规则
- 即使 API 不可用，主流程仍可稳定运行

## 10. 测试
```bash
pytest -q
```

覆盖点：
- 无完全重复行
- 日期标准化（`YYYY-MM-DD` 或 `unknown`）
- 年龄范围合法（0~120）
- 金额非负
- 状态值规范（`paid/refund/cancelled/unknown`）
- 城市值规范（中文城市名或 `unknown`）
- 输出文件可生成

## 11. GitHub 提交建议
本仓库已清理运行产物，仅保留源码和必要示例数据。  
建议提交流程：

```bash
git init
git add .
git commit -m "feat: DataClean-Agent initial release"
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```

## 12. 演示脚本
可直接使用：
- `video_script_by_file_order.md`
