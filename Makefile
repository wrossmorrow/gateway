.DEFAULT_GOAL := help

.PHONY: format
format:
	poetry run isort .
	poetry run black .
	poetry run flake8 .

.PHONY: check-format
check-format:
	poetry run isort . --check
	poetry run black . --check
	poetry run flake8 .

.PHONY: types
types:
	poetry run mypy extproc

.PHONY: checks
checks: check-format types

.PHONY: validate
validate: format types test

.PHONY: schema-lint
schema-lint:
	buf lint

.PHONY: schema-breaking
schema-breaking:
	buf breaking --against '.git#branch=master'

.PHONY: codegen
codegen: codegen-clean codegen-gateway codegen-google codegen-validate

.PHONY: codegen-clean
codegen-clean:
	rm -rf generated

.PHONY: codegen-gateway
codegen-gateway:
	buf -v generate

.PHONY: codegen-google
codegen-google:
	buf -v generate https://github.com/googleapis/googleapis.git \
		--path google/api/field_behavior.proto \
		--path google/api/annotations.proto \
		--path google/api/http.proto \
		--path google/rpc/status.proto \
		--path google/type/money.proto \
		--path google/type/date.proto \
		--path google/rpc/code.proto

.PHONY: codegen-validate
codegen-validate:
	buf -v generate https://github.com/envoyproxy/protoc-gen-validate.git \
		--path validate/validate.proto

.PHONY: up-kafka
up-kafka: 
	docker compose up -d zookeeper kafka

.PHONY: up-postgres
up-postgres: 
	docker compose up -d postgres

.PHONY: up-redis
up-redis: 
	docker compose up -d redis

.PHONY: up-infra
up-infra: up-kafka up-redis up-postgres

.PHONY: up-targets
up-targets: 
	docker compose up -d --build auth echo consumer gateway

.PHONY: up-extproc
up-extproc: 
	docker compose up --build authn_ext_proc logging_ext_proc digest_ext_proc idemp_ext_proc

.PHONY: down
down: 
	docker compose down --volumes

.PHONY: run
run: 
	PYTHONPATH=generated/python/standardproto/ \
		poetry run python -m extproc run

.PHONY: unit-test
unit-test:
	mkdir -p test-results
	PYTHONPATH=generated/python/standardproto/ DD_TRACE_ENABLED=false \
		poetry run coverage run -m pytest -v tests/unit \
			--junitxml=test-results/junit.xml

.PHONY: integration-test
integration-test:
	PYTHONPATH=generated/python/standardproto/ DD_TRACE_ENABLED=false \
		poetry run pytest -v tests/integration

