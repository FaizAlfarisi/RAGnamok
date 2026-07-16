import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.generator import generate_answer, _build_multimodal_prompt
from app.config import settings

async def test():
    context = {
        "texts": ["MUHAMMAD FA'IZ ALFARISI\n\n+629666070999 | faizalfarisi67@gmail.com | www.linkedin.com/in/mfaizalfarisi/ | faiz-alfarisi.vercel.app\n\nPasuruan, East Java, Indonesia\n\nFresh graduate in Mathematics with hands-on experience in applied AI and backend development."],
        "images": []
    }
    
    # First, just show the prompt that would be sent
    from app.services.prompts import SYSTEM_PROMPT
    prompt = _build_multimodal_prompt(context, "say hi", [])
    print("=== Prompt messages ===")
    for i, msg in enumerate(prompt):
        print(f"Message {i} type={type(msg).__name__}")
        if hasattr(msg, 'content'):
            c = msg.content
            if isinstance(c, list):
                for j, part in enumerate(c):
                    print(f"  Part {j}: {part.get('type', '')} = {str(part.get('text', ''))[:200]}")
            elif isinstance(c, str):
                print(f"  Content: {c[:500]}")
    
    print()
    print("=== Generating answer ===")
    start = asyncio.get_event_loop().time()
    result = await generate_answer(context, "say hi", [])
    elapsed = asyncio.get_event_loop().time() - start
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Result length: {len(result)}")
    print(f"Result: {repr(result[:500])}")

asyncio.run(test())
