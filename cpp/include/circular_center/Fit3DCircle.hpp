// SPDX-License-Identifier: Apache-2.0
#ifndef CIRCULAR_CENTER_FIT_3D_CIRCLE_HPP
#define CIRCULAR_CENTER_FIT_3D_CIRCLE_HPP

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <limits>
#include <type_traits>
#include <vector>

#include <Eigen/Core>
#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include "CircleFitResult.hpp"

class ConformalFit3DCicle
{
private:
    ConformalFit3DCicle() = default;

    template <typename Scalar>
    static Eigen::Matrix<Scalar, 5, 5> ConformalMetric()
    {
        Eigen::Matrix<Scalar, 5, 5> metric =
            Eigen::Matrix<Scalar, 5, 5>::Zero();
        metric(0, 0) = Scalar(1);
        metric(1, 1) = Scalar(1);
        metric(2, 2) = Scalar(1);
        metric(3, 4) = Scalar(-1);
        metric(4, 3) = Scalar(-1);
        return metric;
    }

    template <typename Scalar>
    static circular_center::FitStatus CanonicalizeNormal(
        Eigen::Matrix<Scalar, 3, 1> &normal)
    {
        const Scalar norm = normal.norm();
        if (!std::isfinite(norm) || norm <= std::numeric_limits<Scalar>::epsilon())
            return circular_center::FitStatus::kDegenerate;
        normal /= norm;
        Eigen::Index pivot = 0;
        normal.cwiseAbs().maxCoeff(&pivot);
        if (normal(pivot) < Scalar(0))
            normal = -normal;
        return circular_center::FitStatus::kSuccess;
    }

public:
    template <typename Derived>
    static int Skew(
        const Eigen::Matrix<typename Derived::Scalar, 3, 1> &value,
        Eigen::MatrixBase<Derived> &matrix)
    {
        matrix << typename Derived::Scalar(0), -value[2], value[1],
            value[2], typename Derived::Scalar(0), -value[0],
            -value[1], value[0], typename Derived::Scalar(0);
        return 0;
    }

    template <typename Derived>
    static int OuterProduct(
        const Eigen::MatrixBase<Derived> &y,
        const Eigen::MatrixBase<Derived> &x,
        Eigen::Matrix<typename Derived::Scalar, 10, 1> &value)
    {
        using Scalar = typename Derived::Scalar;
        Eigen::Matrix<Scalar, 3, 3> skew;
        Skew(y.template head<3>(), skew);
        Eigen::Matrix<Scalar, 10, 5> matrix =
            Eigen::Matrix<Scalar, 10, 5>::Zero();
        matrix.template block<3, 3>(0, 0) = skew;
        matrix.template block<3, 3>(3, 0) =
            y[3] * Eigen::Matrix<Scalar, 3, 3>::Identity();
        matrix.template block<3, 1>(3, 3) = -y.template head<3>();
        matrix.template block<3, 3>(6, 0) =
            -y[4] * Eigen::Matrix<Scalar, 3, 3>::Identity();
        matrix.template block<3, 1>(6, 4) = y.template head<3>();
        matrix(9, 3) = -y(4);
        matrix(9, 4) = y(3);
        value.noalias() = matrix * x;
        return 0;
    }

    template <typename Point, typename Derived>
    static int EstablishPmat(
        const std::vector<Point> &points,
        Eigen::MatrixBase<Derived> &operator_matrix)
    {
        using Scalar = typename Derived::Scalar;
        if (points.empty())
            return -1;
        Eigen::Matrix<Scalar, 5, 5> scatter =
            Eigen::Matrix<Scalar, 5, 5>::Zero();
        for (const auto &point : points)
        {
            const Eigen::Matrix<Scalar, 3, 1> xyz(
                static_cast<Scalar>(point.x),
                static_cast<Scalar>(point.y),
                static_cast<Scalar>(point.z));
            if (!xyz.allFinite())
                return -1;
            Eigen::Matrix<Scalar, 5, 1> embedded;
            embedded << xyz, Scalar(1), Scalar(0.5) * xyz.squaredNorm();
            scatter.noalias() += embedded * embedded.transpose();
        }
        operator_matrix =
            (scatter / static_cast<Scalar>(points.size())) * ConformalMetric<Scalar>();
        return 0;
    }

