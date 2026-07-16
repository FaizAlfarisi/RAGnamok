import asyncio, httpx, json

async def test():
    url = 'http://localhost:8000/api/v1/chat/sessions/201aa35c-8a4b-4882-89e1-6241dd18db25/messages'
    payload = {'query': 'say hi', 'top_k': 1}
    
    print('Calling backend...')
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=600) as cl:
            resp = await cl.post(url, json=payload)
            elapsed = asyncio.get_event_loop().time() - start
            print(f'Status: {resp.status_code}, elapsed: {elapsed:.1f}s')
            data = resp.json()
            print(f'Full response keys: {list(data.keys())}')
            for k, v in data.items():
                if isinstance(v, str):
                    print(f'  {k}: {repr(v[:500])}')
                else:
                    print(f'  {k}: {v}')
            print(f'answer length: {len(data.get("answer", ""))}')
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start
        print(f'Error after {elapsed:.1f}s: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
