#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AI功能模块：用于分析爬虫数据并发送通知
使用Google Gemini API通过OpenAI兼容接口进行数据分析
"""

import os
import sys
import json
import pandas as pd
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# 如果使用OpenAI兼容接口调用Gemini API
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("警告: openai 库未安装，AI分析功能将不可用")
    print("可通过 pip install openai 安装")

class AIAnalyzer:
    """使用AI分析爬虫数据并生成洞察"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化AI分析器
        
        参数:
            api_key: Gemini API密钥，如不提供则尝试从环境变量GEMINI_API_KEY获取
        """
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key and HAS_OPENAI:
            print("警告: 未提供API密钥，AI分析功能将不可用")
        
        self.client = None
        if HAS_OPENAI and self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
    
    def analyze_data(self, data_file: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        分析TSV格式的爬虫数据
        
        参数:
            data_file: TSV数据文件路径
            
        返回:
            (数据摘要, AI分析结果)
        """
        # 检查文件是否存在
        if not os.path.exists(data_file):
            print(f"错误: 文件 {data_file} 不存在")
            return {}, None
        
        # 读取TSV文件
        try:
            df = pd.read_csv(data_file, sep='\t')
            print(f"成功读取数据文件，包含 {len(df)} 条记录")
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return {}, None
        
        # 基本统计分析
        summary = self._generate_data_summary(df)
        
        # 使用AI分析数据
        ai_analysis = None
        if self.client:
            ai_analysis = self._get_ai_insights(summary)
            
        return summary, ai_analysis
    
    def _generate_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成数据摘要统计"""
        total_posts = len(df)
        if total_posts == 0:
            return {"total_posts": 0}
        
        # 各板块帖子数量
        board_counts = df['board_id'].value_counts().to_dict()
        
        # 尝试转换日期列
        try:
            df['date'] = pd.to_datetime(df['date'])
            df_sorted = df.sort_values('date', ascending=False)
            date_range = [
                df['date'].min().strftime('%Y-%m-%d'), 
                df['date'].max().strftime('%Y-%m-%d')
            ]
        except:
            # 如果日期转换失败，就使用原始数据
            df_sorted = df
            date_range = ["未知", "未知"]
        
        # 获取最近的帖子
        recent_columns = ['title', 'author', 'date', 'board_id', 'replies', 'views']
        available_columns = [col for col in recent_columns if col in df.columns]
        recent_posts = df_sorted.head(5)[available_columns].to_dict('records')
        
        # 最多回复/浏览的帖子
        if 'replies' in df.columns:
            most_replies = df.sort_values('replies', ascending=False).head(3)[available_columns].to_dict('records')
        else:
            most_replies = []
            
        if 'views' in df.columns:
            most_views = df.sort_values('views', ascending=False).head(3)[available_columns].to_dict('records')
        else:
            most_views = []
        
        # 汇总信息
        summary = {
            "total_posts": total_posts,
            "board_distribution": board_counts,
            "recent_posts": recent_posts,
            "most_replied": most_replies,
            "most_viewed": most_views,
            "date_range": date_range
        }
        
        return summary
    
    def _get_ai_insights(self, summary: Dict[str, Any]) -> Optional[str]:
        """使用Gemini API获取数据洞察"""
        if not self.client:
            return None
            
        try:
            # 构建分析提示词
            analysis_prompt = f"""
            **AI提示词：钱币市场信息提取与分类（收购与出售 - TSV输出）**

            **你的角色：** 你是一个钱币市场信息分析助手。

            **你的任务：**
            请仔细阅读并分析下面提供的每一个帖子标题及其附带的元数据（board_id, title）。你需要：
            1.  判断该帖子的主要意图是 **“收购”（想买）** 还是 **“出售”（想卖）**，或者意图不明确归为 **“其他”**。
            2.  从标题中提取相关的 **“物品名称”**。
            3.  提取任何与价格相关的信息，记录在 **“价格描述”** 中（例如：“428元一捆”，“每张188元”，“1060出”，“金价售”，“高价求购”，“面议”等）。
            4.  如果“价格描述”中包含明确的阿拉伯数字，请将其提取到 **“数值价格”** 字段；若无明确数字，则此字段为空。
            5.  根据意图和价格信息，判断 **“价格类型”**（“收购价”、“出售价”或“N/A”）。
            6.  提取任何与数量相关的信息，记录在 **“数量描述”** 中（例如：“一捆”，“5桶”，“整包”，“5-10枚”）。
            7.  提取描述物品 **“特征/品相”** 的信息（例如：“无油”，“小号”，“靓号”，“原桶”，“评级货”，“无47”，“NGC首日70分”）。
            8.  将提取的信息与给定的 `board_id` 和 `title ` 一同输出。

            **处理规则与注意事项：**

            * **意图分类：**
                * 包含“收购”、“求购”、“求”、“收”、“寻”等通常表示想买。
                * 包含“出”、“售”、“转让”、“批”等通常表示想卖。
                * 若意图不明确，或同时包含买卖信息难以区分，则归为“其他”。
            * **物品名称：** 提取核心的、可识别的物品名称。
            * **价格信息：**
                * “价格描述”要尽可能完整记录原文中关于价格的说法。
                * “数值价格”只填写纯数字，方便后续计算。如果价格是一个范围（如“5-10元”），可记录范围或平均值（并注明），或暂时只记录范围的第一个数字。
                * 如果“价格描述”中没有具体数字（如“高价”、“面议”），则“数值价格”字段留空。
            * **特征/品相：** 记录所有能描述物品状态、版本、评级等关键信息。
            * **完整性：** 尽量为每一个被识别为“收购”或“出售”的帖子都提取信息，即使某些字段（如价格、数量）可能为空。

            **输出格式要求（TSV - Tab-Separated Values）：**
            请直接生成TSV格式的内容。
            * **第一行**应为表头（列名）。
            * 之后的**每一行**代表一条记录。
            * **字段（列）之间用一个制表符（Tab character）分隔。**

            **TSV输出示例：**

            ```tsv
            原始标题文本	意图分类	物品名称	价格描述	数值价格	价格类型	数量描述	特征/品相	板块ID	日期
            (示例) 原捆无油一分428元一捆，小号一分698一捆	出售	一分(纸币)	428元一捆, 698一捆	428, 698	出售价	一捆	原捆无油, 小号	11	2025-05-09 14:20:00
            (示例) 长期收购：三版伍角纺织工人包捆	收购	三版伍角纺织工人		N/A	包捆		11	2025-05-09 14:19:43
            (示例) 1060出龙银币---5桶-原桶	出售	龙银币	1060出	1060	出售价	5桶	原桶	9	2025-05-09 14:18:05
            (示例) 980求龙原桶1000枚	收购	龙(币)	980求	980	收购价	1000枚, 原桶		9	2025-05-09 14:15:06
            ... (根据你提供的数据填写，每一列用制表符分隔)
            """
            
            # 调用Gemini API
            response = self.client.chat.completions.create(
                model="gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": "你是数据分析助手，负责分析爬虫数据并提供简洁的洞察。"},
                    {"role": "user", "content": analysis_prompt}
                ]
            )
            
            # 获取分析结果
            ai_analysis = response.choices[0].message.content
            return ai_analysis
            
        except Exception as e:
            print(f"AI分析过程中出错: {e}")
            return f"AI分析失败: {str(e)}"


class NotificationSender:
    """负责将分析结果发送到各种通知渠道"""
    
    def __init__(self):
        """初始化通知发送器"""
        self.dingtalk_webhook = os.environ.get('DINGTALK_WEBHOOK_URL')
        self.feishu_webhook = os.environ.get('FEISHU_WEBHOOK_URL')
        self.wechat_webhook = os.environ.get('WECHAT_WORK_WEBHOOK_URL')
        self.github_repo = os.environ.get('GITHUB_REPOSITORY', '')
    
    def prepare_notification(self, summary: Dict[str, Any], ai_analysis: Optional[str]) -> str:
        """准备通知内容"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 构建通知内容
        content = f"""### PM001网站数据更新通知

**数据概览**:
- 总帖子数: {summary.get('total_posts', 0)}
- 日期范围: {summary.get('date_range', ['未知', '未知'])[0]} 至 {summary.get('date_range', ['未知', '未知'])[1]}
"""

        # 添加AI分析结果（如果有）
        if ai_analysis:
            content += f"""
**AI分析摘要**:
{ai_analysis}
"""
        else:
            # 如果没有AI分析，添加一些基本统计信息
            board_dist = summary.get('board_distribution', {})
            if board_dist:
                content += "\n**板块分布**:\n"
                for board, count in sorted(board_dist.items(), key=lambda x: x[1], reverse=True)[:5]:
                    content += f"- 板块 {board}: {count} 篇帖子\n"
            
            recent = summary.get('recent_posts', [])
            if recent:
                content += "\n**最新帖子**:\n"
                for post in recent[:3]:
                    title = post.get('title', '无标题')
                    author = post.get('author', '未知')
                    date = post.get('date', '未知日期')
                    content += f"- {title} (作者: {author}, 日期: {date})\n"
        
        # 添加数据链接
        if self.github_repo:
            content += f"""
**查看完整数据**: [GitHub仓库](https://github.com/{self.github_repo}/blob/main/pm001_recent_posts.tsv)
"""
        
        return content
    
    def send_to_dingtalk(self, content: str) -> bool:
        """发送通知到钉钉"""
        if not self.dingtalk_webhook:
            print("未配置钉钉Webhook，跳过发送")
            return False
            
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"PM001爬虫数据更新 ({today})",
                    "text": content
                }
            }
            
            response = requests.post(
                self.dingtalk_webhook,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                print("成功发送通知到钉钉")
                return True
            else:
                print(f"发送到钉钉失败: HTTP {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            print(f"发送钉钉通知时出错: {e}")
            return False
    
    def send_to_feishu(self, content: str) -> bool:
        """发送通知到飞书"""
        if not self.feishu_webhook:
            print("未配置飞书Webhook，跳过发送")
            return False
            
        try:
            # 飞书的消息格式与钉钉不同
            today = datetime.now().strftime('%Y-%m-%d')
            message = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"PM001爬虫数据更新 ({today})"
                        },
                        "template": "blue"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": content
                            }
                        }
                    ]
                }
            }
            
            # 如果有GitHub仓库链接，添加按钮
            if self.github_repo:
                message["card"]["elements"].append({
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看完整数据"
                            },
                            "url": f"https://github.com/{self.github_repo}/blob/main/pm001_recent_posts.tsv",
                            "type": "default"
                        }
                    ]
                })
            
            response = requests.post(
                self.feishu_webhook,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                print("成功发送通知到飞书")
                return True
            else:
                print(f"发送到飞书失败: HTTP {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            print(f"发送飞书通知时出错: {e}")
            return False
    
    def send_to_wechat_work(self, content: str) -> bool:
        """发送通知到企业微信"""
        if not self.wechat_webhook:
            print("未配置企业微信Webhook，跳过发送")
            return False
            
        try:
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
            
            response = requests.post(
                self.wechat_webhook,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                print("成功发送通知到企业微信")
                return True
            else:
                print(f"发送到企业微信失败: HTTP {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            print(f"发送企业微信通知时出错: {e}")
            return False
    
    def send_notification(self, content: str) -> bool:
        """尝试发送到所有配置的通知渠道"""
        success = False
        
        # 尝试发送到钉钉
        if self.dingtalk_webhook:
            dingtalk_success = self.send_to_dingtalk(content)
            success = success or dingtalk_success
        
        # 尝试发送到飞书
        if self.feishu_webhook:
            feishu_success = self.send_to_feishu(content)
            success = success or feishu_success
        
        # 尝试发送到企业微信
        if self.wechat_webhook:
            wechat_success = self.send_to_wechat_work(content)
            success = success or wechat_success
        
        # 如果没有配置任何通知渠道
        if not (self.dingtalk_webhook or self.feishu_webhook or self.wechat_webhook):
            print("警告: 未配置任何通知渠道")
            # 将内容打印到控制台
            print("\n=== 通知内容 ===\n")
            print(content)
            print("\n=================\n")
        
        return success


def analyze_and_notify(data_file: str) -> bool:
    """
    分析数据并发送通知的主函数
    
    参数:
        data_file: TSV数据文件路径
        
    返回:
        是否成功完成分析和通知
    """
    print(f"开始分析文件: {data_file}")
    
    # 1. 初始化AI分析器
    analyzer = AIAnalyzer()
    
    # 2. 分析数据
    summary, ai_analysis = analyzer.analyze_data(data_file)
    if not summary:
        print("无法生成数据摘要，退出")
        return False
    
    # 3. 初始化通知发送器
    sender = NotificationSender()
    
    # 4. 准备通知内容
    notification_content = sender.prepare_notification(summary, ai_analysis)
    
    # 5. 保存分析结果
    try:
        with open('analysis_result.md', 'w', encoding='utf-8') as f:
            f.write(notification_content)
        print("分析结果已保存到 analysis_result.md")
    except Exception as e:
        print(f"保存分析结果时出错: {e}")
    
    # 6. 发送通知
    success = sender.send_notification(notification_content)
    
    return success


if __name__ == "__main__":
    """命令行入口点"""
    # 默认数据文件名
    default_file = "pm001_recent_posts.tsv"
    
    # 从命令行获取文件名
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    else:
        data_file = default_file
        print(f"未指定数据文件，使用默认文件: {default_file}")
    
    # 分析并发送通知
    success = analyze_and_notify(data_file)
    
    # 设置退出代码
    sys.exit(0 if success or os.environ.get('CI') else 1) 