import ollama, json

c = ollama.Client(host='http://localhost:11434')
print('=== Sync ollama API (streaming) ===')
try:
    content_parts = []
    for chunk in c.chat(model='qwen3.5:0.8b', messages=[{'role': 'user', 'content': 'say hi in one word'}], stream=True):
        cval = chunk.message.content
        content_parts.append(cval or '')
    print(f'Joined: {repr("".join(content_parts))}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()

print()
print('=== Sync ollama API (non-streaming) ===')
try:
    resp = c.chat(model='qwen3.5:0.8b', messages=[{'role': 'user', 'content': 'say hi in one word'}], stream=False)
    print(f'Content: {repr(resp.message.content)}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
