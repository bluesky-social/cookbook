
SHELL = /bin/bash
.SHELLFLAGS = -o pipefail -c

.PHONY: help
help: ## Print info about all commands
	@echo "Commands:"
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[01;32m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: build-all
build-all: ## Run build for all examples
	cd go-repo-export; go build ./...

.PHONY: test-all
test-all: ## Run tests for all examples
	cd go-repo-export; ./test.sh

.PHONY: lint-all
lint-all: ## Verify code style for all examples
	cd go-repo-export; go vet ./... && test -z $(gofmt -l ./...)

.PHONY: fmt-all
fmt-all: ## Run syntax re-formatting (modify in place)
	cd go-repo-export; go fmt ./...
