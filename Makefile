.PHONY: build-AssistantFunction

build-AssistantFunction:
	python3 -m pip install --upgrade --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: -r requirements-aws.txt -t "$(ARTIFACTS_DIR)"
	python3 -m pip install --upgrade --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: aiohttp cryptography requests -t "$(ARTIFACTS_DIR)"
	python3 -m pip install --upgrade --no-deps pywebpush py-vapid http-ece -t "$(ARTIFACTS_DIR)"
	cp -r app "$(ARTIFACTS_DIR)/app"
	cp config.py "$(ARTIFACTS_DIR)/config.py"
