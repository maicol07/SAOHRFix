#pragma once
#include <array>
#include <atomic>
#include <cstdint>

namespace sprint {
enum class Ui { unknown, open, closed };
inline Ui classify_ui(int character_state, int field_state, bool has_menu) {
    if (character_state>0 && character_state<=8) return Ui::open;
    return character_state==0 && !has_menu && field_state==5 ? Ui::closed : Ui::unknown;
}
enum class Gate : unsigned {
    keyboard, controller, request, physical, player_physical, lock_busy,
    stopped, no_request, capture, original_walk, identity, selector, motion,
    parameter, clip, displacement, ui_unknown, ui_open, preflight, collision,
    revalidation, second_wrapper, accepted, animation, animation_getter, count
};
inline constexpr const char* gate_names[] = {
    "keyboard", "controller", "request", "physical", "player_physical", "lock_busy",
    "stopped", "no_request", "capture", "original_walk", "identity", "selector", "motion",
    "parameter", "clip", "displacement", "ui_unknown", "ui_open", "preflight", "collision",
    "revalidation", "second_wrapper", "accepted", "animation", "animation_getter"
};
static_assert(sizeof(gate_names)/sizeof(*gate_names)==static_cast<unsigned>(Gate::count));
struct Activation {
    std::array<std::atomic<std::uint64_t>, static_cast<unsigned>(Gate::count)> reached{}, excluded{};
    std::atomic<unsigned> first{static_cast<unsigned>(Gate::count)};
    void hit(Gate gate) { reached[static_cast<unsigned>(gate)].fetch_add(1,std::memory_order_relaxed); }
    void reject(Gate gate, bool requested) {
        excluded[static_cast<unsigned>(gate)].fetch_add(1,std::memory_order_relaxed);
        unsigned empty=static_cast<unsigned>(Gate::count);
        if (requested) first.compare_exchange_strong(empty,static_cast<unsigned>(gate));
    }
};
}
