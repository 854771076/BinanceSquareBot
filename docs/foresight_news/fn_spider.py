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
    # def fetch_data(self,pagesize=10) -> List[Dict]:
    #     """
    #     爬取ForesightNews数据
        
    #     :return: 爬取到的新闻数据列表
    #     """
    #     logger.info(f"开始爬取ForesightNews: {self.url}")
    #     date_str=datetime.now().date().strftime("%Y%m%d")
    #     api_url=f'https://api.foresightnews.pro/v1/dayNews?is_important=true&date={date_str}'
    #     try:
    #         response = requests.get(api_url, headers={'User-Agent': self.user_agent.random},impersonate='chrome')
    #         response.raise_for_status()  # 检查请求是否成功
    #         base64_str=response.json().get('data')
    #         if base64_str:
    #             decoded_bytes = base64.b64decode(base64_str)
    #             decompressed_data = zlib.decompress(decoded_bytes)
    #             json_data = json.loads(decompressed_data)
    #             news=[]
    #             if json_data:
    #                 for item in json_data[0].get('news',[])[:pagesize]:
    #                     news.append({
    #                         'id':item.get('source_link'),
    #                         'title':item.get('title'),
    #                         'url':item.get('source_link'),
    #                         'source':self.source,
    #                         'pub_time':datetime.fromtimestamp(item.get('published_at')).strftime("%Y-%m-%d %H:%M:%S")
    #                     })
    #             else:
    #                 logger.warning(f"ForesightNews API返回空新闻列表,{response.text}")
    #         else:
    #             raise ValueError(f"ForesightNews API返回空数据,{response.text}")
    #         return news
    #     except Exception as e:
    #         logger.error(f"爬取ForesightNews失败: {e}")
    #         return []
    # 获取日历一小时一次，一次2条,link去重
    def get_calendar(self,pagesize=10):
        """获取日历"""
        date=datetime.now().date().strftime("%Y%m%d")
        url = f"https://api.foresightnews.pro/v1/calendars?week_date={date}"
        response = requests.get(url,impersonate='chrome')
        response.raise_for_status()  # 检查请求是否成功
        base64_str=response.json().get('data')
        if base64_str:
            decoded_bytes = base64.b64decode(base64_str)
            decompressed_data = zlib.decompress(decoded_bytes)
            json_data = json.loads(decompressed_data)
            for item in json_data[:pagesize]:
                print(item)
                # {'start_time': 1777075200, 'end_time': 1777075200, 'title': 'TRUMP 代币团队将于 4 月 25 日在佛罗里达州棕榈滩海湖庄园举办加密与商业峰会 暨宴会', 'description': 'TRUMP 代币团队将于 4 月 25 日在佛罗里达州棕榈滩海湖庄园举办加密与商业峰会暨宴会，特朗普将出席并担任主旨演讲嘉 宾，泰森也将出席该宴会并发表演讲。此次活动采用排行榜机制，持仓积分排名前 297 位的合格参与者将获得出席资格。其中排名前 29 位的 VIP 用户 还将额外享有与特朗普及其他嘉宾的专属招待会和 VIP 前排座席。', 'link': 'https://foresightnews.pro/news/detail/101178', 'cate': 4}  
    
    # 获取日历一小时一次，一次2条，id去重
    def get_airdrops(self,pagesize=2):
        """获取空投事件"""
        date=datetime.now().date().strftime("%Y%m%d")
        url = f"https://api.foresightnews.pro/v1/airdropEvent?week_date={date}"
        response = requests.get(url,impersonate='chrome')
        response.raise_for_status()  # 检查请求是否成功
        base64_str=response.json().get('data')
        if base64_str:
            decoded_bytes = base64.b64decode(base64_str)
            decompressed_data = zlib.decompress(decoded_bytes)
            json_data = json.loads(decompressed_data)['airdrop_timeline_items']
            for item in json_data[:pagesize]:
                print(item)
        #         {
        #     "id": 73249,
        #     "event_id": 235,
        #     "source_type": "news",
        #     "source_id": 102294,
        #     "img": "",
        #     "published_at": 1776495039,
        #     "news": {
        #         "id": 102294,
        #         "title": "Bitget IPO Prime 首期项目 preSPAX 已开放认购",
        #         "brief": "Bitget IPO Prime 首期项目 preSPAX 已开放认购，投入时间截止 4 月 21 日 14:00。代币分配阶段将于 4 月 21 日 14:00 至 18:00 进行；现货交易将于 4 月 21 日 20:00 开启。更多详情可参阅 Bitget 官方平台。",
        #         "content": "<p>Foresight News 消息，Bitget IPO Prime 首期项目 preSPAX 已开放认购，投入时间截止 4 月 21 日 14:00。代币分配阶段将于 4 月 21 日 14:00 至 18:00 进行；现货交易将于 4 月 21 日 20:00 开启。更多详情可参阅 Bitget 官方平台。</p>",
        #         "img": "",
        #         "tags": [],
        #         "is_important": True,
        #         "important_tag": None,
        #         "label": "重要消息",
        #         "source_link": "https://www.bitget.cloud/zh-CN/support/articles/12560603882368",
        #         "published_at": 1776495039,
        #         "favorited": False,
        #         "wikis": None,
        #         "new_wikis": [
        #             {
        #                 "id": 19964,
        #                 "wiki_type": "wiki",
        #                 "name": "Bitget",
        #                 "logo": "https://img.foresightnews.pro/202507/842-1752637682062.png",
        #                 "title": "",
        #                 "brief": "Bitget 是全球领先的加密交易平台，提供现货、衍生品和跟单交易服务。",
        #                 "website": "https://www.bitget.com/en/",
        #                 "twitter": "https://twitter.com/bitgetglobal",
        #                 "discord": "",
        #                 "medium": "",
        #                 "linkedin": "",
        #                 "telegram": "",
        #                 "galxe": "https://galxe.com/Bitget",
        #                 "galxe_has_active_task": True,
        #                 "hot_index": 0,
        #                 "status": "published",
        #                 "wiki": None,
        #                 "members": None,
        #                 "investors": None,
        #                 "portfolios": None,
        #                 "tags": None,
        #                 "chains": None,
        #                 "news": None,
        #                 "article": None,
        #                 "fundRaising": None,
        #                 "is_official": False,
        #                 "symbol": "BGB",
        #                 "price": "1.8885",
        #                 "change24h": "0.00725",
        #                 "token_address": ""
        #             }
        #         ]
        #     }
        # }

    # 一小时一次，一次2条，id去重
    def get_fundraising(self,pagesize=2):
        """获取众筹事件"""


        params = {
            'page': '1',
            'size': str(pagesize),
            # 'search': '',
            # 'sort_by': '',
            # 'sort': '',
            # 'min_amount': '',
            # 'max_amount': '',
            # 'round': '',
            # 'start_time': '1760808152',
            # 'end_time': '1776705752',
        }

        response = requests.get('https://api.foresightnews.pro/v1/fundraising', params=params,impersonate='chrome')
        response.raise_for_status()  # 检查请求是否成功
        base64_str=response.json().get('data').get('list')

        if base64_str:
            decoded_bytes = base64.b64decode(base64_str)
            decompressed_data = zlib.decompress(decoded_bytes)
            json_data = json.loads(decompressed_data)
        # print(len(json_data))
        for item in json_data:
            print(item)
        # {'id': 6818, 'wiki': {'id': 27190, 'wiki_type': 'wiki', 'name': 'Pumpcade', 'logo': 'https://img.foresightnews.pro/202604/842-1775539346493.png', 'title': '', 'brief': 'Pumpcade 是主打直播内嵌 60 秒超短期预测 / 微投注的 Web3 基础设施平台，支持实时赛事与加密资产等预测， 由官方 API 自动结算无对手方风险。', 'website': 'https://cade.market', 'twitter': 'https://x.com/pumpcade', 'discord': '', 'medium': '', 'linkedin': '', 'galxe': '', 'galxe_has_active_task': False, 'hot_index': 0, 'status': 'published', 'symbol': '', 'wiki': None}, 'date': 1776391500, 'amount': 500, 'round': 3, 'round_str': 'Seed', 'memo': '', 'new_wiki': {'id': 27190, 'wiki_type': 'wiki', 'name': 'Pumpcade', 'logo': 'https://img.foresightnews.pro/202604/842-1775539346493.png', 'title': '', 'brief': 'Pumpcade 是主打直播内嵌 60 秒超短期预测 / 微投注的 Web3 基础设施平台，支持实时赛事与加密资产等预测，由官方 API 自动结算无对手方风险。', 'website': 'https://cade.market', 'twitter': 'https://x.com/pumpcade', 'discord': '', 'medium': '', 'linkedin': '', 'telegram': '', 'galxe': '', 'galxe_has_active_task': False, 'hot_index': 0, 'status': 'published', 'wiki': None, 'members': None, 'investors': None, 'portfolios': None, 'tags': None, 'chains': None, 'news': None, 'article': None, 'fundRaising': None, 'is_official': False, 'symbol': '', 'price': '', 'change24h': '', 'token_address': ''}, 'lead_investors': None, 'fund_raising_investors': [{'id': 32779, 'wiki': {'id': 1321, 'wiki_type': 'vc', 'name': 'Foundation Capital', 'logo': 'https://img.foresightnews.pro/202208/d19914ea151a069a7dccfcc4121d74b9.jpeg', 'title': '', 'brief': 'Foundation Capital 成立于 1995 年，作为一家早期风险投资公司，我们的金融科技、企业和消费者投资重塑了行业并定义了新市场。', 'website': 'http://foundationcapital.com/', 'twitter': 'https://twitter.com/FoundationCap', 'discord': '', 'medium': '', 'linkedin': 'https://linkedin.com/company/foundation-capital', 'galxe': '', 'galxe_has_active_task': False, 'hot_index': 0, 'status': 'published', 'symbol': '', 'wiki': None}, 'new_wiki': {'id': 1321, 'wiki_type': 'wiki', 'name': 'Foundation Capital', 'logo': 'https://img.foresightnews.pro/202208/d19914ea151a069a7dccfcc4121d74b9.jpeg', 'title': '', 'brief': 'Foundation Capital 成立于 1995 年，作为一家早期风险投资公司，我们的金融科技、企 业和消费者投资重塑了行业并定义了新市场。', 'website': 'http://foundationcapital.com/', 'twitter': 'https://twitter.com/FoundationCap', 'discord': '', 'medium': '', 'linkedin': 'https://linkedin.com/company/foundation-capital', 'telegram': '', 'galxe': '', 'galxe_has_active_task': False, 'hot_index': 0, 'status': 'published', 'wiki': None, 'members': None, 'investors': None, 'portfolios': None, 'tags': None, 'chains': None, 'news': None, 'article': None, 'fundRaising': None, 'is_official': False, 'symbol': '', 'price': '', 'change24h': '', 'token_address': ''}, 'fund_raising_id': 6818, 'index': 1}, {'id': 32780, 'wiki': {'id': 3788, 'wiki_type': 'vc', 'name': 'Jump Crypto', 'logo': 'https://img.foresightnews.pro/202208/9-1660630766076.png', 'title': '', 'brief': 'Jump Crypto 是建设者、合作伙伴和交易 者，对加密货币的前景持长期观点，并致力于释放开放的、社区驱动的网络的全部潜力。', 'website': 'https://jumpcrypto.com/', 'twitter': 'https://twitter.com/JumpCryptoHQ', 'discord': '', 'medium': '', 'linkedin': 'https://www.linkedin.com/company/jump-crypto/', 'galxe': '', 'galxe_has_active_task': False, 'hot_index': 20, 'status': 'published', 'symbol': '', 'wiki': None}, 'new_wiki': {'id': 3788, 'wiki_type': 'wiki', 'name': 'Jump Crypto', 'logo': 'https://img.foresightnews.pro/202208/9-1660630766076.png', 'title': '', 'brief': 'Jump Crypto 是建设者、合作伙伴和交易者，对加密货币的前景持长期观点，并致力于释放开放的、社区驱动的网络的全部潜力。', 'website': 'https://jumpcrypto.com/', 'twitter': 'https://twitter.com/JumpCryptoHQ', 'discord': '', 'medium': '', 'linkedin': 'https://www.linkedin.com/company/jump-crypto/', 'telegram': '', 'galxe': '', 'galxe_has_active_task': False, 'hot_index': 0, 'status': 'published', 'wiki': None, 'members': None, 'investors': None, 'portfolios': None, 'tags': None, 'chains': None, 'news': None, 'article': None, 'fundRaising': None, 'is_official': False, 'symbol': '', 'price': '', 'change24h': '', 'token_address': ''}, 'fund_raising_id': 6818, 'index': 2}], 'tags': None}

if __name__ == "__main__":
    spider = ForesightNewsSpider()
    # spider.fetch_data()
    spider.get_fundraising()
