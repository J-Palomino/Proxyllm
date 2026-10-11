FROM postgres:16-alpine

RUN apk add --no-cache curl ca-certificates && \
    curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

WORKDIR /app
COPY backup.sh ./backup.sh
RUN chmod +x backup.sh

CMD ["./backup.sh"]
