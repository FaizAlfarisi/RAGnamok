import ollama, json

try:
    c = ollama.Client(host='http://localhost:11434')
    models = c.list()
    print(json.dumps(models, indent=2, default=str)[:2000])
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
