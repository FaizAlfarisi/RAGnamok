FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m -u 1000 appuser \
 && mkdir -p .streamlit \
 && printf '[theme]\nbase = "light"\nprimaryColor = "#5B7B6A"\nbackgroundColor = "#F1F0EC"\nsecondaryBackgroundColor = "#F9F8F6"\ntextColor = "#1C1A17"\nfont = "sans serif"\n\n[server]\nmaxUploadSize = 50\n\n[browser]\ngatherUsageStats = false\n' > .streamlit/config.toml

USER appuser

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
