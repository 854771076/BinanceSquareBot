import requests

cookies = {
    'TZ': '8',
    'G': 'jIPvKoLaE6yxNmfAaHnftppSotawKqSbtxMsvFIoaGx1msr0aG-_qRfneiOt3Ieh',
    '_ga': 'GA1.1.1217072458.1776697862',
    '_ga_RDXGD4Z1XV': 'GS2.1.s1776697862$o1$g1$t1776698019$j60$l0$h0',
}

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'referer': 'https://followin.io/zh-Hans/trendingTopicList',
    'sec-ch-ua': '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0',
    # 'cookie': 'TZ=8; G=jIPvKoLaE6yxNmfAaHnftppSotawKqSbtxMsvFIoaGx1msr0aG-_qRfneiOt3Ieh; _ga=GA1.1.1217072458.1776697862; _ga_RDXGD4Z1XV=GS2.1.s1776697862$o1$g1$t1776698019$j60$l0$h0',
}

from html.parser import HTMLParser


class NextDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.next_data = None
        self.in_target_script = False

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            for name, value in attrs:
                if name == 'id' and value == '__NEXT_DATA__':
                    self.in_target_script = True
                    break

    def handle_endtag(self, tag):
        if tag == 'script' and self.in_target_script:
            self.in_target_script = False

    def handle_data(self, data):
        if self.in_target_script:
            self.next_data = data


response = requests.get('https://followin.io/zh-Hans/trendingTopic/8436', headers=headers)
response.raise_for_status()

parser = NextDataParser()
parser.feed(response.text)
next_data = parser.next_data


import json
data = json.loads(next_data)
content = data['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']['deep_ai_summariy']['summary']
print(content)
