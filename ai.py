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
import math
import re
import concurrent.futures

# 如果使用OpenAI兼容接口调用Gemini API
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("警告: openai 库未安装，AI分析功能将不可用")
    print("可通过 pip install openai 安装")

# board_id到中文名称映射
BOARD_ID_NAME_MAP = {
    # 邮票类
    "5": "小版张专栏", "7": "邮资片JP专栏", "8": "纪特文编JT新票栏目", "120": "年册/集邮工具", "143": "港澳邮票专栏", "159": "编年版票专栏", "160": "贺年封片简卡", "161": "纪特文编JT销封栏目", "162": "小本票/大本册专栏", "168": "邮票、封片靓号专栏", "190": "普封普片", "191": "邮资片TP/YP/FP", "192": "个性化原票专栏", "193": "JF封/其它类封", "195": "贺年邮票/贺卡邮票/军邮邮票", "196": "编年套票栏目", "199": "原地实寄/外交/极限等封片", "211": "邮票大类产品票礼品册",
    # 钱币类
    "2": "钱币大卖场", "9": "现代金银贵金属币", "10": "普通纪念币", "11": "一二三版纸币", "119": "第四版纸币", "128": "纸币冠号（不含流通纸币）", "136": "评级币评级钞", "148": "古币银元", "151": "联体钞/纪念钞", "163": "清朝民国纸币/老银票", "165": "贵金属金银铜纪念章", "169": "外国纸币、硬币", "171": "新中国兑换券、债券、测试券", "184": "港澳台钱币专栏", "210": "硬币专栏",
    # 卡类
    "3": "卡类大卖场", "74": "田村卡IC卡专栏", "185": "其它卡类卖场",
    # 古玩杂项
    "23": "古玩金银铜瓷陶器", "155": "古玩竹木雕漆器", "157": "书报字画", "166": "当代新制玉器", "187": "其它古玩杂件藏品", "198": "历代古玉器"
}

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
            ai_analysis = self._get_ai_insights(df)
            
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
    
    def _get_ai_insights(self, df: pd.DataFrame) -> Optional[str]:
        """使用Gemini API获取数据洞察"""
        if not self.client:
            return None
            
        try:
            analysis_prompt = """
            **AI提示词：钱币市场信息提取与分类（收购与出售 - TSV输出）**

            **你的角色：** 你是一个钱币市场信息分析助手。

            **你的任务：**
            请仔细阅读并分析下面提供的每一个帖子标题及其附带的元数据（board_id,board_name, title）。你需要：
            1.  判断该帖子的主要意图是 **"收购"（想买）** 还是 **"出售"（想卖）**，或者意图不明确归为 **"其他"**。
            2.  从标题中提取相关的 **"物品名称"**。
            3.  提取任何与价格相关的信息，记录在 **"价格描述"** 中（例如："428元一捆"，"每张188元"，"1060出"，"金价售"，"高价求购"，"面议"等）。
            4.  如果"价格描述"中包含明确的阿拉伯数字，请将其提取到 **"数值价格"** 字段；若无明确数字，则此字段为空。
            5.  根据意图和价格信息，判断 **"价格类型"**（"收购价"、"出售价"或"N/A"）。
            6.  提取任何与数量相关的信息，记录在 **"数量描述"** 中（例如："一捆"，"5桶"，"整包"，"5-10枚"）。
            7.  提取描述物品 **"特征/品相"** 的信息（例如："无油"，"小号"，"靓号"，"原桶"，"评级货"，"无47"，"NGC首日70分"）。
            8.  将提取的信息与给定的 `board_id` 和 `board_name`和 `title` 一同输出。

            **处理规则与注意事项：**

            * **意图分类：**
                * 包含"收购"、"求购"、"求"、"收"、"寻"等通常表示想买。
                * 包含"出"、"售"、"转让"、"批"等通常表示想卖。
                * 若意图不明确，或同时包含买卖信息难以区分，则归为"其他"。
            * **物品名称：** 提取核心的、可识别的物品名称。
            * **价格信息：**
                * "价格描述"要尽可能完整记录原文中关于价格的说法。
                * "数值价格"只填写纯数字，方便后续计算。如果价格是一个范围（如"5-10元"），可记录范围或平均值（并注明），或暂时只记录范围的第一个数字。
                * 如果"价格描述"中没有具体数字（如"高价"、"面议"），则"数值价格"字段留空。
            * **特征/品相：** 记录所有能描述物品状态、版本、评级等关键信息。
            * **完整性：** 尽量为每一个被识别为"收购"或"出售"的帖子都提取信息，即使某些字段（如价格、数量）可能为空。

            **输出格式要求（TSV - Tab-Separated Values）：**
            请直接生成TSV格式的内容。
            * **第一行**应为表头（列名）。
            * 之后的**每一行**代表一条记录。
            * **字段（列）之间用一个制表符（Tab character）分隔。**

            **TSV输出示例：**

            ```tsv
            原始标题文本	意图分类	物品名称	价格描述	数值价格	价格类型	数量描述	特征/品相	板块ID	板块名称	日期
            (示例) 原捆无油一分428元一捆，小号一分698一捆	出售	一分(纸币)	428元一捆, 698一捆	428, 698	出售价	一捆	原捆无油, 小号	11	钱币大卖场	2025-05-09 14:20:00
            (示例) 长期收购：三版伍角纺织工人包捆	收购	三版伍角纺织工人		N/A	包捆		11	钱币大卖场	2025-05-09 14:19:43
            (示例) 1060出龙银币---5桶-原桶	出售	龙银币	1060出	1060	出售价	5桶	原桶	9	2025-05-09 14:18:05
            (示例) 980求龙原桶1000枚	收购	龙(币)	980求	980	收购价	1000枚, 原桶		9	2025-05-09 14:15:06
            ... (根据你提供的数据填写，每一列用制表符分隔)
            """
            
            tsv_data = df.to_csv(sep='\t', index=False)
            prompt_with_data = analysis_prompt + "\n以下是需要分析的帖子数据（TSV格式）：\n" + tsv_data
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-preview-04-17",
                messages=[
                    {"role": "system", "content": "你是数据分析助手，负责分析爬虫数据并提供简洁的洞察。"},
                    {"role": "user", "content": prompt_with_data}
                ]
            )
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


