# Envoy Gateway Customizations

This repo contains demo-style code for using [ExternalProcessors](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/ext_proc_filter) in [`envoy`](https://www.envoyproxy.io/docs/envoy/latest/), a high-performance production ready reverse proxy. Some other examples (not mine) in `golang` can be found [here](https://github.com/google/envoy-processor-examples)

## Motivation

This approach to customizing edge functionality is interesting mainly because it is a _relatively_ low-technical-bar approach yet integrated directly into a performant reverse proxy. Basically, if someone can write `python` code and can grok the "SDK" supplied by the base class `ExternalProcessor`, they could contribute to edge functions. Deployment, at least in `kubernetes`, can follow standard practices. 

This won't be an approach as performant as [adding `envoy` filters directly in C++](https://github.com/envoyproxy/envoy-filter-example) (requiring development, testing, and maintenance of the build process), nor will it likely be competitive with [compiled WASM filters](https://www.envoyproxy.io/docs/envoy/latest/start/sandboxes/wasm-cc). However, most web computing domains have to _balance_ accessibility and performance though. Any approach to gateway actions that can reliable cost less than, say O(100ms), probably captures most of the value to most platforms. 

## Dependencies

* `docker` and `docker compose` (packaged together now)
* `python` (`^3.9`) and `poetry`
* `protobuf` and `grpc` tooling
* `buf` for building protobufs
* `make`
* `curl` (and `jq` would help too)

## Quickstart

Startup follows these steps
```shell
make codegen # runs `buf`
make up-infra # starts zookeeper, kafka, redis, and postgres
make up-targets # starts some target services
make up-extproc # starts the filters
```

You should then (in another terminal) be able to execute
```
$ curl localhost:7000/create-root-key
{"tenant":"74aebf03-5e6c-44e7-ac69-18e3fb549d07","user_id":"b1502c83-bbf3-45b3-9147-72a35c0b926d","key_id":"339d164d-3497-43f7-9020-a7f945fe96d2","created_at":"2022-05-04T05:30:47.951026+00:00","updated_at":"2022-05-04T05:30:47.951042+00:00","revoked_at":null,"status":"active","scopes":[{"resource":"keys","action":"read"},{"resource":"keys","action":"write"}],"secret":"5voli96RpraIo0S4Ka4m3fHH7uxWvbgllEjbGr9PzNQ="}
```
or 
```shell
$ curl localhost:7000/create-root-key -s | jq '"key = \(.key_id), secret = \(.secret)"'
"key = 4005ca44-fe4a-44e3-95ab-2c07f9627320, secret = gyXCUMOvmN667yPiO6BXlnmBF7yOhQ6ihMTHdh8y0Pg="
```
to create an API key, and then make calls like
```shell
$ curl localhost:8080/api/v0/echo
{"message": "Unauthenticated", "status": 401, "details": "NoCredentials One of identity or secret not passed"}
$ curl localhost:8080/api/v0/echo -u '339d164d-3497-43f7-9020-a7f945fe96d2:5voli96RpraIo0S4Ka4m3fHH7uxWvbgllEjbGr9PzNQ='
{"command": "GET", "path": "/api/v0/echo", "message": "Hello"}
```
to route requests to a naive "echo" server through the `envoy` gateway and whatever processors are running. Note in the two calls above, one fails (`401` no auth) and one succeeds _but the echo server has no authentication concept_.  

## Services

Several services make this tick, as laid out in the `docker-compose.yaml` and briefly described below. 

### Infra

To have fun here, there are several "infrastructure" services used:
* `postgres` for API key service (`auth`)
* `zookeeper` and `kafka` for logging
* `redis` for request caching/idempotency

### Echo

`echo` (in `tests/mocks/echoserver/*`) is a trival "request echoer" service to use for testing. It echos method, path, and even request headers. 

### Auth

`auth` (in `tests/mocks/auth/*`) is a bare-bones API key and token ([JWT](https://jwt.io/)) generation service. `envoy` has a JWT filter, but this is a reasonable use case and enables handling of HTTP Basic and HTTP Bearer auth in one place. 

This is written in [`fastapi`](https://fastapi.tiangolo.com/) for a bit of diversity. Not entirely awful security practices are followed with keys, in that the secrets returned to users are never persisted by this service. 

### Gateway 

`gateway` is simply a deployment of `envoy` using the config in `envoy-gateway.yaml`. 

### External Processors

The meat here is in the `ExternalProcessor` implementation(s) in `extproc/*`. There are several demo processors, each of which implements the `gRPC` spec for streaming request and response details with `envoy`. Because `envoy` processes in "phases", there is a base class that manages a version of "context" between request phases. 

Totally demo implementations are for
* `authn` (authentication) against the `auth` service (involving JWTs and `postgres`)
* `logging` via `kafka`
* `idempotency` via `redis` 

### Consumer

`consumer` (in `tests/mocks/consumer/*`) is a naive consumer for demonstrating logging. All this service does is subscribe to a `kafka` topic and read log messages published by the external processor. 
