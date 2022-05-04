#!/bin/bash

# create a root key, get .key_id and .secret from the response
# to use with basic auth
curl localhost:7000/create-root-key

# get a token from basic auth, get .token from the response
curl -u "${KEY_ID}:${SECRET}" localhost:7000/api/v0/tokens

# should also work
curl -H "authorization: bearer ${TOKEN}" localhost:7000/api/v0/tokens
curl -H "authorization: bearer ${TOKEN}" localhost:7000/api/v0/keys/${KEY_ID}

# check a generic request
curl -u "${KEY_ID}:${SECRET}" localhost:8080/api/v0/resource \
    -vvv 

# check idempotency (repeat, look for x-gateway-cached header)
curl -u "${KEY_ID}:${SECRET}" localhost:8080/api/v0/resource \
    -X POST -H 'content-type: application/json' -d '{"empty":"body"}' \
    -vvv 
