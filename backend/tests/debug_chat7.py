import httpx, json, asyncio

async def test():
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "qwen3.5:0.8b",
        "messages": [{"role": "user", "content": "say hi in one word"}],
        "stream": False,
    }
    print("Sending non-streaming request...")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            print(f"Status: {resp.status_code}")
            data = resp.json()
            msg = data.get("message", {})
            c = msg.get("content", "")
            print(f"Content repr: {repr(c)}")
            print(f"Done: {data.get('done')}")
            print(f"Done reason: {data.get('done_reason')}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
