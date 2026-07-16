import asyncio
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

async def test():
    # Try with streaming=False
    llm = ChatOllama(
        model='qwen3.5:0.8b',
        base_url='http://localhost:11434',
        stream=False,  # explicitly disable streaming
        num_predict=128,
    )
    print('Calling ainvoke with stream=False...')
    try:
        response = await llm.ainvoke([HumanMessage(content='say hi in one word')])
        print('Response content repr:', repr(response.content))
        print('Response type:', type(response.content).__name__)
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
