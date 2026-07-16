import asyncio, json, ollama

async def test():
    c = ollama.AsyncClient(host='http://localhost:11434')
    print('=== Direct ollama API (streaming, small model) ===')
    try:
        count = 0
        full = []
        async for chunk in await c.chat(model='qwen3.5:0.8b', messages=[{'role': 'user', 'content': 'say hi in one word'}], stream=True):
            cval = chunk.message.content
            full.append(cval or '')
            count += 1
        print(f'Chunks: {count}')
        print(f'Joined: {repr("".join(full))}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
