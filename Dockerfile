FROM python:3.11-slim
WORKDIR /app
ENV QIANSCOPE_RESOURCE_ROOT=/app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY scenarios ./scenarios
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["sh", "-c", "qianscope serve --host 0.0.0.0 --port ${PORT:-8000}"]
