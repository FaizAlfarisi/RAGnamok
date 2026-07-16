import httpx, json, asyncio

async def test_raw():
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "qwen3.5:0.8b",
        "messages": [{"role": "user", "content": "say hi"}],
        "stream": True,
    }
    print("Sending request...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("POST", url, json=payload) as resp:
                print(f"Status: {resp.status_code}")
                count = 0
                async for line in resp.aiter_lines():
                    if line.strip():
                        data = json.loads(line)
                        msg = data.get("message", {})
                        c = msg.get("content", "")
                        done = data.get("done", False)
                        print(f"  chunk {count}: content={repr(c)}, done={done}")
                        count += 1
                        if done:
                            print(f"  eval_count: {data.get('eval_count')}")
                            break
                print(f"Total chunks: {count}")
    except httpx.TimeoutException:
        print("Timeout!")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_raw())
