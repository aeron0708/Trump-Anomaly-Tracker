import json
try:
    data = open('temp_chain.json', 'r', encoding='utf-16').read()
    start = data.find('{')
    if start != -1:
        j = json.loads(data[start:])
        if 'data' in j and len(j['data']) > 0:
            print("Fields in chain:", list(j['data'][0].keys()))
            print("Sample code:", j['data'][0]['code'])
except Exception as e:
    print(e)
