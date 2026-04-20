import requests

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
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

json_data = {
    'type': 'position_changes_1h',
    'count': 10,
}

response = requests.post('https://api.followin.io/tag/token/recommended', headers=headers, json=json_data)

# Note: json_data will not be serialized by requests
# exactly as it was in the original request.
#data = '{"type":"position_changes_1h","count":15}'
#response = requests.post('https://api.followin.io/tag/token/recommended', headers=headers, data=data)
# Note: json_data will not be serialized by requests
# exactly as it was in the original request.
#data = '{"type":"discussion"}'
#response = requests.post('https://api.followin.io/tag/token/recommended', headers=headers, data=data)
if response.json()['code'] == 2000:
    result=[]
    data=response.json()['data']
    for id in [item['id'] for item in data['list'][:10]]:
        result.append({
            "id": id,
            "token_quote":data['token_quotes'][str(id)][0],
        })

print(result)
    
