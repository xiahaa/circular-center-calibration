// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

#include <Eigen/Core>
#include <Eigen/Geometry>

#include "PclSacmodelCAPI.h"

int main()
{
    constexpr double pi = 3.14159265358979323846;
    const Eigen::Vector3d expected_center(0.4, -0.3, 1.2);
    constexpr double expected_radius = 0.8;
    const Eigen::Vector3d expected_normal =
        Eigen::Vector3d(0.3, -0.4, 0.8660254037844386).normalized();
    Eigen::Vector3d reference = Eigen::Vector3d::UnitX();
    if (std::abs(expected_normal.dot(reference)) > 0.9)
        reference = Eigen::Vector3d::UnitY();
    const Eigen::Vector3d basis_u = expected_normal.cross(reference).normalized();
    const Eigen::Vector3d basis_v = expected_normal.cross(basis_u).normalized();

    std::vector<double> points;
    for (int index = 0; index < 64; ++index)
    {
        const double angle = 2.0 * pi * static_cast<double>(index) / 64.0;
        const Eigen::Vector3d point = expected_center + expected_radius *
            (std::cos(angle) * basis_u + std::sin(angle) * basis_v);
        points.insert(points.end(), {point.x(), point.y(), point.z()});
    }
    points.insert(points.end(), {2.0, 2.0, 2.0, -1.0, 0.5, 0.0});

    const std::size_t point_count = points.size() / 3;
    std::array<double, 7> coefficients{};
    std::vector<std::uint8_t> inlier_mask(point_count, 0);
    std::array<char, 512> error{};
    const int status = ccc_pcl_sacmodel_fit_circle3d(
        points.data(), point_count, 0.01, 1000, 0.99, 0.5, 1.0,
        coefficients.data(), inlier_mask.data(), error.data(), error.size());
    const Eigen::Vector3d center(coefficients[0], coefficients[1], coefficients[2]);
    const Eigen::Vector3d normal(coefficients[4], coefficients[5], coefficients[6]);
    const int inlier_count = static_cast<int>(
        std::count(inlier_mask.begin(), inlier_mask.end(), std::uint8_t{1}));
    if (status != 0 || ccc_pcl_sacmodel_abi_version() != 1 ||
        (center - expected_center).norm() > 1e-3 ||
        std::abs(coefficients[3] - expected_radius) > 1e-3 ||
        std::abs(std::abs(normal.normalized().dot(expected_normal)) - 1.0) > 1e-3 ||
        inlier_count < 64)
    {
        std::cerr << "PCL SACMODEL regression failed: " << error.data() << '\n';
        return 1;
    }
    return 0;
}
