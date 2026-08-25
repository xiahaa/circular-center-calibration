# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)

project(circular_center_calibration VERSION 0.1.0 LANGUAGES CXX)

option(CCC_BUILD_TESTS "Build numerical regression tests" ON)
option(CCC_BUILD_EXAMPLES "Build the minimal C++ example" ON)
option(CCC_BUILD_PCL_BASELINE "Build the optional PCL SACMODEL baseline" OFF)

include(CTest)
add_subdirectory(cpp)
