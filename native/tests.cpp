#include "sprint.hpp"
#include <cassert>
#include <limits>
int main() {
    using namespace sprint;
    Config c; assert(parse_config("true", "hold", "1.25", "LeftShift", "LeftThumb", c));
    Input i;
    i.update(c, true, true); assert(!i.requested);
    i.update(c, true, false); i.update(c, true, true); assert(i.requested);
    i.update(c, false, true); assert(!i.requested);
    i.update(c, true, true); assert(!i.requested);
    i.update(c, true, false); i.update(c, true, true); assert(i.requested);
    i.update(c, true, false); assert(!i.requested);
    c.mode = Mode::toggle;
    i.update(c, true, true); assert(i.requested);
    i.update(c, true, true); assert(i.requested);
    i.update(c, true, false); assert(i.requested);
    i.update(c, true, true); assert(!i.requested);
    i.update(c, false, false); assert(!i.requested);
    assert(!parse_config("yes", "hold", "1.25", "LeftShift", "LeftThumb", c) && !c.enabled);
    assert(!parse_config("true", "toggle", "1.5", "LeftShift", "LeftThumb", c) && !c.enabled);
    Vec v{1,0,2,0}, b{}, a{1,0,2,0}, e{};
    assert(extra(v,b,a,1.25f,e) && e.x == .25f && e.z == .5f && e.y == 0 && e.w == 0);
    assert(!extra(v,b,{.9f,0,2,0},1.25f,e));
    assert(!extra({1,.01f,0,0},b,{1,0,0,0},1.25f,e));
    assert(!extra({},b,b,1.25f,e));
    assert(!extra({std::numeric_limits<float>::quiet_NaN(),0,0,0},b,a,1.25f,e));
    assert(!extra(v,b,a,1.2f,e));
}
