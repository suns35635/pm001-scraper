# pm001_scraper.py
import requests
from bs4 import BeautifulSoup
import datetime
import re
import csv
import time
import logging
import os
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

#########################################
# 配置部分 - 所有可定制参数集中在此处
#########################################

# 站点配置
BASE_URL = "http://www.pm001.net/"
TARGET_BOARD_IDS = [1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 21, 22, 36]  # 要抓取的板块ID列表
DAYS_LIMIT = 2  # 抓取最近几天的帖子
PAGES_PER_BOARD = 2  # 每个板块抓取的页数

# 网络请求配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_BACKOFF_FACTOR = 0.5  # 重试退避因子
RETRY_STATUS_CODES = [408, 429, 500, 502, 503, 504]  # 触发重试的HTTP状态码
REQUEST_TIMEOUT = 30  # 请求超时时间（秒）

# 延迟配置
PAGE_DELAY_MIN = 2  # 页面间最小延迟（秒）
PAGE_DELAY_MAX = 4  # 页面间最大延迟（秒）
BOARD_DELAY_MIN = 3  # 板块间最小延迟（秒）
BOARD_DELAY_MAX = 6  # 板块间最大延迟（秒）

# 输出配置
OUTPUT_FILENAME = 'pm001_recent_posts.tsv'  # 输出文件名
LOG_FILENAME = 'pm001_scraper.log'  # 日志文件名
LOG_LEVEL = logging.INFO  # 日志级别
TSV_FIELDS = ['board_id', 'page', 'post_id', 'title', 'author', 'date', 'replies', 'views']  # TSV导出字段

# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36 Edg/91.0.864.71',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
]

#########################################
# 初始化部分
#########################################

# 配置日志
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

#########################################
# 工具函数
#########################################

# 获取随机User-Agent
def get_random_user_agent():
    return random.choice(USER_AGENTS)

