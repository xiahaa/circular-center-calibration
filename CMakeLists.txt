# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)

project(circular_center_calibration VERSION 0.1.0 LANGUAGES CXX)

option(CCC_BUILD_TESTS "Build numerical regression tests" ON)
option(CCC_BUILD_EXAMPLES "Build the minimal C++ example" ON)
option(CCC_BUILD_PCL_BASELINE "Build the optional PCL SACMODEL baseline" OFF)

# Ubuntu's PCL/VTK package exports a VTK::mpi target whose link interface uses
# MPI::MPI_C. Enable C only for the optional PCL build so CMake can materialize
# that imported target without adding a C compiler requirement to the core.
if(CCC_BUILD_PCL_BASELINE)
    enable_language(C)
endif()

include(CTest)
add_subdirectory(cpp)
