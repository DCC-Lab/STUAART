#pragma once
#include <ArduinoLog.h>

void printPrefix(Print* _logOutput, int logLevel);

void printTimestamp(Print* _logOutput);

void printLogLevel(Print* _logOutput, int logLevel);

void printSuffix(Print* _logOutput, int logLevel);
