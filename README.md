# PM001 爬虫与 AI 分析系统

## 项目概述

PM001 爬虫与 AI 分析系统是一个全自动化的数据爬取、分析和通知解决方案，专为采集 PM001 网站的交易平台数据而设计。系统利用 GitHub Actions 实现定时爬取数据，并使用 Google Gemini API 进行深度内容分析和通知分发。

### 核心功能

- **自动数据采集**：定时从 PM001 网站爬取各个板块的最新帖子
- **智能内容分析**：使用 Gemini API 对帖子内容进行分类和信息提取
- **多渠道通知**：支持钉钉、飞书、企业微信等多种通知渠道
- **历史数据存档**：按日期自动归档所有爬取和分析结果
- **灵活的工作流**：支持自动定时执行和手动触发两种模式

## 系统架构

系统采用完全分离的双工作流架构，提高了系统的稳定性和可维护性：

### 爬虫工作流 (`main.yml`与`crawler.yml`)

- 负责数据采集、清洗和保存
- 创建按日期组织的数据存档
- 生成状态报告和执行日志
- 触发分析工作流

### 分析工作流 (`analyzer.yml`与`ai_analysis.yml`)

- 读取爬虫采集的数据
- 使用 AI 进行深度内容分析
- 生成结构化的分析报告
- 向指定渠道发送通知

## 技术实现细节

### 爬虫模块 (`测试.py`)

- 使用`requests`和`BeautifulSoup`实现网页解析
- 实现错误重试、请求延迟和随机 User-Agent 等反爬策略
- 支持多板块并发爬取和时间范围过滤
- 数据以 TSV 格式存储，便于后续处理

### AI 分析模块 (`ai.py`)

- 通过 OpenAI 兼容接口调用 Google Gemini API
- 支持批量处理和并发分析大量数据
- 实现了专门的内容分类和价格信息提取算法
- 生成结构化 TSV 格式的分析结果

### 通知模块 (集成在`ai.py`中)

- 支持钉钉、飞书、企业微信等主流团队协作平台
- 统一的通知内容生成和消息格式转换
- 灵活的配置选项和失败重试机制

## 数据结构

系统处理的数据主要包括：

1. **原始爬取数据**：以 TSV 格式存储，包含板块 ID、标题、作者、日期、回复数等字段
2. **AI 分析结果**：结构化提取的帖子意图（收购/出售）、物品名称、价格信息等
3. **通知内容**：根据分析结果生成的摘要和洞察，包含数据概览和关键发现

## 部署与配置

### 环境变量配置

系统需要以下 GitHub Secrets 配置：

- `GEMINI_API_KEY`：Google Gemini API 密钥
- `DINGTALK_WEBHOOK_URL`：钉钉机器人 Webhook 地址（可选）
- `FEISHU_WEBHOOK_URL`：飞书机器人 Webhook 地址（可选）
- `WECHAT_WORK_WEBHOOK_URL`：企业微信机器人 Webhook 地址（可选）
- `WORKFLOW_PAT`：GitHub 个人访问令牌，用于工作流之间的触发

### 工作流配置

爬虫和分析工作流可以通过修改`.github/workflows/`目录下的 YAML 文件进行配置：

- 调整执行频率（默认爬虫每天执行一次）
- 修改爬取的板块范围和时间窗口
- 调整分析批次大小和并发数

## 使用指南

### 自动运行模式

系统默认配置为：

- 爬虫工作流：每天 UTC 时间 22 点（北京时间次日 6 点）自动运行
- 分析工作流：在爬虫完成后自动触发

### 手动触发爬虫

1. 进入 GitHub 仓库页面
2. 点击"Actions"选项卡
3. 选择"PM001 Web Scraper"或"PM001 爬虫任务"工作流
4. 点击"Run workflow"按钮
5. 点击绿色"Run workflow"按钮确认

### 手动触发分析

1. 进入 GitHub 仓库页面
2. 点击"Actions"选项卡
3. 选择"PM001 AI 分析任务"工作流
4. 点击"Run workflow"按钮
5. 填写数据日期和文件路径参数
6. 点击绿色"Run workflow"按钮确认

## 数据文件结构

- `/data/daily/YYYY-MM-DD/`：按日期归档的原始爬取数据
- `/analysis/daily/YYYY-MM-DD/`：按日期归档的分析结果
- `/.github/status/`：工作流执行状态记录

## 故障排除

### 常见问题

1. **爬虫无法获取数据**

   - 检查网站结构是否发生变化
   - 查看爬虫日志中的错误信息
   - 调整请求延迟参数减轻反爬限制

2. **AI 分析失败**

   - 确认 Gemini API 密钥是否正确配置
   - 检查输入数据格式是否符合要求
   - 查看是否达到 API 调用限制

3. **通知未发送**
   - 确认 Webhook URL 是否正确配置
   - 检查分析结果是否成功生成
   - 查看通知发送日志中的错误信息

### 日志与状态文件

- 爬虫状态：`.github/status/crawler_status.json`
- 分析状态：`.github/status/analyzer_status.json`
- 运行日志：在 GitHub Actions 执行记录中查看

## 定制与扩展

### 添加新的爬取目标

修改`测试.py`中的`TARGET_BOARD_IDS`列表，添加需要爬取的板块 ID。

### 自定义 AI 分析逻辑

在`ai.py`的`_get_ai_insights`方法中修改`analysis_prompt`，调整分析提示词和输出要求。

### 添加新的通知渠道

扩展`NotificationSender`类，添加新的发送方法，并在`send_notification`中调用。

## 项目文件说明

- `测试.py`：爬虫主程序，负责数据采集
- `ai.py`：AI 分析和通知发送模块
- `.github/workflows/main.yml`：主爬虫工作流
- `.github/workflows/crawler.yml`：增强版爬虫工作流
- `.github/workflows/analyzer.yml`：AI 分析工作流
- `.github/workflows/ai_analysis.yml`：通用 AI 分析工作流

## 维护与贡献

- 定期检查网站结构变化，更新爬虫逻辑
- 优化 AI 提示词以提高分析准确性
- 增强错误处理和日志记录机制
