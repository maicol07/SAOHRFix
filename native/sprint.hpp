#pragma once
#include <cmath>
#include <string>

namespace sprint {
enum class Mode { hold, toggle };
struct Config {
    bool enabled = false;
    Mode mode = Mode::hold;
    float factor = 1.25f;
};
struct Input {
    bool requested = false;
    bool previous = false;
    bool armed = false;
    void update(const Config& c, bool available, bool down) {
        if (!available || !c.enabled) {
            requested = false; previous = down; armed = false; return;
        }
        if (!down) armed = true;
        if (c.mode == Mode::hold) requested = armed && down;
        else if (armed && down && !previous) requested = !requested;
        previous = down;
    }
};
struct alignas(16) Vec { float x, y, z, w; };
inline bool extra(const Vec& requested, const Vec& before, const Vec& after,
                  float factor, Vec& result) {
    const float values[] = {requested.x, requested.y, requested.z, requested.w,
        before.x, before.y, before.z, after.x, after.y, after.z, factor};
    for (float v : values) if (!std::isfinite(v)) return false;
    if (factor != 1.25f || std::fabs(requested.y) > .001f ||
        std::fabs(after.x - before.x - requested.x) > .0002f ||
        std::fabs(after.z - before.z - requested.z) > .0002f ||
        requested.x * requested.x + requested.z * requested.z <= 0) return false;
    result = {requested.x * (factor - 1), 0, requested.z * (factor - 1), 0};
    return true;
}
inline bool parse_config(const std::string& enabled, const std::string& mode,
                         const std::string& factor, const std::string& key,
                         const std::string& button, Config& out) {
    out = {};
    if ((enabled != "true" && enabled != "false") ||
        (mode != "hold" && mode != "toggle") || factor != "1.25" ||
        key != "LeftShift" || button != "LeftThumb") return false;
    out.enabled = enabled == "true";
    out.mode = mode == "hold" ? Mode::hold : Mode::toggle;
    return true;
}
}
