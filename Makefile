# Prefer .env, but fall back to .env.example if .env is missing
ifeq (,$(wildcard .env))
  ifeq (,$(wildcard .env.example))
    $(error No .env or .env.example file found. Please create one.)
  else
    $(info ⚠️  Using .env.example because .env is missing.)
    ENV_FILE := .env.example
  endif
else
  ENV_FILE := .env
endif

include $(ENV_FILE)

CHECK_DIRS := .

ava-build:
	docker compose --env-file $(ENV_FILE) build

ava-run:
	docker compose --env-file $(ENV_FILE) up --build -d

ava-stop:
	docker compose --env-file $(ENV_FILE) stop

ifeq ($(OS),Windows_NT)
    RM_CMD = rmdir /s /q
else
    RM_CMD = rm -rf
endif

ava-delete:
	-$(RM_CMD) long_term_memory
	-$(RM_CMD) short_term_memory
	-$(RM_CMD) generated_images
	docker compose --env-file $(ENV_FILE) down

format-fix:
	uv run ruff format $(CHECK_DIRS) 
	uv run ruff check --select I --fix $(CHECK_DIRS)

lint-fix:
	uv run ruff check --fix $(CHECK_DIRS)

format-check:
	uv run ruff format --check $(CHECK_DIRS) 
	uv run ruff check -e $(CHECK_DIRS)
	uv run ruff check --select I -e $(CHECK_DIRS)

lint-check:
	uv run ruff check $(CHECK_DIRS)