    template <typename Derived, typename NormalDerived>
    static int ExtractGeometricParameters(
        const Eigen::Matrix<typename Derived::Scalar, 10, 1> &representation,
        Eigen::MatrixBase<Derived> &center,
        Eigen::MatrixBase<NormalDerived> &normal,
        typename Derived::Scalar &radius)
    {
        using Scalar = typename Derived::Scalar;
        static_assert(
            std::is_same<Scalar, typename NormalDerived::Scalar>::value,
            "center and normal must use the same scalar type");
        const auto euclidean = representation.template head<3>();
        const auto origin = representation.template segment<3>(3);
        const auto infinity = representation.template segment<3>(6);
        const Scalar origin_infinity = -representation[9];
        const Scalar tolerance = Scalar(100) * std::numeric_limits<Scalar>::epsilon() *
                                 std::max(Scalar(1), representation.norm());
        const Scalar alpha = origin.norm();
        if (!std::isfinite(alpha) || alpha <= tolerance)
            return -1;

        Eigen::Matrix<Scalar, 3, 1> unit_normal = -origin / alpha;
        const Eigen::Matrix<Scalar, 3, 1> unscaled_normal = -origin;
        const Scalar normal_squared = unscaled_normal.squaredNorm();
        if (!std::isfinite(normal_squared) || normal_squared <= tolerance * tolerance)
            return -1;

        Eigen::Matrix<Scalar, 3, 3> matrix;
        matrix.row(0) << origin_infinity, -euclidean[2], euclidean[1];
        matrix.row(1) << euclidean[2], origin_infinity, -euclidean[0];
        matrix.row(2) << -euclidean[1], euclidean[0], origin_infinity;
        center = matrix * unscaled_normal / normal_squared;
        Scalar radius_squared = center.squaredNorm() -
                                Scalar(2) * unit_normal.dot(infinity) / alpha -
                                Scalar(2) * std::pow(center.dot(unit_normal), Scalar(2));
        const Scalar radius_tolerance = Scalar(1e-10) *
                                        std::max(Scalar(1), center.squaredNorm());
        if (!std::isfinite(radius_squared) || radius_squared < -radius_tolerance)
            return -1;
        radius = std::sqrt(std::max(Scalar(0), radius_squared));
        if (CanonicalizeNormal(unit_normal) != circular_center::FitStatus::kSuccess)
            return -1;
        normal = unit_normal;
        return center.allFinite() && normal.allFinite() && std::isfinite(radius) ? 0 : -1;
    }

    template <typename Derived>
    static int ExtractGeometricParameters(
        const Eigen::Matrix<typename Derived::Scalar, 10, 1> &representation,
        Eigen::MatrixBase<Derived> &center,
        typename Derived::Scalar &radius)
    {
        Eigen::Matrix<typename Derived::Scalar, 3, 1> normal;
        return ExtractGeometricParameters(representation, center, normal, radius);
    }

