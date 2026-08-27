# SPDX-License-Identifier: Apache-2.0

import math

import numpy as np


def get_ellipse_polynomial_coeff(elps):
    a = elps[1][0]*0.5
    b = elps[1][1]*0.5
    theta = elps[2]*np.pi / 180.0
    M_PI = np.pi
    cx = elps[0][0]
    cy = elps[0][1]

    if a<b:
        theta += M_PI/2
        c=a
        a=b
        b=c

    A = (a**2) * (np.sin(theta)**2) + (b**2) * (np.cos(theta)**2)
    B = 2*((b**2)-(a**2))*np.sin(theta)*np.cos(theta)
    C = (a**2)*(np.cos(theta)**2)+(b**2)*(np.sin(theta)**2)
    D = -2*A*cx-B*cy
    E = -B*cx-2*C*cy
    F = A*(cx**2)+B*cx*cy+C*(cy**2)-(a**2)*(b**2)
    k = 1/F

    poly = np.array([A,B,C,D,E,F]) * k
    return poly


def get_ellipse_line_intersections(em, x0, y0, theta):
    p1 = np.zeros((2,))
    p2 = np.zeros((2,))
    if abs(theta - np.pi / 2) < 1e-6:
        p1[0] = x0
        p1[1] = (-(x0 * em[1]) - em[4] - np.sqrt((x0 * em[1] + em[4])**2 - 4 * em[2] * ((x0**2) * em[0] + x0 * em[3] + em[5]))) / (2 * em[2])
        p2[0] = x0
        p2[1] = (-(x0 * em[1]) - em[4] + np.sqrt((x0 * em[1] + em[4])**2 - 4 * em[2] * ((x0**2) * em[0] + x0 * em[3] + em[5]))) / (2 * em[2])
    else:
        lm = np.array([-np.tan(theta), 1.0, np.tan(theta) * x0 - y0])
        tmp0 = lm[0]
        tmp1 = lm[1]
        tmp2 = em[2]
        tmp3 = em[1]
        tmp4 = lm[2]
        tmp5 = em[4]
        tmp6 = em[3]
        tmp7 = tmp1**2
        tmp8 = tmp0**2
        tmp9 = tmp2 * tmp8
        tmp10 = -(tmp3 * tmp0)
        tmp11 = em[0]
        tmp12 = tmp11 * tmp1
        tmp13 = tmp10 + tmp12
        tmp14 = tmp1 * tmp13
        tmp15 = tmp9 + tmp14
        tmp16 = 1 / tmp15
        tmp17 = tmp3 * tmp4
        tmp18 = tmp5 * tmp0 * tmp1
        tmp19 = -(tmp6 * tmp7)
        tmp20 = -2 * tmp2 * tmp0
        tmp21 = tmp3 * tmp1
        tmp22 = tmp20 + tmp21
        tmp23 = tmp22 * tmp4
        tmp24 = tmp18 + tmp19 + tmp23
        tmp25 = tmp24**2
        tmp26 = em[5]
        tmp27 = tmp26 * tmp7
        tmp28 = -(tmp5 * tmp1)
        tmp29 = tmp2 * tmp4
        tmp30 = tmp28 + tmp29
        tmp31 = tmp4 * tmp30
        tmp32 = tmp27 + tmp31
        tmp33 = -4 * tmp15 * tmp32
        tmp34 = tmp25 + tmp33
        if tmp34 > 1e-10:
            tmp35 = np.sqrt(tmp34)
        else:
            tmp35 = 0
        tmp36 = 1 / tmp1
        tmp37 = tmp6 * tmp0
        tmp38 = -2 * tmp11 * tmp4
        tmp39 = tmp37 + tmp38
        tmp40 = tmp7 * tmp39
        tmp41 = -(tmp5 * tmp0)
        tmp42 = tmp41 + tmp17
        tmp43 = tmp0 * tmp1 * tmp42

        p1[0] = -(tmp16 * (tmp6 * tmp7 + 2 * tmp2 * tmp0 * tmp4 - tmp1 * (tmp5 * tmp0 + tmp17) + tmp35)) / 2.
        p1[1] = (tmp36 * tmp16 * (tmp40 + tmp43 + tmp0 * tmp35)) / 2.
        p2[0] = (tmp16 * (tmp18 + tmp19 - 2 * tmp2 * tmp0 * tmp4 + tmp3 * tmp1 * tmp4 + tmp35)) / 2.
        p2[1] = (tmp36 * tmp16 * (tmp40 + tmp43 - tmp0 * tmp35)) / 2.

    return (p1, p2)

