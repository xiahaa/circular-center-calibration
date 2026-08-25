// SPDX-License-Identifier: Apache-2.0
#ifndef CIRCULAR_CENTER_PCL_SACMODEL_C_API_H
#define CIRCULAR_CENTER_PCL_SACMODEL_C_API_H

#include <cstddef>
#include <cstdint>

#if defined(_WIN32)
#define CCC_PCL_SACMODEL_API __declspec(dllexport)
#else
#define CCC_PCL_SACMODEL_API
#endif

extern "C"
{

CCC_PCL_SACMODEL_API int ccc_pcl_sacmodel_abi_version();

// Coefficients are returned as center xyz, radius, and normal xyz.
// A non-positive maximum_radius disables the upper radius constraint.
CCC_PCL_SACMODEL_API int ccc_pcl_sacmodel_fit_circle3d(
    const double *points_xyz,
    std::size_t point_count,
    double distance_threshold,
    int max_iterations,
    double probability,
    double minimum_radius,
    double maximum_radius,
    double *coefficients,
    std::uint8_t *inlier_mask,
    char *error_message,
    std::size_t error_capacity);

}  // extern "C"

#endif  // CIRCULAR_CENTER_PCL_SACMODEL_C_API_H
