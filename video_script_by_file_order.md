# DataClean-Agent 

## 0. 完整功能介绍
DataClean-Agent 是一个面向企业表格数据治理的智能清洗 Demo，核心能力是“从脏数据到可分析数据”的一站式自动化流程。  

完整功能包括：
1. **多入口导入**：支持上传 CSV 或粘贴 CSV 文本。  
2. **非标准表头兼容**：支持自动字段映射（如 `Transaction ID`、`Total Spent`），并支持手工 JSON 覆盖。  
3. **映射预览确认**：清洗前可先预览映射结果，避免错配字段导致误清洗。  
4. **多 Agent 协作清洗**：Profiler、Quality、Strategy、Cleaner、Validator、Report 六个 Agent 分工协作。  
5. **规则清洗主流程**：去重、日期标准化、金额异常修复、年龄修复、手机号异常标记、城市与状态规范化。  
6. **可选 LLM 策略增强**：支持 Qwen/OpenAI 兼容接口，仅增强策略建议，失败自动回退规则模式。  
7. **质量评估可解释**：自动计算清洗前后质量指标和质量分，按“已映射字段范围”评分，避免不相关字段误罚。  
8. **实时日志追踪**：网页实时滚动显示每个 Agent 的执行过程，便于演示和审计。  
9. **多维结果展示**：指标卡片、对比图、原始/清洗后全量数据表、字段映射结果。  
10. **结果导出与归档**：支持下载 `clean_orders.csv`、`quality_metrics.json`、Markdown/HTML 报告、映射文件与 ZIP。  
11. **历史任务回放**：保留最近 5 次任务，支持复核、复测和答辩回放。 

**它不仅能清洗数据，还能解释“为什么这么清洗”，并把过程和结果完整沉淀为可复核资产。**


## 1. requirements.txt
核心数据处理用 `pandas/numpy/matplotlib`，测试用 `pytest`，网页端用 `fastapi/uvicorn/python-multipart`。  

## 2. main.py
`main.py` 是命令行入口和流水线编排器。  
它串联 6 个 Agent：Profiler、Quality、Strategy、Cleaner、Validator、Report。  
如果 `data/dirty_orders.csv` 不存在，它会自动生成演示脏数据。  
随后按顺序执行清洗，并输出 `CSV/JSON/MD/HTML/PNG`。  
另外它支持 `quality_scope_fields`，实现“按映射字段范围评分”，避免非标准数据被误罚。

## 3. web_app.py
`web_app.py` 是网页后端。  
核心接口：
1. `/api/jobs`：创建清洗任务
2. `/api/jobs/{job_id}`：轮询任务状态和实时日志
3. `/api/mapping/preview`：先预览字段映射
4. `/api/history`：查看最近任务历史
5. `/api/jobs/{job_id}/download/...`：下载结果文件

每次任务都会落盘到 `outputs/runs/<job_id>/`，并保留最近 5 次。

## 4. data/dirty_orders.csv
这是内置模拟脏数据。  
当你不上传外部数据时，系统会用它演示缺失值、重复值、格式错误和异常值清洗流程。

## 5. web/index.html
这是单页前端，也是演示主界面。  
页面分区：
1. 左侧输入与参数：上传 CSV、粘贴 CSV、配置 Qwen/OpenAI、映射 JSON
2. 预览映射：先看字段映射是否正确，再执行清洗
3. 右侧执行日志：实时展示每个 Agent 执行过程
4. 指标卡片：展示清洗前后质量变化
5. 映射结果区：展示标准字段与源字段的对应关系
6. 对比图：可视化问题数量变化
7. 原始/清洗后全量表格：逐行复核
8. 下载区：导出 CSV/JSON/报告/ZIP
9. 历史区：快速回看最近 5 次任务

## 6. agents/__init__.py
Agent 模块导出入口，统一管理 6 个 Agent 类。

## 7. agents/profiler_agent.py
ProfilerAgent 负责数据画像：
1. 读取数据
2. 统计行列
3. 统计缺失值
4. 推断字段类型

## 8. agents/quality_agent.py
QualityAgent 负责问题检测：
1. 缺失值
2. 重复行
3. order_id 重复
4. 日期异常
5. 金额异常
6. 年龄异常
7. 手机号异常
8. 城市/状态不统一

并输出结构化问题清单供后续策略使用。

## 9. agents/strategy_agent.py
StrategyAgent 负责把问题转成规则策略。  
例如“删重、日期标准化、异常值填充、状态统一”等。  
如果开启 API，会调用 Qwen 生成“补充建议”，但不会直接改动核心执行逻辑。

## 10. agents/cleaner_agent.py0
CleanerAgent 执行清洗动作：
1. 删除完全重复行
2. 按 order_id 去重
3. 日期统一成 `YYYY-MM-DD`，非法填 `unknown`
4. 金额异常修复并标记 `amount_is_outlier`
5. 年龄异常修复并标记 `age_is_invalid`
6. 手机号异常替换 `missing_phone` 并标记
7. 城市、状态标准化

## 11. agents/validator_agent.py
ValidatorAgent 负责清洗前后复算指标并计算质量分。  
当前采用“按映射字段范围计分”，确保 Café 这类非标准表头数据不会被不相关规则误罚。

## 12. agents/report_agent.py
ReportAgent 生成 Markdown 和 HTML 报告。  
报告包含：
1. 项目简介
2. Agent 协作流程
3. 原始问题统计
4. 清洗策略
5. 清洗规则总表（规则/默认值/可配置）
6. 清洗前后对比
7. 示例数据对比
8. 结论

## 13. utils/__init__.py
工具模块入口。

## 14. utils/data_generator.py
用于自动生成演示脏数据，支持离线快速演示。

## 15. utils/metrics.py
质量指标和评分核心：
1. 指标计算
2. 评分公式
3. 按映射字段范围评分
4. 避免空值重复惩罚

## 16. utils/schema_mapper.py
泛化输入核心：
1. 自动字段映射（别名和轻量语义匹配）
2. 手工映射 JSON 覆盖
3. 语义提示（如 Location、Payment Method 的降噪处理）

## 17. utils/llm_client.py
LLM 适配层，支持 Qwen/OpenAI 兼容调用。  
主要用于 StrategyAgent 补充建议，失败自动回退规则模式。

## 18. utils/visualization.py
生成质量对比图。  
图尺寸已收敛，保证网页显示协调。

## 19. tests/test_cleaning.py
核心清洗结果测试：去重、日期、金额、状态、城市、输出文件等。

## 21. tests/test_web_app.py
网页接口测试：任务创建、映射预览、ZIP 下载、历史记录上限等。

## 22. pytest.ini
测试配置文件，避免扫描缓存目录导致误报。

## 23. README.md
项目说明文档：运行方式、网页演示、API 配置、输出说明。

## 24. video_demo_script.md
通用讲稿和操作脚本，适合快速录制。

## 25. outputs/
最终产物目录：
1. `clean_orders.csv`
2. `quality_metrics.json`
3. `data_quality_report.md`
4. `data_quality_report.html`
5. `quality_comparison.png`
6. `runs/`（每次网页任务独立产物）

---

## 总结
这个项目展示了：  
1. 非标准表头数据也能清洗（靠映射层）  
2. 清洗过程可解释（实时日志+规则总表）  
3. 结果可复核（全量表+下载产物+历史任务）  
4. 可扩展到更多企业数据治理场景。
