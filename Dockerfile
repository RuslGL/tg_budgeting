FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && \
    curl -fsSL https://reestr.digital.gov.ru/upload/ca/russian_trusted_root_ca.cer \
      -o /usr/local/share/ca-certificates/russian_trusted_root_ca.crt && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "import certifi; open(certifi.where(), 'ab').write(open('/etc/ssl/certs/russian_trusted_root_ca.pem','rb').read())" 2>/dev/null || true

COPY . .

CMD ["python", "-m", "bot.main"]
