import asyncio, httpx, json
from langchain_ollama.chat_models import ChatOllama
from langchain_core.messages import HumanMessage

async def test_lc_streaming():
    """Test LangChain chat with streaming to see what chunks look like."""
    llm = ChatOllama(
        model='qwen3.5:0.8b',
        base_url='http://localhost:11434',
        num_predict=128,
    )
    # Use the streaming interface to see raw chunks
    print("=== LangChain streaming chunks ===")
    full_content = ""
    chunk_count = 0
    async for chunk in llm.astream([HumanMessage(content="say hi in one word")]):
        content = chunk.content
        if content:
            full_content += content
        chunk_count += 1
        if chunk_count <= 5 or content:  # show first 5 empty chunks + all non-empty
            print(f"  chunk {chunk_count}: content={repr(content)}")
    print(f"Total chunks: {chunk_count}")
    print(f"Full content: {repr(full_content)}")

    print()
    print("=== LangChain ainvoke ===")
    response = await llm.ainvoke([HumanMessage(content="say hi in one word")])
    print(f"Response content: {repr(response.content)}")

asyncio.run(test_lc_streaming())
