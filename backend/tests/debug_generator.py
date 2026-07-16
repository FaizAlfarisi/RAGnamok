import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.generator import generate_answer
from app.config import settings

async def test():
    context = {
        "texts": ["Muhammad Fa'iz Alfarisi is a fresh graduate in Mathematics with experience in AI and backend development."],
        "images": []
    }
    print(f"Model: {settings.generation_model}")
    print(f"Temperature: {settings.generation_temperature}")
    print(f"Ollama URL: {settings.ollama_base_url}")
    print()
    print("=== Testing generate_answer ===")
    start = asyncio.get_event_loop().time()
    result = await generate_answer(context, "say hi", [])
    elapsed = asyncio.get_event_loop().time() - start
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Result length: {len(result)}")
    print(f"Result: {repr(result[:500])}")

asyncio.run(test())
