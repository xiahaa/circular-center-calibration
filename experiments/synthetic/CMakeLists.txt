# SPDX-License-Identifier: Apache-2.0
find_package(PCL 1.10 REQUIRED COMPONENTS common sample_consensus segmentation)

add_executable(circular_center_pcl_batch pcl_circle_fit_batch.cpp)
target_compile_features(circular_center_pcl_batch PRIVATE cxx_std_17)
target_include_directories(circular_center_pcl_batch PRIVATE ${PCL_INCLUDE_DIRS})
target_link_directories(circular_center_pcl_batch PRIVATE ${PCL_LIBRARY_DIRS})
target_compile_options(circular_center_pcl_batch PRIVATE ${PCL_DEFINITIONS})
target_link_libraries(circular_center_pcl_batch PRIVATE ${PCL_LIBRARIES})
