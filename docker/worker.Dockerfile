FROM python:3.11-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39

# Only public policy code and arithmetic primitives. No evaluator, generator,
# records, artifacts, configuration, credentials or host directory is copied.
WORKDIR /app
COPY src/genesis_fintech/__init__.py /app/src/genesis_fintech/__init__.py
COPY src/genesis_fintech/domain/ /app/src/genesis_fintech/domain/
COPY src/genesis_fintech/policies/ /app/src/genesis_fintech/policies/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
USER 65534:65534
ENTRYPOINT ["python", "-I", "-S", "-u", "/app/src/genesis_fintech/policies/worker.py"]
CMD ["reconciliation"]
