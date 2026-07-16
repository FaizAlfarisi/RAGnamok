import asyncio
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

async def test():
    print('Testing qwen3.5:4b...')
    start = asyncio.get_event_loop().time()
    llm = ChatOllama(
        model='qwen3.5:4b',
        base_url='http://localhost:11434',
        temperature=0.1,
    )
    try:
        resp = await llm.ainvoke([HumanMessage(content='say hi in one word')])
        elapsed = asyncio.get_event_loop().time() - start
        print(f'Elapsed: {elapsed:.1f}s')
        print(f'Content: {repr(resp.content)}')
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start
        print(f'Error after {elapsed:.1f}s: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