# 创建带有重试机制的会话
def create_session_with_retry():
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Function to get soup object from a URL
def get_soup(url, max_retries=MAX_RETRIES):
    """
    获取URL内容并返回BeautifulSoup对象，带有重试和错误处理机制
    
    Args:
        url: 要抓取的网页URL
        max_retries: 最大重试次数
        
    Returns:
        BeautifulSoup对象或None（如果请求失败）
    """
    session = create_session_with_retry()
    retry_count = 0
    backoff_time = 2  # 初始等待时间，秒

    logger.debug(f"开始请求 URL: {url}")
    
    while retry_count <= max_retries:
        try:
            headers = {
                'User-Agent': get_random_user_agent(),
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0',
                'Referer': BASE_URL,  # 添加引用来源，模拟真实浏览行为
            }
            
            response = session.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
            logger.debug(f"收到 URL {url} 的响应，状态码: {response.status_code}")
            
            # 尝试自动检测编码
            detected_encoding = None
            try:
                detected_encoding = response.apparent_encoding
                response.encoding = detected_encoding
                logger.debug(f"自动检测到编码: {detected_encoding}")
            except Exception as e:
                logger.debug(f"自动检测编码失败: {str(e)}，使用默认的GBK编码")
                # 如果自动检测失败，回退到gbk
                response.encoding = 'gbk'
                
            if response.status_code == 200:
                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    return soup
                except Exception as e:
                    logger.error(f"解析 HTML 内容时出错 {url}: {str(e)}")
                    return None
            else:
                logger.warning(f"错误: 从 URL 获取到状态码 {response.status_code}: {url}")
                # 对于可重试的状态码，重试
                if response.status_code in RETRY_STATUS_CODES:
                    retry_count += 1
                    wait_time = backoff_time * (2 ** (retry_count - 1)) * (0.5 + random.random())  # 指数退避加随机抖动
                    logger.info(f"等待 {wait_time:.2f} 秒后重试 ({retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"请求 URL {url} 超时: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = backoff_time * (2 ** (retry_count - 1)) * (0.5 + random.random())
                logger.info(f"等待 {wait_time:.2f} 秒后重试超时请求 ({retry_count}/{max_retries})...")
                time.sleep(wait_time)
            else:
                logger.error(f"在 {max_retries} 次尝试后放弃超时请求 {url}")
                return None
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"连接到 URL {url} 时出错: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = backoff_time * (2 ** (retry_count - 1)) * (0.5 + random.random())
                logger.info(f"等待 {wait_time:.2f} 秒后重试连接 ({retry_count}/{max_retries})...")
                time.sleep(wait_time)
            else:
                logger.error(f"在 {max_retries} 次尝试后放弃连接 {url}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"获取 URL {url} 时出错: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = backoff_time * (2 ** (retry_count - 1)) * (0.5 + random.random())
                logger.info(f"等待 {wait_time:.2f} 秒后重试 ({retry_count}/{max_retries})...")
                time.sleep(wait_time)
            else:
                logger.error(f"在 {max_retries} 次尝试后放弃请求 {url}")
                return None
        except Exception as e:
            logger.error(f"请求 URL {url} 时发生未预期的错误: {str(e)}")
            return None
    return None

# 支持多种日期格式的解析函数
def parse_date_string(date_str):
    """
    尝试使用多种格式解析日期字符串
    
    Args:
        date_str: 日期字符串
        
    Returns:
        datetime对象或None（如果无法解析）
    """
    # 规范化日期字符串
    normalized = date_str.strip().replace('/', '-')
    
    # 尝试多种日期格式
    date_formats = [
        '%Y-%m-%d %H:%M:%S',    # 2023-01-02 10:30:45
        '%Y-%m-%d %H:%M',       # 2023-01-02 10:30
        '%Y-%m-%d',             # 2023-01-02
        '%y-%m-%d %H:%M:%S',    # 23-01-02 10:30:45
        '%y-%m-%d %H:%M',       # 23-01-02 10:30
        '%y-%m-%d',             # 23-01-02
        '%m-%d %H:%M:%S',       # 01-02 10:30:45 (当前年份)
        '%m-%d %H:%M'           # 01-02 10:30 (当前年份)
    ]
    
    # 尝试不同的格式
    for fmt in date_formats:
        try:
            dt = datetime.datetime.strptime(normalized, fmt)
            # 如果格式中没有年份，添加当前年份
            if '%y' not in fmt and '%Y' not in fmt:
                current_year = datetime.datetime.now().year
                dt = dt.replace(year=current_year)
            return dt
        except ValueError:
            continue
    
    # 如果以上格式都不匹配，尝试使用正则表达式提取
    patterns = [
        # 年-月-日 时:分:秒
        r'(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})[\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?',
        # 月-日 时:分:秒 (当前年份)
        r'(\d{1,2})[/-](\d{1,2})[\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                if len(match.groups()) >= 6:  # 年月日时分秒
                    year = int(match.group(1))
                    # 处理两位数年份
                    if year < 100:
                        year += 2000
                    month = int(match.group(2))
                    day = int(match.group(3))
                    hour = int(match.group(4))
                    minute = int(match.group(5))
                    second = int(match.group(6)) if match.group(6) else 0
                    return datetime.datetime(year, month, day, hour, minute, second)
                elif len(match.groups()) >= 5:  # 月日时分秒 (当前年份)
                    current_year = datetime.datetime.now().year
                    month = int(match.group(1))
                    day = int(match.group(2))
                    hour = int(match.group(3))
                    minute = int(match.group(4))
                    second = int(match.group(5)) if len(match.groups()) >= 5 and match.group(5) else 0
                    return datetime.datetime(current_year, month, day, hour, minute, second)
            except (ValueError, IndexError) as e:
                logger.debug(f"尝试使用正则解析日期 '{date_str}' 时出错: {e}")
                continue
    
    # 所有尝试都失败
    return None

# Function to parse post details from a board page based on new DIV structure
def parse_board_page(board_id, page_num):
    """
    解析指定板块页面上的所有帖子
    
    Args:
        board_id: 板块ID
        page_num: 页码
        
    Returns:
        包含帖子信息的列表，每个帖子为一个字典
    """
    page_url = f"{BASE_URL}index.asp?boardid={board_id}&page={page_num}"
    logger.debug(f"正在抓取 {page_url}")
    
    try:
        soup = get_soup(page_url)
        posts_data = []

        if not soup:
            logger.warning(f"未能获取 {page_url} 的页面内容")
            return posts_data

        # 查找所有包含帖子的div元素
        post_divs = soup.find_all('div', class_='list')

        if not post_divs:
            logger.warning(f"在 {page_url} 上未找到任何 <div class='list'> 元素。")
            return posts_data
        
        logger.debug(f"在 {page_url} 上找到 {len(post_divs)} 个 <div class='list'> 元素")

        for idx, post_div in enumerate(post_divs):
            try:
                title_text = ""
                post_datetime = None
                author = ""
                post_id = ""
                replies = 0
                views = 0

                # 从帖子中提取标题和帖子ID
                title_div = post_div.find('div', class_='listtitle')
                if title_div:
                    title_link = title_div.find('a', href=lambda href: href and 'dispbbs.asp' in href and 'ID=' in href)
                    if title_link:
                        title_text = title_link.get_text(strip=True)
                        
                        # 提取帖子ID
                        if 'href' in title_link.attrs:
                            id_match = re.search(r'ID=(\d+)', title_link['href'], re.IGNORECASE)
                            if id_match:
                                post_id = id_match.group(1)

                # 从帖子中提取作者
                author_div = post_div.find('div', class_='list_a')
                if author_div and author_div.find('a'):
                    author = author_div.find('a').get_text(strip=True)

                # 提取回复数和浏览量
                list_c_divs = post_div.find_all('div', class_='list_c')
                if len(list_c_divs) >= 2:
                    try:
                        replies = int(list_c_divs[0].get_text(strip=True))
                        views = int(list_c_divs[1].get_text(strip=True))
                    except (ValueError, IndexError) as e:
                        logger.debug(f"解析回复数或浏览量时出错: {str(e)}")

                # 从帖子中提取日期
                list_r1_div = post_div.find('div', class_='list_r1')
                if list_r1_div:
                    date_div = list_r1_div.find('div', class_='list_t')
                    if date_div:
                        date_link = date_div.find('a')
                        if date_link:
                            date_str_candidate = date_link.get_text(strip=True)
                            # 首先尝试使用标准正则提取日期部分
                            date_match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})', date_str_candidate)
                            if date_match:
                                parsed_date_str = date_match.group(1)
                                post_datetime = parse_date_string(parsed_date_str)
                            else:
                                # 如果标准格式不匹配，尝试直接解析整个字符串
                                post_datetime = parse_date_string(date_str_candidate)
                                
                            if post_datetime is None:
                                logger.error(f"无法解析日期字符串: '{date_str_candidate}' 在 {page_url}")
                
                if title_text and post_datetime:
                    post_data = {
                        'title': title_text,
                        'date': post_datetime,
                        'board_id': board_id,
                        'page': page_num,
                        'author': author,
                        'replies': replies,
                        'views': views,
                        'post_id': post_id
                    }
                    logger.debug(f"提取的帖子: 板块={board_id}, ID={post_id}, 标题='{title_text}', 作者='{author}', 回复数={replies}, 浏览量={views}, 日期='{post_datetime}'")
                    posts_data.append(post_data)
                else:
                    if not title_text: 
                        logger.debug(f"在 {page_url} 的第 {idx+1} 个 div.list 中缺少标题。内容: {post_div.get_text(strip=True)[:100]}")
                    if not post_datetime: 
                        logger.debug(f"在 {page_url} 的第 {idx+1} 个 div.list 中缺少日期。内容: {post_div.get_text(strip=True)[:100]}")
            except Exception as e:
                logger.error(f"处理 {page_url} 上的第 {idx+1} 个帖子时出错: {str(e)}")
                continue

        if not posts_data and page_num == 1:
            logger.info(f"使用基于div的解析逻辑从板块ID: {board_id}, 页面: 1, URL: {page_url} 未提取到任何帖子。")
        return posts_data
    except Exception as e:
        logger.error(f"解析板块 {board_id} 页面 {page_num} 时发生错误: {str(e)}")
        return []

# Function to scrape recent posts from multiple boards
def scrape_recent_posts(board_ids=TARGET_BOARD_IDS, days_limit=DAYS_LIMIT):
    """
    从多个板块抓取最近的帖子
    
    Args:
        board_ids: 要抓取的板块ID列表
        days_limit: 抓取多少天内的帖子
        
    Returns:
        包含最近帖子信息的列表
    """
    all_recent_posts = []
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_limit)
    logger.info(f"开始抓取最近 {days_limit} 天内的帖子，截止日期: {cutoff_date.strftime('%Y-%m-%d')}")

    try:
        for board_id in board_ids:
            try:
                logger.info(f"\n处理板块ID: {board_id}")
                page_had_recent_posts_ever_for_this_board = False
                
                for page_num in range(1, PAGES_PER_BOARD + 1):  # 检查每个板块的前几页
                    try:
                        logger.info(f"正在抓取板块ID: {board_id}, 页面: {page_num}")
                        posts_on_page = parse_board_page(board_id, page_num)
                        
                        # 随机化延迟，避免被检测到爬虫行为
                        delay_time = PAGE_DELAY_MIN + random.random() * (PAGE_DELAY_MAX - PAGE_DELAY_MIN)
                        logger.debug(f"等待 {delay_time:.2f} 秒...")
                        time.sleep(delay_time)
                        
                        if not posts_on_page and page_num == 1:
                            logger.info(f"在板块ID: {board_id} 的第一页未找到帖子。转到下一个板块。")
                            break 
                        if not posts_on_page:
                            logger.info(f"在板块ID: {board_id}, 页面: {page_num} 上未找到更多帖子。")
                            break

                        current_page_had_recent = False
                        oldest_post_on_page = None

                        for post in posts_on_page:
                            if oldest_post_on_page is None or post['date'] < oldest_post_on_page['date']:
                                oldest_post_on_page = post
                            
                            if post['date'] >= cutoff_date:
                                all_recent_posts.append(post)
                                current_page_had_recent = True
                                page_had_recent_posts_ever_for_this_board = True
                        
                        if oldest_post_on_page and oldest_post_on_page['date'] < cutoff_date and not current_page_had_recent:
                            logger.info(f"板块 {board_id} 页面 {page_num} 上最旧的帖子(日期: {oldest_post_on_page['date']})早于截止日期({cutoff_date.strftime('%Y-%m-%d')})且此页上没有最近的帖子。停止抓取此板块。")
                            break
                    except Exception as e:
                        logger.error(f"处理板块 {board_id} 页面 {page_num} 时出错: {str(e)}")
                        continue
                
                # 板块之间使用更长的随机延迟
                board_delay = BOARD_DELAY_MIN + random.random() * (BOARD_DELAY_MAX - BOARD_DELAY_MIN)
                logger.debug(f"在处理下一个板块前等待 {board_delay:.2f} 秒...")
                time.sleep(board_delay)
            except Exception as e:
                logger.error(f"处理板块 {board_id} 时出错: {str(e)}")
                continue
                
        logger.info(f"抓取完成，共找到 {len(all_recent_posts)} 条最近 {days_limit} 天内的帖子")
        return all_recent_posts
    except Exception as e:
        logger.critical(f"抓取过程中发生严重错误: {str(e)}")
        return all_recent_posts

