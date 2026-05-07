# Host-side unit tests for the LoadCell class.
#
# Builds the production LoadCell.cpp (from Firmware/STUAART/) against a
# tiny set of stubs that replace Arduino.h, HX711.h, SPI.h. The stubbed
# HX711 is programmable so tests script the next return value of read().
#
# Usage :
#   make           # build and run
#   make build     # build only
#   make clean     # remove build artefacts

CXX      ?= clang++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O0 -g

PROD_DIR = ../../Firmware/STUAART
STUB_DIR = stubs

INCLUDES = -I$(STUB_DIR) -I$(PROD_DIR)

SOURCES  = $(PROD_DIR)/LoadCell.cpp \
           $(STUB_DIR)/stubs.cpp \
           test_loadcell.cpp

BIN      = build/test_loadcell

.PHONY: all build run clean

all: run

build: $(BIN)

$(BIN): $(SOURCES) $(STUB_DIR)/Arduino.h $(STUB_DIR)/HX711.h $(STUB_DIR)/SPI.h
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) -o $(BIN)

run: build
	@./$(BIN)

clean:
	rm -rf build