def extract_tsv_from_ai_output(ai_output: str) -> list:
    """
    从AI输出中提取TSV表头及数据行，过滤说明性文字和错误提示。
    返回TSV行列表（含表头）。
    """
    # 匹配 ```tsv ... ``` 或直接以表头开头的TSV块
    tsv_block = ""
    # 优先找```tsv代码块
    match = re.search(r"```tsv\s*([\s\S]+?)```", ai_output)
    if match:
        tsv_block = match.group(1)
    else:
        # 退而求其次，找以"原始标题文本"开头的行及其下方内容
        lines = ai_output.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith("原始标题文本"):
                tsv_block = "\n".join(lines[idx:])
                break
    # 分割为行，去除空行和错误提示
    tsv_lines = [l for l in tsv_block.splitlines() if l.strip() and not l.startswith("AI分析失败") and not l.startswith("# ")]
    return tsv_lines

def merge_all_ai_tsv_results(ai_outputs: list) -> str:
    """
    合并所有AI输出的TSV内容，只保留第一个表头，去重数据行，并将board_id映射为中文名称，新增"板块名称"列。
    """
    all_lines = []
    header = None
    for ai_output in ai_outputs:
        tsv_lines = extract_tsv_from_ai_output(ai_output)
        if not tsv_lines:
            continue
        if header is None:
            header = tsv_lines[0]
            all_lines.append(header)
            all_lines.extend(tsv_lines[1:])
        else:
            all_lines.extend(tsv_lines[1:])
    # 去重
    all_lines = [all_lines[0]] + list(dict.fromkeys(all_lines[1:]))
    # 替换board_id为中文名称，新增"板块名称"列
    if all_lines:
        header_fields = all_lines[0].split('\t')
        if '板块ID' in header_fields:
            idx = header_fields.index('板块ID')
            if '板块名称' not in header_fields:
                header_fields.insert(idx+1, '板块名称')
            new_lines = ['\t'.join(header_fields)]
            for line in all_lines[1:]:
                fields = line.split('\t')
                if len(fields) > idx:
                    board_id = fields[idx].strip()
                    board_name = BOARD_ID_NAME_MAP.get(board_id, board_id)
                    fields.insert(idx+1, board_name)
                new_lines.append('\t'.join(fields))
            return '\n'.join(new_lines)
    return '\n'.join(all_lines)


