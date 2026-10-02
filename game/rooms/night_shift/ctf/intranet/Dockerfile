# Kestrel Intranet: Night Shift's CTF challenge (PLAN.md Section 10, ADR-0018).
# Built by the platform from this directory alone. The flag arrives at run
# time in $FLAG (per session); none is baked into the image.
FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
COPY templates ./templates
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /intranet .

FROM scratch
COPY --from=build /intranet /intranet
USER 65534:65534
EXPOSE 8080
ENTRYPOINT ["/intranet"]
