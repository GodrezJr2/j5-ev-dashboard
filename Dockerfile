FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tools/ /app/tools/
COPY web/  /app/web/

ENV CARLINKO_DATA=/data
VOLUME /data
WORKDIR /app/tools
EXPOSE 8088

# Default = the dashboard. The logger runs as a second service (see docker-compose.yml).
CMD ["python", "server.py", "8088"]
