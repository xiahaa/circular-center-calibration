// SPDX-License-Identifier: Apache-2.0
#ifndef CIRCULAR_CENTER_CIRCLE_FIT_RESULT_HPP
#define CIRCULAR_CENTER_CIRCLE_FIT_RESULT_HPP

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include <Eigen/Core>

namespace circular_center
{
enum class FitStatus
{
    kSuccess = 0,
    kInvalidInput,
    kDegenerate,
    kNumericalFailure,
    kNoConsensus,
};

inline const char *FitStatusName(const FitStatus status)
{
    switch (status)
    {
    case FitStatus::kSuccess:
        return "success";
    case FitStatus::kInvalidInput:
        return "invalid_input";
    case FitStatus::kDegenerate:
        return "degenerate";
    case FitStatus::kNumericalFailure:
        return "numerical_failure";
    case FitStatus::kNoConsensus:
        return "no_consensus";
    }
    return "unknown";
}

template <typename Scalar>
struct CircleFitResult
{
    FitStatus status = FitStatus::kNumericalFailure;
    std::string method;
    Eigen::Matrix<Scalar, 3, 1> center =
        Eigen::Matrix<Scalar, 3, 1>::Constant(
            std::numeric_limits<Scalar>::quiet_NaN());
    Scalar radius = std::numeric_limits<Scalar>::quiet_NaN();
    Eigen::Matrix<Scalar, 3, 1> normal =
        Eigen::Matrix<Scalar, 3, 1>::Constant(
            std::numeric_limits<Scalar>::quiet_NaN());
    std::vector<Scalar> residuals;
    std::vector<std::uint8_t> inlier_mask;
    Scalar condition_number = std::numeric_limits<Scalar>::quiet_NaN();
    std::size_t iterations = 0;
    double elapsed_seconds = std::numeric_limits<double>::quiet_NaN();

    explicit operator bool() const noexcept
    {
        return status == FitStatus::kSuccess;
    }
};

}  // namespace circular_center

#endif  // CIRCULAR_CENTER_CIRCLE_FIT_RESULT_HPP
