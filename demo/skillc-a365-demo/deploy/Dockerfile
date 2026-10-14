# The hosted demo: built from the context that build_context.py stages, not from the repository root.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SKILLC_DEMO_HOSTED=1 PORT=8000
RUN pip install --no-cache-dir "z3-solver>=4.12" "pyyaml>=6.0"
WORKDIR /app
COPY app/ /app/
RUN useradd --system --uid 10001 demo
USER 10001
EXPOSE 8000
CMD ["python", "demo/skillc-a365-demo/app.py"]
