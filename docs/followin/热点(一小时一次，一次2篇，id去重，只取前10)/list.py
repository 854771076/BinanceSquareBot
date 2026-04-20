import requests

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'cache-control': 'no-cache',
    # Already added when you pass json=
    # 'content-type': 'application/json',
    'origin': 'https://followin.io',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://followin.io/',
    'sec-ch-ua': '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0',
    'x-bparam': '{"a":"web","b":"Windows","c":"zh-Hans","d":8,"e":"","f":"","g":"","h":"3.4.0","i":"official"}',
    'x-gtoken': 'jIPvKoLaE6yxNmfAaHnftppSotawKqSbtxMsvFIoaGx1msr0aG-_qRfneiOt3Ieh',
    'x-token': 'null',
}

json_data = {}

response = requests.post('https://api.followin.io/trending_topic/ranks', headers=headers, json=json_data)
response.raise_for_status()
if response.json()['code'] == 2000:
    ids=[item['id'] for item in response.json()['data']['list'][0]['topics'][:10]]
    print(ids) # 最新趋势话题