if __name__ == '__main__':
    try:
        logger.info("开始使用基于用户提供的HTML样本的解析逻辑启动爬虫(v8)...")
        recent_posts = scrape_recent_posts()

        if recent_posts:
            logger.info(f"\n--- 找到 {len(recent_posts)} 条最近的帖子: ---")
            recent_posts_sorted = sorted(recent_posts, key=lambda x: x['date'], reverse=True)
            for post in recent_posts_sorted:
                logger.info(f"标题: {post['title']} | 作者: {post['author']} | 日期: {post['date'].strftime('%Y-%m-%d %H:%M:%S')} | 板块: {post['board_id']} | 回复/浏览: {post['replies']}/{post['views']}")
            
            try:
                with open(OUTPUT_FILENAME, 'w', newline='', encoding='utf-8-sig') as tsvfile:
                    fieldnames = TSV_FIELDS
                    writer = csv.DictWriter(tsvfile, fieldnames=fieldnames, delimiter='\t')
                    writer.writeheader()
                    for post_data in recent_posts_sorted:
                        post_data_tsv = post_data.copy()
                        post_data_tsv['date'] = post_data['date'].strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow(post_data_tsv)
                logger.info(f"\n结果已保存到 {OUTPUT_FILENAME}")
            except Exception as e:
                logger.error(f"保存TSV文件时出错: {str(e)}")
        else:
            logger.warning("\n使用新的解析逻辑(v8)未找到符合条件的最近帖子。")
    except KeyboardInterrupt:
        logger.info("用户中断，程序终止")
    except Exception as e:
        logger.critical(f"程序执行过程中发生未处理的异常: {str(e)}")
        import traceback
        logger.critical(traceback.format_exc())
