FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
COPY pytest.ini .
RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown app /data
USER app
ENV CEPES_CONFIG_DIR=/config CEPES_CACHE_DB=/data/cache.sqlite
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
