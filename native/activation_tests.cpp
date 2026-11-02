#include "activation.hpp"
#include "sprint.hpp"
#include <cassert>
int main() {
    using sprint::Ui;
    assert(sprint::classify_ui(0,5,false)==Ui::closed);
    assert(sprint::classify_ui(5,0,true)==Ui::open);
    for (int state=1;state<=8;++state) assert(sprint::classify_ui(state,5,false)==Ui::open);
    assert(sprint::classify_ui(0,5,true)==Ui::unknown);
    assert(sprint::classify_ui(0,0,false)==Ui::unknown);
    assert(sprint::classify_ui(-1,5,false)==Ui::unknown);
    assert(sprint::classify_ui(9,5,false)==Ui::unknown);
    sprint::Activation a;
    a.hit(sprint::Gate::physical);
    a.reject(sprint::Gate::no_request,false);
    assert(a.first==static_cast<unsigned>(sprint::Gate::count));
    a.reject(sprint::Gate::selector,true);
    a.reject(sprint::Gate::clip,true);
    assert(a.first==static_cast<unsigned>(sprint::Gate::selector));
    assert(a.reached[static_cast<unsigned>(sprint::Gate::physical)]==1);
    assert(a.excluded[static_cast<unsigned>(sprint::Gate::clip)]==1);
    sprint::Config config; config.enabled=true;
    sprint::Input input;
    input.update(config,true,false);
    input.update(config,true,true);
    assert(input.requested); // Keyboard availability does not depend on XInput.
    input.update(config,true,false); assert(!input.requested);
}
