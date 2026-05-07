# Host-side unit tests for the LoadCell + LoadCellController classes.
#
# Builds the production *.cpp from Firmware/STUAART/ against a tiny set
# of stubs that replace Arduino.h, HX711.h, SPI.h. The stubbed HX711 is
# programmable so tests script the next return value of read().
#
# Two test binaries :
#   - build/test_loadcell    : tests for LoadCell only
#   - build/test_controller  : tests for LoadCellController (SPIFFS-free
#                              methods only)
#
# Usage :
#   make           # build and run both
#   make build     # build only
#   make clean     # remove build/

CXX      ?= clang++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O0 -g -Wno-expansion-to-defined

PROD_DIR = ../../Firmware/STUAART
STUB_DIR = stubs

INCLUDES = -I$(STUB_DIR) -I$(PROD_DIR)

LOADCELL_SOURCES   = $(PROD_DIR)/LoadCell.cpp \
                     $(STUB_DIR)/stubs.cpp \
                     test_loadcell.cpp

CONTROLLER_SOURCES = $(PROD_DIR)/LoadCell.cpp \
                     $(PROD_DIR)/LoadCellController.cpp \
                     $(STUB_DIR)/stubs.cpp \
                     $(STUB_DIR)/spiffs_stubs.cpp \
                     test_controller.cpp

LOADCELL_BIN   = build/test_loadcell
CONTROLLER_BIN = build/test_controller

.PHONY: all build run clean

all: run

build: $(LOADCELL_BIN) $(CONTROLLER_BIN)

$(LOADCELL_BIN): $(LOADCELL_SOURCES) $(STUB_DIR)/Arduino.h $(STUB_DIR)/HX711.h $(STUB_DIR)/SPI.h
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(LOADCELL_SOURCES) -o $(LOADCELL_BIN)

$(CONTROLLER_BIN): $(CONTROLLER_SOURCES) $(STUB_DIR)/Arduino.h $(STUB_DIR)/HX711.h $(STUB_DIR)/SPI.h
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(CONTROLLER_SOURCES) -o $(CONTROLLER_BIN)

run: build
	@./$(LOADCELL_BIN)
	@echo
	@./$(CONTROLLER_BIN)

clean:
	rm -rf build
