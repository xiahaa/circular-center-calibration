// SPDX-License-Identifier: Apache-2.0

#include "PclSacmodelCAPI.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
#include <string>

#include <pcl/ModelCoefficients.h>
#include <pcl/PointIndices.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl/sample_consensus/method_types.h>
#include <pcl/sample_consensus/model_types.h>
#include <pcl/segmentation/sac_segmentation.h>

namespace
{
constexpr int kSuccess = 0;
constexpr int kInvalidInput = 1;
constexpr int kNoConsensus = 2;
constexpr int kInternalFailure = 3;

int fail(
    const int status,
    const std::string &message,
    char *error_message,
    const std::size_t error_capacity)
{
    if (error_message != nullptr && error_capacity > 0)
    {
        std::snprintf(error_message, error_capacity, "%s", message.c_str());
    }
    return status;
}

bool finitePoint(const double *point)
{
    return std::isfinite(point[0]) && std::isfinite(point[1]) &&
        std::isfinite(point[2]);
}
}  // namespace

extern "C" int ccc_pcl_sacmodel_abi_version()
{
    return 1;
}

extern "C" int ccc_pcl_sacmodel_fit_circle3d(
    const double *points_xyz,
    const std::size_t point_count,
    const double distance_threshold,
    const int max_iterations,
    const double probability,
    const double minimum_radius,
    const double maximum_radius,
    double *coefficients,
    std::uint8_t *inlier_mask,
    char *error_message,
    const std::size_t error_capacity)
{
    if (points_xyz == nullptr || coefficients == nullptr || inlier_mask == nullptr)
    {
        return fail(kInvalidInput, "input and output pointers must not be null",
                    error_message, error_capacity);
    }
    if (point_count < 3)
    {
        return fail(kInvalidInput, "at least three points are required",
                    error_message, error_capacity);
    }
    if (!std::isfinite(distance_threshold) || distance_threshold <= 0.0 ||
        max_iterations <= 0 || !std::isfinite(probability) || probability <= 0.0 ||
        probability >= 1.0 || !std::isfinite(minimum_radius) || minimum_radius < 0.0 ||
        !std::isfinite(maximum_radius) ||
        (maximum_radius > 0.0 && maximum_radius < minimum_radius))
    {
        return fail(kInvalidInput, "invalid PCL SACMODEL parameters",
                    error_message, error_capacity);
    }

    try
    {
        auto cloud = pcl::make_shared<pcl::PointCloud<pcl::PointXYZ>>();
        cloud->resize(point_count);
        for (std::size_t index = 0; index < point_count; ++index)
        {
            const double *source = points_xyz + 3 * index;
            if (!finitePoint(source))
            {
                return fail(kInvalidInput, "points must contain only finite values",
                            error_message, error_capacity);
            }
            (*cloud)[index].x = static_cast<float>(source[0]);
            (*cloud)[index].y = static_cast<float>(source[1]);
            (*cloud)[index].z = static_cast<float>(source[2]);
        }
        cloud->width = static_cast<std::uint32_t>(point_count);
        cloud->height = 1;
        cloud->is_dense = true;

        pcl::SACSegmentation<pcl::PointXYZ> segmentation(false);
        segmentation.setOptimizeCoefficients(true);
        segmentation.setModelType(pcl::SACMODEL_CIRCLE3D);
        segmentation.setMethodType(pcl::SAC_RANSAC);
        segmentation.setDistanceThreshold(distance_threshold);
        segmentation.setMaxIterations(max_iterations);
        segmentation.setProbability(probability);
        if (minimum_radius > 0.0 || maximum_radius > 0.0)
        {
            segmentation.setRadiusLimits(
                minimum_radius,
                maximum_radius > 0.0 ? maximum_radius :
                    std::numeric_limits<double>::max());
        }
        segmentation.setInputCloud(cloud);

        pcl::PointIndices inliers;
        pcl::ModelCoefficients model;
        segmentation.segment(inliers, model);
        if (inliers.indices.empty() || model.values.size() != 7)
        {
            return fail(kNoConsensus, "PCL SACMODEL did not find a 3D circle",
                        error_message, error_capacity);
        }

        std::fill(inlier_mask, inlier_mask + point_count, std::uint8_t{0});
        for (const int index : inliers.indices)
        {
            if (index >= 0 && static_cast<std::size_t>(index) < point_count)
                inlier_mask[static_cast<std::size_t>(index)] = std::uint8_t{1};
        }
        for (std::size_t index = 0; index < model.values.size(); ++index)
            coefficients[index] = static_cast<double>(model.values[index]);
        if (error_message != nullptr && error_capacity > 0)
            error_message[0] = '\0';
        return kSuccess;
    }
    catch (const std::exception &error)
    {
        return fail(kInternalFailure, error.what(), error_message, error_capacity);
    }
    catch (...)
    {
        return fail(kInternalFailure, "unknown PCL failure", error_message, error_capacity);
    }
}
