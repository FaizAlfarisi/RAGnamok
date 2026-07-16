import asyncio, httpx, json, sys

async def test_raw():
    """Raw httpx streaming test"""
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "qwen3.5:0.8b",
        "messages": [{"role": "user", "content": "say hi"}],
        "stream": True,
    }
    print("=== Raw httpx streaming ===")
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload) as resp:
            count = 0
            has_content = 0
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print(f"  JSON parse error at chunk {count}: {line[:100]}")
                    continue
                msg = data.get("message", {})
                c = msg.get("content", "")
                done = data.get("done", False)
                if c:
                    has_content += 1
                count += 1
                if done or count == 140:  # stop at done or 140
                    if done:
                        print(f"  Final chunk: content={repr(c)}, done={done}, done_reason={data.get('done_reason')}, eval_count={data.get('eval_count')}")
                    break
            print(f"Total chunks (including thinking): {count}")
            print(f"Non-empty content chunks: {has_content}")

    print()
    
    # Now test LangChain streaming to see raw chunks from the generator
    print("=== LangChain internal streaming (patching) ===")
    from langchain_ollama.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage
    
    llm = ChatOllama(
        model='qwen3.5:0.8b',
        base_url='http://localhost:11434',
        num_predict=128,
    )
    
    # Directly use the internal _acreate_chat_stream to see raw ollama responses
    count = 0
    has_content_count = 0
    async for stream_resp in llm._acreate_chat_stream([HumanMessage(content="say hi")], None):
        if isinstance(stream_resp, str):
            print(f"  chunk {count}: STRING: {repr(stream_resp)}")
        else:
            # It's a ChatResponse
            try:
                msg = stream_resp["message"]
                c = msg["content"] if msg else ""
                done = stream_resp.get("done", False)
                if c:
                    has_content_count += 1
                    print(f"  chunk {count}: content={repr(c)}, done={done}")
                count += 1
                if count % 20 == 0:
                    print(f"  ... at chunk {count} (all empty so far)")
                if done:
                    print(f"  Final chunk: content={repr(c)}, done={done}, done_reason={stream_resp.get('done_reason')}, eval_count={stream_resp.get('eval_count')}")
                    break
            except Exception as e:
                print(f"  chunk {count}: Error: {type(e).__name__}: {e}")
                count += 1
    print(f"Total chunks: {count}")
    print(f"Non-empty content chunks: {has_content_count}")

asyncio.run(test_raw())
