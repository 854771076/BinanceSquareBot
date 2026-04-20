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
        self.user_agent = UserAgent()
    
    
    # 一小时一次，一次2条，id去重
    def fetch_data(self,pagesize=10) -> List[Dict]:
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
                    for item in json_data[0].get('news',[])[:pagesize]:
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
    # 获取日历
    def get_calendar(self,pagesize=10):
        """获取日历"""
        date=datetime.now().date().strftime("%Y%m%d")
        url = f"https://api.foresightnews.pro/v2/todayInHistory?week_date={date}"
        response = requests.get(url,impersonate='chrome')
        response.raise_for_status()  # 检查请求是否成功
        base64_str=response.json().get('data')
        if base64_str:
            decoded_bytes = base64.b64decode(base64_str)
            decompressed_data = zlib.decompress(decoded_bytes)
            json_data = json.loads(decompressed_data)
            print(json_data)
    
if __name__ == "__main__":
    spider = ForesightNewsSpider()
    # spider.fetch_data()
    spider.get_calendar()
