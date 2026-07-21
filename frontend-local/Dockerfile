FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m -u 1000 appuser \
 && mkdir -p .streamlit \
 && printf '[theme]\nbase = "dark"\nprimaryColor = "#7BAF8A"\nbackgroundColor = "#1A1A1A"\nsecondaryBackgroundColor = "#2A2A2A"\ntextColor = "#E8E6E3"\nfont = "sans serif"\n\n[server]\nmaxUploadSize = 50\n\n[browser]\ngatherUsageStats = false\n' > .streamlit/config.toml

USER appuser

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
