from typing import List, Dict
import json
import zlib
from datetime import datetime
import base64
from fake_useragent import UserAgent
from curl_cffi import requests
class ForesightNewsSpider():
    """
    ForesightNews爬虫适配器
    """
    name='foresight_news'
    def __init__(self, config: Dict = None):
        """
        初始化ForesightNews爬虫
        """
        self.url = self.config.get("url")
        if not self.url:
             self.url = config_loader.get_config("spiders", "foresight_news").get("url")
        self.source = "foresightnews"
        self.user_agent = UserAgent()
    
    def fetch_data(self) -> List[Dict]:
        """
        爬取ForesightNews数据
        
        :return: 爬取到的新闻数据列表
        """
        logger.info(f"开始爬取ForesightNews: {self.url}")
        date_str=datetime.now().date().strftime("%Y%m%d")
        api_url=f'https://api.foresightnews.pro/v1/dayNews?is_important=true&date={date_str}'
        try:
            response = requests.get(api_url, headers={'User-Agent': self.user_agent.random},impersonate='chrome')
            response.raise_for_status()  # 检查请求是否成功
            base64_str=response.json().get('data')
            if base64_str:
                decoded_bytes = base64.b64decode(base64_str)
                decompressed_data = zlib.decompress(decoded_bytes)
                json_data = json.loads(decompressed_data)
                news=[]
                if json_data:
                    for item in json_data[0].get('news',[]):
                        news.append({
                            'id':item.get('source_link'),
                            'title':item.get('title'),
                            'url':item.get('source_link'),
                            'source':self.source,
                            'pub_time':datetime.fromtimestamp(item.get('published_at')).strftime("%Y-%m-%d %H:%M:%S")
                        })
                else:
                    logger.warning(f"ForesightNews API返回空新闻列表,{response.text}")
            else:
                raise ValueError(f"ForesightNews API返回空数据,{response.text}")
            return news
        except Exception as e:
            logger.error(f"爬取ForesightNews失败: {e}")
            return []
"""
ForesightNews API SDK
逆向工程 by URL Analyzer SDK Generator

解密算法:
  1. 响应中的 data 字段是 base64 编码的 zlib 压缩数据
  2. base64 解码 -> zlib 解压 -> 得到原始 JSON 数据
"""

import base64
import zlib
import json
from typing import Dict, Any, Optional

from curl_cffi import requests


class ForesightNewsAPI:
    """ForesightNews API 客户端"""

    def __init__(self, base_url: str = "https://api.foresightnews.pro"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Referer': 'https://foresightnews.pro/',
            'Origin': 'https://foresightnews.pro',
            'Accept': 'application/json, text/plain, */*',
        })

    def _decompress_data(self, compressed_data: str) -> Dict[str, Any]:
        """解压缩数据"""
        # 补全padding
        padding = 4 - len(compressed_data) % 4
        if padding:
            compressed_data += '=' * padding

        # base64解码
        decoded = base64.b64decode(compressed_data)

        # zlib解压
        decompressed = zlib.decompress(decoded)

        # 解析JSON
        return json.loads(decompressed.decode('utf-8'))

    def get_news_detail(self, news_id: int) -> Dict[str, Any]:
        """获取文章详情

        Args:
            news_id: 文章ID

        Returns:
            文章详情JSON
        """
        url = f"{self.base_url}/v1/news/{news_id}"
        resp = self.session.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get('code') == 1 and isinstance(data.get('data'), str):
            # 解压缩数据
            decompressed = self._decompress_data(data['data'])
            return {
                'code': data['code'],
                'msg': data.get('msg'),
                'data': decompressed
            }

        return data

    def get_activity_list(self, page: int = 1, size: int = 10,
                           start_time: Optional[int] = None,
                           end_time: Optional[int] = None) -> Dict[str, Any]:
        """获取活动列表"""
        url = f"{self.base_url}/v1/activities"
        params = {
            'page': page,
            'size': size,
        }
        if start_time:
            params['start_time'] = start_time
        if end_time:
            params['end_time'] = end_time

        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_hot_search(self, page: int = 1, size: int = 100) -> Dict[str, Any]:
        """获取热门搜索"""
        url = f"{self.base_url}/v1/search/hot"
        params = {'page': page, 'size': size}
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_feed(self, page: int = 1, size: int = 30) -> Dict[str, Any]:
        """获取信息流"""
        url = f"{self.base_url}/v2/feed"
        params = {'page': page, 'size': size}
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get('code') == 1 and isinstance(data.get('data'), str):
            decompressed = self._decompress_data(data['data'])
            return {
                'code': data['code'],
                'msg': data.get('msg'),
                'data': decompressed
            }

        return data


# 示例使用
if __name__ == '__main__':
    import json
    api = ForesightNewsAPI()

    # 加载从浏览器捕获的cookies
    # with open('../../../capture-data/cookies.json', 'r') as f:
    #     cookies = json.load(f)
    # for cookie in cookies:
    #     api.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    # 获取文章详情测试
    result = api.get_news_detail(101916)
    print(f"文章标题: {result['data']['title']}")
    print(f"文章简介: {result['data']['brief'][:100]}...")
    print(f"文章ID: {result['data']['id']}")
    print(f"发布时间: {result['data']['published_at']}")
