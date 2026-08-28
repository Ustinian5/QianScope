FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY scenarios ./scenarios
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["sh", "-c", "echo-swm serve --host 0.0.0.0 --port ${PORT:-8000}"]
