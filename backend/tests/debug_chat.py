import asyncio, json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

async def test():
    llm = ChatOllama(
        model='qwen3.5:4b',
        base_url='http://localhost:11434',
        num_predict=128,
        top_k=10,
        top_p=0.9,
        temperature=0.7,
        num_ctx=8192,
        timeout=900,
        keep_alive='5m',
    )
    print('Calling ainvoke...')
    try:
        response = await llm.ainvoke([HumanMessage(content='say hi in one word')])
        print('Response content repr:', repr(response.content))
        print('Response type:', type(response.content).__name__)
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