def split_and_analyze_by_board(data_file: str, analyzer: 'AIAnalyzer', batch_size: int = 100, max_retry: int = 3, max_workers: int = 5) -> str:
    """
    按board_id分组并分批调用AI分析，合并所有结果为一个TSV字符串，支持每个板块内批次并发。
    """
    if not os.path.exists(data_file):
        print(f"错误: 文件 {data_file} 不存在")
        return "数据文件不存在"

    try:
        df = pd.read_csv(data_file, sep='\t')
        print(f"成功读取数据文件，包含 {len(df)} 条记录")
    except Exception as e:
        print(f"读取文件时出错: {e}")
        return f"读取文件时出错: {e}"

    ai_outputs = []

    def analyze_batch(board_id, batch_idx, num_batches, batch_df):
        print(f"  [INFO] 开始AI分析：板块{board_id} 第{batch_idx+1}/{num_batches}批，数据量：{len(batch_df)} 条")
        ai_result = None
        for attempt in range(1, max_retry+1):
            try:
                ai_result = analyzer._get_ai_insights(batch_df)
                if ai_result and not ai_result.strip().startswith("AI分析失败"):
                    print(f"  [SUCCESS] AI分析完成：板块{board_id} 第{batch_idx+1}/{num_batches}批，返回{len(ai_result)}字符 (第{attempt}次尝试)")
                    print(f"  [AI OUTPUT] 前200字符：\n{ai_result[:200]}\n...")
                    return ai_result
                else:
                    print(f"  [FAIL] AI分析失败或返回无效内容：板块{board_id} 第{batch_idx+1}/{num_batches}批 (第{attempt}次尝试)")
            except Exception as e:
                print(f"  [ERROR] AI分析异常：板块{board_id} 第{batch_idx+1}/{num_batches}批，异常：{e} (第{attempt}次尝试)")
        print(f"  [ERROR] AI分析最终失败：板块{board_id} 第{batch_idx+1}/{num_batches}批，已重试{max_retry}次，跳过该批次")
        return None

    for board_id, group in df.groupby('board_id'):
        group = group.reset_index(drop=True)
        total = len(group)
        num_batches = math.ceil(total / batch_size)
        print(f"分析板块 {board_id}，共{total}条，分为{num_batches}批")
        batch_args = [(board_id, i, num_batches, group.iloc[i*batch_size : (i+1)*batch_size]) for i in range(num_batches)]
        # 并发处理每个板块的批次
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {executor.submit(analyze_batch, *args): idx for idx, args in enumerate(batch_args)}
            # 保证顺序合并
            batch_results = [None] * num_batches
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    batch_results[idx] = result
                except Exception as exc:
                    print(f"  [ERROR] 并发AI分析批次异常: {exc}")
            # 只收集成功的结果
            ai_outputs.extend([r for r in batch_results if r and not r.strip().startswith("AI分析失败")])

    print(f"[INFO] 全部AI分析批次完成，开始合并TSV结果")
    final_tsv = merge_all_ai_tsv_results(ai_outputs)
    print(f"[INFO] 合并完成，总输出{len(final_tsv.splitlines())}行TSV数据")
    return final_tsv


def analyze_and_notify(data_file: str) -> bool:
    """
    分析数据并发送通知的主函数（新版，支持分批AI分析）
    """
    print(f"开始分析文件: {data_file}")

    # 1. 初始化AI分析器
    analyzer = AIAnalyzer()

    # 2. 分批AI分析
    ai_analysis = split_and_analyze_by_board(data_file, analyzer, batch_size=100)
    if not ai_analysis or ai_analysis.startswith("数据文件不存在") or ai_analysis.startswith("读取文件时出错"):
        print("AI分析失败，退出")
        return False

    # 3. 保存分析结果
    try:
        with open('analysis_result.md', 'w', encoding='utf-8') as f:
            f.write("**AI分析TSV结果**:\n")
            f.write("```\n")
            f.write(ai_analysis)
            f.write("\n```\n")
        print("分析结果已保存到 analysis_result.md")
    except Exception as e:
        print(f"保存分析结果时出错: {e}")

    # 4. 可选：发送通知（如需，可拼接简要统计信息）
    # sender = NotificationSender()
    # notification_content = sender.prepare_notification({}, ai_analysis)
    # sender.send_notification(notification_content)

    return True


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
