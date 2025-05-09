# PM001 爬虫与分析系统

这是一个用于抓取 PM001 网站数据并进行 AI 分析的自动化系统。系统分为两个独立的工作流，实现数据抓取和 AI 分析的分离运行。

## 系统架构

系统采用完全分离的双工作流架构，具有以下特点：

1. **爬虫工作流**：负责数据采集和存储
2. **分析工作流**：负责数据分析和通知

这种分离架构有以下优势：

- 错误隔离：一个流程的失败不会影响另一个
- 独立扩展：可以单独优化或扩展每个工作流
- 资源优化：可以为不同工作流分配不同的资源

## 工作流程

### 爬虫工作流 (crawler.yml)

1. 每天自动运行或手动触发
2. 抓取 PM001 网站的最新帖子数据
3. 将数据保存为 TSV 格式文件
4. 创建以日期命名的存档数据
5. 创建状态文件记录运行结果
6. 触发分析工作流

### 分析工作流 (analyzer.yml)

1. 由爬虫工作流触发或手动触发
2. 读取指定日期的爬虫数据
3. 使用 AI (Gemini API) 分析数据趋势
4. 生成分析报告
5. 发送通知到指定渠道（钉钉、飞书、企业微信等）
6. 创建状态文件记录分析结果

## 文件结构

- `测试.py` - 爬虫脚本
- `ai.py` - AI 分析脚本
- `update_status.py` - 工作流状态更新工具
- `.github/workflows/crawler.yml` - 爬虫工作流定义
- `.github/workflows/analyzer.yml` - 分析工作流定义
- `data/daily/YYYY-MM-DD/` - 按日期存档的爬虫数据
- `analysis/daily/YYYY-MM-DD/` - 按日期存档的分析结果

## 环境变量配置

系统需要以下环境变量（GitHub Secrets）：

- `GEMINI_API_KEY` - Google Gemini API 密钥
- `DINGTALK_WEBHOOK_URL` - 钉钉机器人 Webhook URL（可选）
- `FEISHU_WEBHOOK_URL` - 飞书机器人 Webhook URL（可选）
- `WECHAT_WORK_WEBHOOK_URL` - 企业微信机器人 Webhook URL（可选）
- `GITHUB_TOKEN` - GitHub 令牌（系统默认提供）

## 手动运行

### 手动运行爬虫

1. 进入 GitHub 仓库
2. 点击"Actions"选项卡
3. 选择"PM001 爬虫任务"
4. 点击"Run workflow"按钮
5. 点击"Run workflow"确认

### 手动运行分析

1. 进入 GitHub 仓库
2. 点击"Actions"选项卡
3. 选择"PM001 AI 分析任务"
4. 点击"Run workflow"按钮
5. 填写数据日期和文件路径
6. 点击"Run workflow"确认

## 错误处理

每个工作流都有独立的状态文件，记录在`.github/status/`目录下：

- `crawler_status.json` - 爬虫运行状态
- `analyzer_status.json` - 分析运行状态

可以通过检查这些文件来诊断问题。

## 维护与扩展

### 添加新的爬虫目标

修改`测试.py`中的`TARGET_BOARD_IDS`列表添加更多板块。

### 修改 AI 分析提示词

修改`ai.py`中的`_get_ai_insights`方法中的`analysis_prompt`字符串。

### 添加新的通知渠道

在`ai.py`的`NotificationSender`类中添加新的发送方法，并在`send_notification`方法中调用。