def get_distance_given_center(elps, c, r, N, K):
    sum = 0
    sumsq = 0
    f = K[0,0]
    cx = K[0,2]
    cy = K[1,2]
    M_PI = np.pi
    cnt = 0
    for i in range(0,N):
        theta = i * M_PI / N
        p1, p2 = get_ellipse_line_intersections(elps, c[0], c[1], theta)
        if p1 is not None and p2 is not None:
            vr1 = np.array([(p1[0]-cx)/f,(p1[1]-cy)/f,1])
            vr2 = np.array([(p2[0] - cx) / f, (p2[1] - cy) / f, 1])
            vrc = np.array([(c[0] - cx) / f, (c[1] - cy) / f, 1])

            try:
                dotprod = np.dot(vr1/np.linalg.norm(vr1), vrc/np.linalg.norm(vrc))
                dotprod = np.clip(dotprod,-1,1)
                th1 = math.acos(dotprod)
                dotprod = np.dot(vr2/np.linalg.norm(vr2), vrc/np.linalg.norm(vrc))
                dotprod = np.clip(dotprod, -1, 1)
                th2 = math.acos(dotprod)
            except (ValueError, FloatingPointError) as error:
                raise RuntimeError("failed to compute a valid chord angle") from error

            res = np.clip(3-2*np.cos(2*th1)-2*np.cos(2*th2)+np.cos(2*(th1+th2)),0,1e6)
            curd = (np.sqrt(2)*r*np.sin(th1+th2))/np.sqrt(res)

            sum+=curd
            sumsq+=curd**2
            cnt+=1
    if cnt != 0:
        mu = sum /cnt
        if (sumsq/cnt - mu**2) < 1e-10:
            std = 0
        else:
            std = np.sqrt(sumsq/cnt-mu**2)
    else:
        mu = sum / N
        std = np.sqrt(sumsq / N - mu ** 2)

    if np.isnan(std):
        mu = 0
        std = 0

    return (mu, std)

def eval_distance_f0(outer, x, K, marker_diamater, N=16):
    mu, std = get_distance_given_center(outer, x, marker_diamater / 2, N, K)
    ret = std
    # could add some regularization term here

    return ret


