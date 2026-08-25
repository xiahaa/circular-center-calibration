// SPDX-License-Identifier: Apache-2.0
#include <pcl/ModelCoefficients.h>
#include <pcl/PointIndices.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl/sample_consensus/method_types.h>
#include <pcl/sample_consensus/model_types.h>
#include <pcl/segmentation/sac_segmentation.h>

#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

struct Sample {
    int id = -1;
    double distance_threshold = 0.0;
    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud{new pcl::PointCloud<pcl::PointXYZ>};
};

struct FitResult {
    bool success = false;
    std::vector<float> coefficients;
    double elapsed_seconds = 0.0;
    std::size_t inlier_count = 0;
};

std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> fields;
    std::istringstream stream(line);
    std::string field;
    while (std::getline(stream, field, ',')) {
        fields.push_back(field);
    }
    return fields;
}

std::vector<Sample> read_samples(const std::string& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open PCL input CSV: " + path);
    }

    std::string line;
    if (!std::getline(input, line) || line != "sample_id,distance_threshold,x,y,z") {
        throw std::runtime_error("unexpected PCL input CSV header");
    }

    std::vector<Sample> samples;
    std::unordered_map<int, std::size_t> sample_indices;
    std::size_t line_number = 1;
    while (std::getline(input, line)) {
        ++line_number;
        if (line.empty()) {
            continue;
        }
        const auto fields = split_csv(line);
        if (fields.size() != 5) {
            throw std::runtime_error("invalid PCL input row at line " +
                                     std::to_string(line_number));
        }

        const int sample_id = std::stoi(fields[0]);
        const double threshold = std::stod(fields[1]);
        if (!(threshold > 0.0) || !std::isfinite(threshold)) {
            throw std::runtime_error("invalid distance threshold at line " +
                                     std::to_string(line_number));
        }

        auto position = sample_indices.find(sample_id);
        if (position == sample_indices.end()) {
            position = sample_indices.emplace(sample_id, samples.size()).first;
            samples.push_back(Sample{});
            samples.back().id = sample_id;
            samples.back().distance_threshold = threshold;
        } else if (std::abs(samples[position->second].distance_threshold - threshold) > 1e-12) {
            throw std::runtime_error("inconsistent threshold for sample " +
                                     std::to_string(sample_id));
        }

        pcl::PointXYZ point;
        point.x = std::stof(fields[2]);
        point.y = std::stof(fields[3]);
        point.z = std::stof(fields[4]);
        if (!std::isfinite(point.x) || !std::isfinite(point.y) || !std::isfinite(point.z)) {
            throw std::runtime_error("non-finite point at line " + std::to_string(line_number));
        }
        samples[position->second].cloud->push_back(point);
    }

    for (auto& sample : samples) {
        sample.cloud->width = static_cast<std::uint32_t>(sample.cloud->size());
        sample.cloud->height = 1;
        sample.cloud->is_dense = true;
    }
    return samples;
}

FitResult fit_circle(const Sample& sample, int max_iterations, double probability) {
    FitResult result;
    if (sample.cloud->size() < 3) {
        return result;
    }

    pcl::ModelCoefficients coefficients;
    pcl::PointIndices inliers;
    pcl::SACSegmentation<pcl::PointXYZ> segmentation;
    segmentation.setOptimizeCoefficients(true);
    segmentation.setModelType(pcl::SACMODEL_CIRCLE3D);
    segmentation.setMethodType(pcl::SAC_RANSAC);
    segmentation.setDistanceThreshold(sample.distance_threshold);
    segmentation.setMaxIterations(max_iterations);
    segmentation.setProbability(probability);
    segmentation.setInputCloud(sample.cloud);

    const auto start = std::chrono::steady_clock::now();
    segmentation.segment(inliers, coefficients);
    result.elapsed_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    result.inlier_count = inliers.indices.size();
    result.coefficients = std::move(coefficients.values);

    if (result.inlier_count < 3 || result.coefficients.size() < 7) {
        return result;
    }
    result.success = true;
    for (std::size_t index = 0; index < 7; ++index) {
        result.success = result.success && std::isfinite(result.coefficients[index]);
    }
    result.success = result.success && result.coefficients[3] > 0.0F;
    return result;
}

void write_results(const std::string& path,
                   const std::vector<Sample>& samples,
                   int max_iterations,
                   double probability) {
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("cannot open PCL output CSV: " + path);
    }
    output << "sample_id,success,center_x,center_y,center_z,radius,normal_x,normal_y,"
              "normal_z,elapsed_seconds,inlier_count\n";
    output << std::setprecision(17);

    const double nan = std::numeric_limits<double>::quiet_NaN();
    for (const auto& sample : samples) {
        const auto result = fit_circle(sample, max_iterations, probability);
        output << sample.id << ',' << (result.success ? 1 : 0);
        for (std::size_t index = 0; index < 7; ++index) {
            const double value = result.success ? result.coefficients[index] : nan;
            output << ',' << value;
        }
        output << ',' << result.elapsed_seconds << ',' << result.inlier_count << '\n';
    }
}

void print_usage(const char* program) {
    std::cout << "Usage: " << program
              << " INPUT.csv OUTPUT.csv [--max-iterations N] [--probability P]\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--help") {
        print_usage(argv[0]);
        return 0;
    }
    if (argc < 3) {
        print_usage(argv[0]);
        return 2;
    }

    int max_iterations = 1000;
    double probability = 0.99;
    for (int index = 3; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--max-iterations" && index + 1 < argc) {
            max_iterations = std::stoi(argv[++index]);
        } else if (argument == "--probability" && index + 1 < argc) {
            probability = std::stod(argv[++index]);
        } else {
            std::cerr << "unknown or incomplete argument: " << argument << '\n';
            return 2;
        }
    }
    if (max_iterations <= 0 || !(probability > 0.0 && probability < 1.0)) {
        std::cerr << "invalid RANSAC parameters\n";
        return 2;
    }

    try {
        const auto samples = read_samples(argv[1]);
        write_results(argv[2], samples, max_iterations, probability);
        std::cout << "fitted " << samples.size() << " samples with PCL\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
