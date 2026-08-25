# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)

project(circular_center_calibration VERSION 0.1.1 LANGUAGES CXX)

option(CCC_BUILD_TESTS "Build numerical regression tests" ON)
option(CCC_BUILD_EXAMPLES "Build the minimal C++ example" ON)
option(CCC_BUILD_PCL_EXPERIMENTS "Build the optional PCL experiment adapter" OFF)

include(CTest)
add_subdirectory(cpp)

if(CCC_BUILD_PCL_EXPERIMENTS)
    add_subdirectory(experiments/synthetic)
endif()
