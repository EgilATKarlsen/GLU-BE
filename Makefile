.PHONY: venv

venv:
	uv venv
	echo "\nexport PYTHONPATH=$(shell pwd)" >> .venv/bin/activate 