    template <typename Point, typename Scalar>
    static circular_center::FitStatus FitImpl(
        const std::vector<Point> &points,
        Eigen::Matrix<Scalar, 3, 1> &center,
        Scalar &radius,
        Eigen::Matrix<Scalar, 3, 1> &normal,
        Scalar *condition_number)
    {
        using circular_center::FitStatus;
        if (points.size() < 3)
            return FitStatus::kInvalidInput;

        Eigen::Matrix<Scalar, 3, 1> centroid =
            Eigen::Matrix<Scalar, 3, 1>::Zero();
        for (const auto &point : points)
        {
            const Eigen::Matrix<Scalar, 3, 1> value(
                static_cast<Scalar>(point.x),
                static_cast<Scalar>(point.y),
                static_cast<Scalar>(point.z));
            if (!value.allFinite())
                return FitStatus::kInvalidInput;
            centroid += value;
        }
        centroid /= static_cast<Scalar>(points.size());

        Eigen::Matrix<Scalar, 3, 3> coordinate_scatter =
            Eigen::Matrix<Scalar, 3, 3>::Zero();
        Scalar sum_squared_distance = Scalar(0);
        for (const auto &point : points)
        {
            const Eigen::Matrix<Scalar, 3, 1> centered(
                static_cast<Scalar>(point.x) - centroid.x(),
                static_cast<Scalar>(point.y) - centroid.y(),
                static_cast<Scalar>(point.z) - centroid.z());
            coordinate_scatter.noalias() += centered * centered.transpose();
            sum_squared_distance += centered.squaredNorm();
        }
        Eigen::SelfAdjointEigenSolver<Eigen::Matrix<Scalar, 3, 3>> coordinate_solver(
            coordinate_scatter);
        if (coordinate_solver.info() != Eigen::Success)
            return FitStatus::kNumericalFailure;
        const auto coordinate_values = coordinate_solver.eigenvalues();
        const Scalar rank_tolerance = Scalar(100) *
                                      std::numeric_limits<Scalar>::epsilon() *
                                      std::max(Scalar(1), coordinate_values.maxCoeff());
        if (coordinate_values(1) <= rank_tolerance)
            return FitStatus::kDegenerate;

        const Scalar rms_distance = std::sqrt(
            sum_squared_distance / static_cast<Scalar>(points.size()));
        if (!std::isfinite(rms_distance) ||
            rms_distance <= std::numeric_limits<Scalar>::epsilon())
            return FitStatus::kDegenerate;
        const Scalar scale = std::sqrt(Scalar(2)) / rms_distance;

        // Accumulate only a fixed 5x5 scatter matrix.  No dynamic 5xN
        // conformal matrix or normalized point buffer is allocated.
        Eigen::Matrix<Scalar, 5, 5> conformal_scatter =
            Eigen::Matrix<Scalar, 5, 5>::Zero();
        for (const auto &point : points)
        {
            const Eigen::Matrix<Scalar, 3, 1> normalized(
                (static_cast<Scalar>(point.x) - centroid.x()) * scale,
                (static_cast<Scalar>(point.y) - centroid.y()) * scale,
                (static_cast<Scalar>(point.z) - centroid.z()) * scale);
            Eigen::Matrix<Scalar, 5, 1> embedded;
            embedded << normalized, Scalar(1),
                Scalar(0.5) * normalized.squaredNorm();
            conformal_scatter.noalias() += embedded * embedded.transpose();
        }
        const Eigen::Matrix<Scalar, 5, 5> operator_matrix =
            (conformal_scatter / static_cast<Scalar>(points.size())) *
            ConformalMetric<Scalar>();

        Eigen::EigenSolver<Eigen::Matrix<Scalar, 5, 5>> eigen_solver(operator_matrix);
        if (eigen_solver.info() != Eigen::Success)
            return FitStatus::kNumericalFailure;
        const auto eigenvalues = eigen_solver.eigenvalues();
        const auto eigenvectors = eigen_solver.eigenvectors();
        std::vector<int> indices{0, 1, 2, 3, 4};
        std::sort(indices.begin(), indices.end(), [&eigenvalues](const int lhs, const int rhs) {
            return std::abs(eigenvalues[lhs]) < std::abs(eigenvalues[rhs]);
        });
        const Scalar spectrum_scale = std::max(
            Scalar(1), eigenvalues.cwiseAbs().maxCoeff());
        const Scalar imaginary_tolerance = Scalar(1e-10) * spectrum_scale;
        if (std::abs(eigenvalues[indices[0]].imag()) > imaginary_tolerance ||
            std::abs(eigenvalues[indices[1]].imag()) > imaginary_tolerance)
            return FitStatus::kNumericalFailure;

        // With the indefinite CGA metric, an exact real two-dimensional
        // nullspace may appear as a conjugate eigenvector pair.  Recover the
        // real span rather than treating the operator as symmetric PSD.
        Eigen::Matrix<Scalar, 5, 4> real_candidates;
        real_candidates.col(0) = eigenvectors.col(indices[0]).real();
        real_candidates.col(1) = eigenvectors.col(indices[1]).real();
        real_candidates.col(2) = eigenvectors.col(indices[0]).imag();
        real_candidates.col(3) = eigenvectors.col(indices[1]).imag();
        Eigen::JacobiSVD<Eigen::Matrix<Scalar, 5, 4>> subspace_solver(
            real_candidates, Eigen::ComputeFullU);
        const auto subspace_values = subspace_solver.singularValues();
        const Scalar subspace_tolerance = Scalar(100) *
                                          std::numeric_limits<Scalar>::epsilon() *
                                          Scalar(5) *
                                          std::max(Scalar(1), subspace_values(0));
        if (subspace_values(1) <= subspace_tolerance)
            return FitStatus::kNumericalFailure;

        Eigen::Matrix<Scalar, 10, 1> bivector;
        OuterProduct(
            subspace_solver.matrixU().col(1),
            subspace_solver.matrixU().col(0),
            bivector);
        Eigen::Matrix<Scalar, 3, 1> normalized_center;
        Scalar normalized_radius = Scalar(0);
        if (ExtractGeometricParameters(
                bivector, normalized_center, normal, normalized_radius) != 0)
            return FitStatus::kNumericalFailure;
        center = normalized_center / scale + centroid;
        radius = normalized_radius / scale;
        if (!center.allFinite() || !normal.allFinite() || !std::isfinite(radius))
            return FitStatus::kNumericalFailure;

        if (condition_number != nullptr)
        {
            Eigen::JacobiSVD<Eigen::Matrix<Scalar, 5, 5>> spectrum(operator_matrix);
            const auto values = spectrum.singularValues();
            const Scalar floor = std::max(
                std::numeric_limits<Scalar>::epsilon() * values(0),
                std::numeric_limits<Scalar>::min());
            *condition_number = values(0) / std::max(values(2), floor);
        }
        return FitStatus::kSuccess;
    }

