# SPDX-License-Identifier: Apache-2.0
find_package(Eigen3 3.3 REQUIRED NO_MODULE)

add_library(circular_center_core INTERFACE)
add_library(circular_center::core ALIAS circular_center_core)

target_compile_features(circular_center_core INTERFACE cxx_std_17)
target_include_directories(
    circular_center_core
    INTERFACE $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/cpp/include/circular_center>
)
target_link_libraries(circular_center_core INTERFACE Eigen3::Eigen)

if(CCC_BUILD_PCL_BASELINE)
    find_package(PCL 1.10 REQUIRED COMPONENTS common sample_consensus segmentation)

    add_library(circular_center_pcl_sacmodel SHARED src/pcl_sacmodel_c_api.cpp)
    target_compile_features(circular_center_pcl_sacmodel PRIVATE cxx_std_17)
    target_include_directories(
        circular_center_pcl_sacmodel
        PRIVATE ${PCL_INCLUDE_DIRS}
    )
    target_link_directories(circular_center_pcl_sacmodel PRIVATE ${PCL_LIBRARY_DIRS})
    target_compile_options(circular_center_pcl_sacmodel PRIVATE ${PCL_DEFINITIONS})
    target_link_libraries(
        circular_center_pcl_sacmodel
        PUBLIC circular_center::core
        PRIVATE ${PCL_LIBRARIES}
    )

    if(CCC_BUILD_TESTS)
        add_executable(circular_center_pcl_sacmodel_test tests/test_pcl_sacmodel.cpp)
        target_link_libraries(
            circular_center_pcl_sacmodel_test
            PRIVATE circular_center_pcl_sacmodel
        )
        add_test(
            NAME circular_center.pcl_sacmodel_regression
            COMMAND circular_center_pcl_sacmodel_test
        )
    endif()
endif()

if(CCC_BUILD_TESTS)
    add_executable(circular_center_header_smoke tests/header_smoke.cpp)
    target_link_libraries(circular_center_header_smoke PRIVATE circular_center::core)
    add_test(NAME circular_center.header_smoke COMMAND circular_center_header_smoke)

    add_executable(circular_center_fit3d_test tests/test_fit_3d_circle.cpp)
    target_link_libraries(circular_center_fit3d_test PRIVATE circular_center::core)
    add_test(NAME circular_center.fit3d_regression COMMAND circular_center_fit3d_test)
endif()

if(CCC_BUILD_EXAMPLES)
    add_executable(circular_center_fit_circle examples/fit_circle.cpp)
    target_link_libraries(circular_center_fit_circle PRIVATE circular_center::core)
endif()
