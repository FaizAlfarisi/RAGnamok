import asyncio
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

async def check_num_predict():
    # Check LangChain's default num_predict
    import inspect
    from langchain_ollama.chat_models import ChatOllama as CO
    sig = inspect.signature(CO.__init__)
    for name, param in sig.parameters.items():
        if 'num_predict' in name:
            print(f"Field '{name}': default={param.default}")
    # Also check the field definition
    print(f"num_predict field default: {CO.model_fields['num_predict'].default}")
    print()

    # Test 1: No num_predict limit
    print("=== Test 1: no num_predict (default LangChain) ===")
    llm1 = ChatOllama(
        model='qwen3.5:0.8b',
        base_url='http://localhost:11434',
    )
    try:
        resp1 = await llm1.ainvoke([HumanMessage(content='say hi')])
        print(f"Content: {repr(resp1.content)}")
    except Exception as e:
        print(f"Error: {e}")

    print()

    # Test 2: With num_predict=2048
    print("=== Test 2: num_predict=2048 ===")
    llm2 = ChatOllama(
        model='qwen3.5:0.8b',
        base_url='http://localhost:11434',
        num_predict=2048,
    )
    try:
        resp2 = await llm2.ainvoke([HumanMessage(content='say hi')])
        print(f"Content: {repr(resp2.content)}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(check_num_predict())
