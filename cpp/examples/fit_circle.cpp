// SPDX-License-Identifier: Apache-2.0

#include <cmath>
#include <iostream>
#include <vector>

#include <Eigen/Core>

#include "Fit3DCircle.hpp"

struct Point3
{
    double x;
    double y;
    double z;
};

int main()
{
    constexpr double pi = 3.14159265358979323846;
    const Eigen::Vector3d expected_center(0.4, -0.3, 1.2);
    constexpr double expected_radius = 0.12;
    const Eigen::Vector3d normal =
        Eigen::Vector3d(0.3, -0.4, 0.8660254037844386).normalized();
    const Eigen::Vector3d basis_u = normal.cross(Eigen::Vector3d::UnitX()).normalized();
    const Eigen::Vector3d basis_v = normal.cross(basis_u).normalized();

    std::vector<Point3> points;
    for (int index = 0; index < 64; ++index)
    {
        const double angle = 2.0 * pi * static_cast<double>(index) / 64.0;
        const Eigen::Vector3d point = expected_center + expected_radius *
            (std::cos(angle) * basis_u + std::sin(angle) * basis_v);
        points.push_back({point.x(), point.y(), point.z()});
    }

    const auto result = ConformalFit3DCircle::FitDetailed(points);
    if (!result)
    {
        std::cerr << "circle fit failed: "
                  << circular_center::FitStatusName(result.status) << '\n';
        return 1;
    }

    std::cout << "center: " << result.center.transpose() << '\n'
              << "radius: " << result.radius << '\n'
              << "normal: " << result.normal.transpose() << '\n'
              << "center error [m]: "
              << (result.center - expected_center).norm() << '\n';
    return 0;
}
