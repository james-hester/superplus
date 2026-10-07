BUILD ?= Build
MPW_SHELL ?= mpw-shell
PYTHON ?= python3
TARGET ?= MacPlus-v3.rebuilt.bin

.PHONY: all build native prepare verify test clean

all: build

build: prepare
	$(MAKE) native

native:
	cd "$(BUILD)" && mpw Make -f MPW/ROM.make "$(TARGET)" > ROM.commands
	cd "$(BUILD)" && $(MPW_SHELL) < ROM.commands

prepare:
	$(PYTHON) Tools/stage.py "$(BUILD)"

all verify:
	cd "$(BUILD)" && shasum -a 256 -c "$(CURDIR)/ROM/MacPlus-v3.sha256"

test:
	$(PYTHON) -m unittest discover -s Tools -p 'test_*.py'

clean:
	rm -rf "$(BUILD)"
