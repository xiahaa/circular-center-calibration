// SPDX-License-Identifier: Apache-2.0

#include <cmath>
#include <iostream>
#include <vector>

#include <Eigen/Core>

#include "CircleFitResult.hpp"
#include "Fit3DCircle.hpp"

namespace
{
struct Point3
{
    double x;
    double y;
    double z;
};

std::vector<Point3> makeCircle(
    const Eigen::Vector3d &center,
    double radius,
    const Eigen::Vector3d &normal,
    double arc_radians,
    int count)
{
    Eigen::Vector3d reference = Eigen::Vector3d::UnitX();
    if (std::abs(normal.dot(reference)) > 0.9)
        reference = Eigen::Vector3d::UnitY();
    const Eigen::Vector3d basis_u = normal.cross(reference).normalized();
    const Eigen::Vector3d basis_v = normal.cross(basis_u).normalized();

    std::vector<Point3> points;
    points.reserve(static_cast<std::size_t>(count));
    for (int index = 0; index < count; ++index)
    {
        const double fraction = static_cast<double>(index) / count;
        const double angle = 0.31 + arc_radians * fraction;
        const Eigen::Vector3d point = center + radius *
            (std::cos(angle) * basis_u + std::sin(angle) * basis_v);
        points.push_back({point.x(), point.y(), point.z()});
    }
    return points;
}
}  // namespace

int main()
{
    constexpr double pi = 3.14159265358979323846;
    const Eigen::Vector3d expected_center(1.5, -0.7, 2.0);
    constexpr double expected_radius = 0.8;
    const Eigen::Vector3d expected_normal =
        Eigen::Vector3d(0.3, -0.4, 0.8660254037844386).normalized();

    const auto points = makeCircle(
        expected_center, expected_radius, expected_normal, 2.0 * pi, 64);
    const auto result = ConformalFit3DCircle::FitDetailed(points);
    if (!result || result.method != "normalized_cga" ||
        (result.center - expected_center).norm() > 1e-8 ||
        std::abs(result.radius - expected_radius) > 1e-8 ||
        std::abs(std::abs(result.normal.dot(expected_normal)) - 1.0) > 1e-8 ||
        result.residuals.size() != points.size())
    {
        std::cerr << "exact-circle regression failed\n";
        return 1;
    }

    const auto partial = makeCircle(
        expected_center, expected_radius, expected_normal, 2.0 * pi / 3.0, 64);
    const auto partial_result = ConformalFit3DCircle::FitDetailed(partial);
    if (!partial_result || (partial_result.center - expected_center).norm() > 1e-8 ||
        std::abs(partial_result.radius - expected_radius) > 1e-8)
    {
        std::cerr << "partial-arc regression failed\n";
        return 1;
    }

    std::vector<Point3> collinear;
    for (int index = -5; index <= 5; ++index)
    {
        const double value = static_cast<double>(index);
        collinear.push_back({value, 2.0 * value, -value});
    }
    const auto invalid = ConformalFit3DCircle::FitDetailed(collinear);
    if (invalid.status != circular_center::FitStatus::kDegenerate)
    {
        std::cerr << "degenerate input was not rejected\n";
        return 1;
    }

    const Eigen::Vector3d translated_center(1e6, -5e5, 2.5e5);
    const auto translated = makeCircle(
        translated_center, expected_radius, expected_normal, 2.0 * pi, 128);
    const auto translated_result = ConformalFit3DCircle::FitDetailed(translated);
    if (!translated_result ||
        (translated_result.center - translated_center).norm() > 1e-7 ||
        std::abs(translated_result.radius - expected_radius) > 1e-7)
    {
        std::cerr << "large-translation regression failed\n";
        return 1;
    }

    return 0;
}