    template <typename Point, typename Derived>
    static int Fit(
        const std::vector<Point> &points,
        Eigen::MatrixBase<Derived> &center,
        typename Derived::Scalar &radius)
    {
        using Scalar = typename Derived::Scalar;
        Eigen::Matrix<Scalar, 3, 1> fitted_center;
        Eigen::Matrix<Scalar, 3, 1> fitted_normal;
        const auto status = FitImpl(
            points, fitted_center, radius, fitted_normal,
            static_cast<Scalar *>(nullptr));
        if (status != circular_center::FitStatus::kSuccess)
            return -1;
        center = fitted_center;
        return 0;
    }

    template <typename Point, typename CenterDerived, typename NormalDerived>
    static int Fit(
        const std::vector<Point> &points,
        Eigen::MatrixBase<CenterDerived> &center,
        Eigen::MatrixBase<NormalDerived> &normal,
        typename CenterDerived::Scalar &radius)
    {
        using Scalar = typename CenterDerived::Scalar;
        static_assert(
            std::is_same<Scalar, typename NormalDerived::Scalar>::value,
            "center and normal must use the same scalar type");
        Eigen::Matrix<Scalar, 3, 1> fitted_center;
        Eigen::Matrix<Scalar, 3, 1> fitted_normal;
        const auto status = FitImpl(
            points, fitted_center, radius, fitted_normal,
            static_cast<Scalar *>(nullptr));
        if (status != circular_center::FitStatus::kSuccess)
            return -1;
        center = fitted_center;
        normal = fitted_normal;
        return 0;
    }

    template <typename Scalar = double, typename Point>
    static circular_center::CircleFitResult<Scalar> FitDetailed(
        const std::vector<Point> &points)
    {
        const auto start = std::chrono::steady_clock::now();
        circular_center::CircleFitResult<Scalar> result;
        result.method = "normalized_cga";
        result.status = FitImpl(
            points,
            result.center,
            result.radius,
            result.normal,
            &result.condition_number);
        result.iterations = result.status == circular_center::FitStatus::kSuccess ? 1 : 0;
        if (result.status == circular_center::FitStatus::kSuccess)
        {
            result.residuals.reserve(points.size());
            result.inlier_mask.assign(points.size(), std::uint8_t(1));
            for (const auto &point : points)
            {
                const Eigen::Matrix<Scalar, 3, 1> offset(
                    static_cast<Scalar>(point.x) - result.center.x(),
                    static_cast<Scalar>(point.y) - result.center.y(),
                    static_cast<Scalar>(point.z) - result.center.z());
                const Scalar plane = offset.dot(result.normal);
                const Scalar radial =
                    (offset - plane * result.normal).norm() - result.radius;
                result.residuals.push_back(std::hypot(plane, radial));
            }
        }
        result.elapsed_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        return result;
    }
};

using ConformalFit3DCircle = ConformalFit3DCicle;

#endif  // CIRCULAR_CENTER_FIT_3D_CIRCLE_HPP
