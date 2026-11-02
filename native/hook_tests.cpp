#include <MinHook.h>
#include <cassert>
using Function=int(*)(int);
Function original;
__declspec(noinline) int target(int value) { volatile int input=value; return input+7; }
int detour(int value) { return original(value)+1; }
int main() {
    assert(MH_Initialize()==MH_OK);
    assert(MH_CreateHook(reinterpret_cast<void*>(&target),reinterpret_cast<void*>(&detour),reinterpret_cast<void**>(&original))==MH_OK);
    Function volatile invoke=&target;
    assert(invoke(1)==8);
    assert(MH_EnableHook(reinterpret_cast<void*>(&target))==MH_OK);
    assert(invoke(1)==9);
    assert(MH_DisableHook(reinterpret_cast<void*>(&target))==MH_OK);
    assert(invoke(1)==8);
    assert(MH_RemoveHook(reinterpret_cast<void*>(&target))==MH_OK);
    assert(MH_Uninitialize()==MH_OK);
}
