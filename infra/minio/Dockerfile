FROM golang:1.24-bookworm AS build
WORKDIR /src
# Official RELEASE.2025-09-07T16-13-09Z, pinned to its signed release commit.
RUN git init . && git remote add origin https://github.com/minio/minio.git && \
    git fetch --depth 1 origin 07c3a429bfed433e49018cb0f78a52145d4bedeb && \
    git checkout --detach FETCH_HEAD
RUN CGO_ENABLED=0 go build -p 2 -trimpath -o /out/minio .

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /usr/share/doc/minio/LICENSE
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="07c3a429bfed433e49018cb0f78a52145d4bedeb"
EXPOSE 9000 9001
ENTRYPOINT ["/usr/local/bin/minio"]
