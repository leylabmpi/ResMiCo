#pragma once

#include <algorithm>
#include <cmath>
#include <sstream>
#include <string>
#include <vector>

/**
 * Join a vector's element into sep-separated string.
 */
template <typename T>
std::string join_vec(const std::vector<T> &vec, char sep = ',') {
    std::stringstream out;
    if (vec.empty()) {
        return "";
    }

    for (uint32_t i = 0; i < vec.size() - 1; ++i) {
        out << vec[i] << sep;
    }
    out << vec.back();
    out << std::endl;
    return out.str();
}

template <typename T>
std::tuple<T, double, T> min_mean_max(const std::vector<T> &v) {
    if (v.empty()) {
        return { 0, 0, 0 };
    }
    T min = v[0];
    T max = v[0];
    double mean = v[0];
    for (uint32_t i = 1; i < v.size(); ++i) {
        if (v[i] < min) {
            min = v[i];
        }
        if (v[i] > max) {
            max = v[i];
        }
        mean += v[i];
    }
    return { min, mean / v.size(), max };
}

template <typename T>
double std_dev(const std::vector<T> &v, double mean) {
    if (v.size() < 2) {
        return NAN;
    }
    double var = 0;
    for (T el : v) {
        var += (el - mean) * (el - mean);
    }
    var /= (v.size()-1);
    return sqrt(var);
}

bool starts_with(std::string const &value, std::string const &prefix);
bool ends_with(std::string const &value, std::string const &ending);

// trim from start (in place)
static inline void ltrim(std::string &s) {
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](char ch) {
      return !std::isspace(ch);
    }));
}

// trim from end (in place)
static inline void rtrim(std::string &s) {
    s.erase(std::find_if(s.rbegin(), s.rend(), [](char ch) {
      return !std::isspace(ch);
    }).base(), s.end());
}

// trim from both ends (in place)
static inline void trim(std::string &s) {
    ltrim(s);
    rtrim(s);
}

/** Truncate to 2 decimals */
std::string round2(float v);