def eval_distance_f0_batch(
    outer,
    centers,
    K,
    marker_diameter,
    N=16,
    inverse_intrinsic=None,
):
    """Evaluate the center score for many candidates without Python loops.

    The implementation intersects each line through each candidate center with
    the polynomial ellipse using a batched quadratic equation.  It then applies
    the same angular-distance expression as :func:`eval_distance_f0`.

    Args:
        outer: Six polynomial ellipse coefficients ``[A, B, C, D, E, F]``.
        centers: Candidate image points with shape ``(M, 2)``.
        K: Camera intrinsic matrix. Points are converted to rays with ``K^-1``.
        marker_diameter: Physical marker diameter; it scales all scores equally.
        N: Number of unoriented chord directions through each candidate.
        inverse_intrinsic: Optional precomputed inverse of the rectified ``K``.

    Returns:
        One score per candidate. Invalid/non-intersecting candidates receive
        ``np.inf`` so they cannot become minima accidentally.
    """
    coefficients = np.asarray(outer, dtype=float).reshape(-1)
    candidate_centers = np.asarray(centers, dtype=float)
    intrinsic = np.asarray(K, dtype=float)
    if coefficients.shape != (6,):
        raise ValueError("Expected six polynomial ellipse coefficients")
    if candidate_centers.ndim != 2 or candidate_centers.shape[1] != 2:
        raise ValueError("Expected candidate centers with shape (M, 2)")
    if intrinsic.shape != (3, 3):
        raise ValueError("Expected a 3x3 camera intrinsic matrix")
    if N <= 0:
        raise ValueError("N must be positive")
    if len(candidate_centers) == 0:
        return np.empty((0,), dtype=float)

    angles = np.arange(N, dtype=float) * np.pi / N
    directions = np.column_stack((np.cos(angles), np.sin(angles)))
    dx = directions[:, 0]
    dy = directions[:, 1]

    A, B, C, D, E, F = coefficients
    x0 = candidate_centers[:, 0, None]
    y0 = candidate_centers[:, 1, None]
    quadratic = A * dx**2 + B * dx * dy + C * dy**2
    linear = (
        2.0 * A * x0 * dx
        + B * (x0 * dy + y0 * dx)
        + 2.0 * C * y0 * dy
        + D * dx
        + E * dy
    )
    constant = A * x0**2 + B * x0 * y0 + C * y0**2 + D * x0 + E * y0 + F
    discriminant = linear**2 - 4.0 * quadratic * constant

    coefficient_scale = max(1.0, float(np.max(np.abs(coefficients))))
    tolerance = 100.0 * np.finfo(float).eps * coefficient_scale
    valid = (np.abs(quadratic)[None, :] > tolerance) & (discriminant >= -tolerance)

    with np.errstate(invalid="ignore", divide="ignore"):
        square_root = np.sqrt(np.maximum(discriminant, 0.0))
        root_1 = (-linear - square_root) / (2.0 * quadratic)
        root_2 = (-linear + square_root) / (2.0 * quadratic)
        point_1 = candidate_centers[:, None, :] + root_1[:, :, None] * directions
        point_2 = candidate_centers[:, None, :] + root_2[:, :, None] * directions

        if inverse_intrinsic is None:
            inverse_intrinsic = np.linalg.inv(intrinsic)
        else:
            inverse_intrinsic = np.asarray(inverse_intrinsic, dtype=float)
            if inverse_intrinsic.shape != (3, 3) or not np.isfinite(inverse_intrinsic).all():
                raise ValueError("inverse_intrinsic must be a finite 3x3 matrix")
        center_homogeneous = np.column_stack(
            (candidate_centers, np.ones(len(candidate_centers)))
        )
        point_1_homogeneous = np.concatenate(
            (point_1, np.ones(point_1.shape[:2] + (1,))), axis=2
        )
        point_2_homogeneous = np.concatenate(
            (point_2, np.ones(point_2.shape[:2] + (1,))), axis=2
        )
        center_rays = center_homogeneous @ inverse_intrinsic.T
        ray_1 = point_1_homogeneous @ inverse_intrinsic.T
        ray_2 = point_2_homogeneous @ inverse_intrinsic.T

        center_rays /= np.linalg.norm(center_rays, axis=1, keepdims=True)
        ray_1 /= np.linalg.norm(ray_1, axis=2, keepdims=True)
        ray_2 /= np.linalg.norm(ray_2, axis=2, keepdims=True)
        theta_1 = np.arccos(
            np.clip(np.einsum("mnj,mj->mn", ray_1, center_rays), -1.0, 1.0)
        )
        theta_2 = np.arccos(
            np.clip(np.einsum("mnj,mj->mn", ray_2, center_rays), -1.0, 1.0)
        )

        denominator_term = np.clip(
            3.0
            - 2.0 * np.cos(2.0 * theta_1)
            - 2.0 * np.cos(2.0 * theta_2)
            + np.cos(2.0 * (theta_1 + theta_2)),
            0.0,
            1e6,
        )
        radius = marker_diameter / 2.0
        distances = (
            np.sqrt(2.0) * radius * np.sin(theta_1 + theta_2)
        ) / np.sqrt(denominator_term)
        scores = np.std(distances, axis=1)

    valid_rows = np.all(valid, axis=1) & np.all(np.isfinite(distances), axis=1)
    scores[~valid_rows | ~np.isfinite(scores)] = np.inf
    return scores
