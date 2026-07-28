import urllib.request
import json

# Fetch DSR API
req = urllib.request.Request('http://127.0.0.1:8771/api/dsr')
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))

print(f"Total: {data['total']}")
if data['dsr_data']:
    first = data['dsr_data'][0]
    print("Keys:")
    for k, v in first.items():
        print(f"  '{k}' = {v}")
