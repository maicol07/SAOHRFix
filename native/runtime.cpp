#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <xinput.h>
#include <MinHook.h>
#include "sprint.hpp"
#include "activation.hpp"
#include <array>
#include <atomic>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <vector>

namespace {
using Ptr = std::uintptr_t;
using sprint::Vec;
using Physical = void(*)(void*, void*, float);
using Rate = float(*)(void*);
Ptr base;
HMODULE module;
Physical physical_original;
Rate rate_original;
sprint::Config config;
std::atomic<bool> started{}, stopped{}, requested{};
std::atomic<unsigned long long> applied{};
std::atomic<unsigned long long> animation_applied{};
std::mutex log_mutex;
std::ofstream log_file;
std::shared_mutex step_mutex;
struct Binding {
    Ptr pc{}, wrapper{}, kcc{}, ghost{}, owner{}, controller{}, channel{};
    int id = -1;
    bool operator==(const Binding& b) const {
        return pc==b.pc && wrapper==b.wrapper && kcc==b.kcc && ghost==b.ghost &&
            owner==b.owner && controller==b.controller && channel==b.channel && id==b.id;
    }
};
std::shared_ptr<const Binding> binding;
bool accepted = false; // Protected by step_mutex; latest completed physical update.
Binding accepted_binding;
struct Witness { Vec original{}, extra{}, before{}, after{}; };
std::array<Witness,16> witnesses{};
std::size_t witness_count=0;
bool diagnostics=false;
std::atomic<int> reason{};
std::atomic<std::uint32_t> rejected_parameter{};
sprint::Activation activation;
using Gate=sprint::Gate;
using Ui=sprint::Ui;
Ui ui_state();
void log(const char* event, unsigned long long value = 0) {
    std::lock_guard<std::mutex> lock(log_mutex);
    if (log_file) { log_file << "tick=" << GetTickCount64() << " event=" << event << " value=" << value << '\n'; log_file.flush(); }
}
template<class T> bool read(Ptr address, T& value) {
    SIZE_T count = 0;
    return address && ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(address),
        &value, sizeof(value), &count) && count == sizeof(value);
}
bool bytes(Ptr address, void* dst, std::size_t size) {
    SIZE_T count = 0;
    return address && ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(address), dst, size, &count) && count == size;
}
template<class T> bool equal(Ptr address, T expected) { T value{}; return read(address,value) && value==expected; }

Ui ui_state() {
    Ptr game{}, bridge{}, field{}, character{}, menu{};
    int state{}, field_state{}, again{};
    if (!read(base+0xAEA4A0,game) || !read(game+0x38,bridge) || !read(bridge,field) ||
        !read(bridge+0x18,character) || character!=field+0x5C8 ||
        !equal(field,base+0x82C268) || !equal(character,base+0x82C438) ||
        !read(character+0x28,state) || !read(character+0x30,menu) ||
        !read(field+0x28,field_state) || !read(character+0x28,again) || again!=state ||
        !equal(game+0x38,bridge) || !equal(bridge+0x18,character)) return Ui::unknown;
    // Only the observed field-active / character-inactive combination permits Sprint.
    return sprint::classify_ui(state,field_state,menu!=0);
}

bool resolve(Ptr pc, Binding& b) {
    b.pc = pc;
    Ptr global{}, manager{}, array{};
    int count{};
    if (!equal(pc,base+0x80AE08) || !read(pc+0x9FCC,b.id) || b.id<0 ||
        !read(base+0xB148B8,global) || !read(global,manager) || !read(manager+0x18,array) ||
        !read(manager+0x134,count) || count<=0 || count>32768) return false;
    std::vector<Ptr> entries(static_cast<std::size_t>(count));
    if (!bytes(array,entries.data(),entries.size()*sizeof(Ptr))) return false;
    int matches = 0;
    for (Ptr e : entries) if (e && equal(e,b.id)) { b.wrapper=e+0x10; ++matches; }
    if (matches!=1 || !read(b.wrapper+0x148,b.kcc) || !equal(b.kcc,base+0x879BD0) ||
        !equal(b.kcc+0xF0,b.wrapper) || !read(b.kcc+0x10,b.ghost) ||
        !equal(b.ghost,base+0x8C3F08) || !read(pc+0x4C0,b.owner) ||
        !read(b.owner+0x108,b.controller) || !read(b.controller+0x2F0,b.channel) ||
        !equal(b.channel,base+0x822AE8)) return false;
    return true;
}
bool current(const Binding& b) {
    Ptr global{}, manager{}, array{}, kcc{}, owner{}, controller{}, channel{};
    int count{};
    if (!equal(b.pc,base+0x80AE08) || !equal(b.pc+0x9FCC,b.id) || !equal(b.wrapper-0x10,b.id) ||
        !read(b.wrapper+0x148,kcc) || kcc!=b.kcc || !equal(kcc,base+0x879BD0) ||
        !equal(kcc+0xF0,b.wrapper) || !equal(kcc+0x10,b.ghost) ||
        !read(b.pc+0x4C0,owner) || owner!=b.owner || !read(owner+0x108,controller) || controller!=b.controller ||
        !read(controller+0x2F0,channel) || channel!=b.channel || !equal(channel,base+0x822AE8) ||
        !read(base+0xB148B8,global) || !read(global,manager) || !read(manager+0x18,array) ||
        !read(manager+0x134,count) || count<=0 || count>32768) return false;
    std::vector<Ptr> entries(static_cast<std::size_t>(count));
    return bytes(array,entries.data(),entries.size()*sizeof(Ptr)) &&
        std::count(entries.begin(),entries.end(),b.wrapper-0x10)==1;
}
bool run(const Binding& b) {
    std::uint32_t parameter{};
    return equal(b.pc+0xA9E0,base+0x80A8F0) && equal<std::uint8_t>(b.pc+0xA9E9,0xFF) &&
        equal<std::uint8_t>(b.pc+0xA9F0,0xFE) && equal<std::uint8_t>(b.pc+0xF8A6,1) &&
        equal<std::uint8_t>(b.pc+0xF8AD,0) && read(b.pc+0x9F24,parameter) &&
        (parameter==0x3E2BB98D || parameter==0x3E2D712B);
}
bool clip122(const Binding& b) {
    int index{}, count{}, again{};
    Ptr descriptors{};
    return read(b.channel+0x114,index) && read(b.channel+0xB8,count) && index>=0 && index<count && count<4096 &&
        read(b.channel+0xA8,descriptors) && equal<int>(descriptors+static_cast<Ptr>(index)*40+0x18,122) &&
        read(b.channel+0x114,again) && again==index;
}
// Read-only discovery. No vptr exchanges and no stored object is invoked.
std::shared_ptr<const Binding> discover() {
    SYSTEM_INFO si{}; GetSystemInfo(&si);
    std::vector<unsigned char> data(1024*1024);
    std::shared_ptr<const Binding> found;
    Ptr address = reinterpret_cast<Ptr>(si.lpMinimumApplicationAddress);
    MEMORY_BASIC_INFORMATION region{};
    while (!stopped.load() && VirtualQuery(reinterpret_cast<void*>(address),&region,sizeof(region))) {
        const Ptr end = reinterpret_cast<Ptr>(region.BaseAddress)+region.RegionSize;
        if (end<=address) break;
        if (region.State==MEM_COMMIT && region.Type==MEM_PRIVATE && !(region.Protect&PAGE_GUARD) &&
            (region.Protect==PAGE_READWRITE || region.Protect==PAGE_WRITECOPY)) {
            for (Ptr p=address; p<end; p+=data.size()) {
                const auto n=std::min<std::size_t>(end-p,data.size());
                if (!bytes(p,data.data(),n)) continue;
                for (std::size_t j=0;j+8<=n;j+=8) {
                    const Ptr candidate=p+j;
                    const Ptr buffer=reinterpret_cast<Ptr>(data.data());
                    if (candidate>=buffer && candidate<buffer+data.size()) continue;
                    Ptr v{}; std::memcpy(&v,data.data()+j,8);
                    if (v!=base+0x80AE08) continue;
                    Binding b;
                    if (resolve(p+j,b)) {
                        if (found) return {}; // Ambiguous active player: vanilla.
                        found=std::make_shared<Binding>(b);
                    }
                }
            }
        }
        address=end;
    }
    return found;
}
struct alignas(16) Transform { Vec basis[3]; Vec origin; };
struct alignas(16) Callback {
    Ptr vptr; float fraction; int group; int mask; unsigned char padding[0x3c];
    Ptr hit; unsigned char tail[8]; Ptr self; unsigned char pad[8]; Vec direction;
};
static_assert(sizeof(Vec)==16 && sizeof(Transform)==64);
static_assert(offsetof(Callback,hit)==0x50 && offsetof(Callback,self)==0x60 && offsetof(Callback,direction)==0x70);
enum class SweepResult { invalid, blocked, clear };
SweepResult preflight(const Binding& b, void* world, const Vec& movement) {
    Transform from{}, to{};
    Callback cb{};
    Ptr shape{}, handle{}, vt{};
    float margin{}, addition{}, allowed{};
    if (!read(b.ghost+0x10,from) || !read(b.kcc+0x18,shape) || !read(shape,vt) ||
        !read(b.ghost+0xC8,handle) || !read(handle+8,cb.group) ||
        !read(b.kcc+0x48,addition) || !read(reinterpret_cast<Ptr>(world)+0x54,allowed)) return SweepResult::invalid;
    using GetMargin=float(*)(void*); using SetMargin=void(*)(void*,float);
    GetMargin get{}; SetMargin set{};
    if (!read(vt+0x50,get) || !read(vt+0x48,set)) return SweepResult::invalid;
    margin=get(reinterpret_cast<void*>(shape));
    if (!std::isfinite(margin) || !std::isfinite(addition) || !std::isfinite(allowed)) return SweepResult::invalid;
    to=from; to.origin.x+=movement.x; to.origin.z+=movement.z;
    cb.vptr=base+0x8C55C0; cb.fraction=1; cb.self=b.ghost;
    cb.direction={-movement.x,0,-movement.z,0};
    using Sweep=void(*)(void*,void*,const Transform*,const Transform*,Callback*,float);
    set(reinterpret_cast<void*>(shape),margin+addition);
    activation.hit(Gate::preflight);
    reinterpret_cast<Sweep>(base+0x6F8890)(world,reinterpret_cast<void*>(shape),&from,&to,&cb,allowed);
    set(reinterpret_cast<void*>(shape),margin);
    return cb.hit==0 ? SweepResult::clear : SweepResult::blocked;
}
void physical(void* object, void* world, float dt) {
    activation.hit(Gate::physical);
    const auto b=std::atomic_load(&binding);
    if (!b || reinterpret_cast<Ptr>(object)!=b->kcc) { physical_original(object,world,dt); return; }
    activation.hit(Gate::player_physical);
    std::unique_lock<std::shared_mutex> lock(step_mutex,std::try_to_lock);
    if (!lock.owns_lock()) { activation.reject(Gate::lock_busy,requested.load()); physical_original(object,world,dt); return; }
    accepted=false;
    Vec input{}, before{}, after{}, additional{};
    std::uint8_t walk{};
    const bool captured=read(b->kcc+0x50,input) && read(b->ghost+0x40,before) && read(b->kcc+0xE3,walk);
    physical_original(object,world,dt); // The first action is always wholly native.
    const bool intent=requested.load();
    const auto pass=[intent](Gate gate,bool valid) {
        if (valid) activation.hit(gate); else { activation.reject(gate,intent); reason=static_cast<int>(gate)+1; }
        return valid;
    };
    if (!pass(Gate::stopped,!stopped.load()) || !pass(Gate::no_request,intent) ||
        !pass(Gate::capture,captured) || !pass(Gate::original_walk,walk==1) ||
        !pass(Gate::identity,current(*b))) return;
    if (!pass(Gate::selector,equal(b->pc+0xA9E0,base+0x80A8F0) &&
        equal<std::uint8_t>(b->pc+0xA9E9,0xFF) && equal<std::uint8_t>(b->pc+0xA9F0,0xFE))) return;
    if (!pass(Gate::motion,equal<std::uint8_t>(b->pc+0xF8A6,1) && equal<std::uint8_t>(b->pc+0xF8AD,0))) return;
    std::uint32_t parameter{};
    const bool parameter_valid=read(b->pc+0x9F24,parameter) && (parameter==0x3E2BB98D || parameter==0x3E2D712B);
    if (!parameter_valid) rejected_parameter=parameter;
    if (!pass(Gate::parameter,parameter_valid) || !pass(Gate::clip,clip122(*b))) return;
    if (!pass(Gate::displacement,read(b->ghost+0x40,after) && sprint::extra(input,before,after,config.factor,additional))) return;
    const auto ui=ui_state();
    if (!pass(Gate::ui_unknown,ui!=Ui::unknown) || !pass(Gate::ui_open,ui==Ui::closed)) return;
    const auto sweep=preflight(*b,world,additional);
    if (sweep==SweepResult::invalid) { activation.reject(Gate::preflight,intent); reason=static_cast<int>(Gate::preflight)+1; return; }
    if (!pass(Gate::collision,sweep==SweepResult::clear)) return;
    if (!pass(Gate::revalidation,!stopped.load() && requested.load() && current(*b) && run(*b) && clip122(*b) && ui_state()==Ui::closed)) return;
    using SetWalk=void(*)(void*,const Vec*);
    reinterpret_cast<SetWalk>(base+0x72A5F0)(object,&additional);
    physical_original(object,world,0.f);
    activation.hit(Gate::second_wrapper);
    if (diagnostics && witness_count<witnesses.size()) {
        Vec end{};
        if (read(b->ghost+0x40,end)) witnesses[witness_count++]={input,additional,after,end};
    }
    accepted_binding=*b; accepted=true; ++applied; reason=0;
    activation.hit(Gate::accepted);
}
float rate(void* channel) {
    activation.hit(Gate::animation_getter);
    const float original=rate_original(channel);
    if (stopped.load() || !requested.load() || original!=1.f ||
        reinterpret_cast<Ptr>(__builtin_return_address(0))!=base+0x2888CC) return original;
    std::shared_lock<std::shared_mutex> lock(step_mutex,std::try_to_lock);
    if (!lock.owns_lock() || !accepted) return original;
    const auto b=std::atomic_load(&binding);
    if (!b || !(*b==accepted_binding) || reinterpret_cast<Ptr>(channel)!=b->channel ||
        !current(*b) || !run(*b) || !clip122(*b) || ui_state()!=Ui::closed) return original;
    ++animation_applied;
    activation.hit(Gate::animation);
    return original*config.factor;
}
std::string ini(const std::filesystem::path& path, const char* section, const char* key, const char* fallback) {
    char value[256]{};
    GetPrivateProfileStringA(section,key,fallback,value,sizeof(value),path.string().c_str());
    return value;
}
bool supported(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);
    std::vector<unsigned char> image((std::istreambuf_iterator<char>(file)),{});
    BCRYPT_ALG_HANDLE algorithm{}; BCRYPT_HASH_HANDLE hash{};
    if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0) return false;
    std::array<unsigned char,32> digest{};
    bool ok=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)>=0;
    if (ok) ok=BCryptHashData(hash,image.data(),static_cast<ULONG>(image.size()),0)>=0 &&
        BCryptFinishHash(hash,digest.data(),static_cast<ULONG>(digest.size()),0)>=0;
    if (hash) BCryptDestroyHash(hash); BCryptCloseAlgorithmProvider(algorithm,0);
    const unsigned char expected[32]={0x19,0x23,0xf0,0xd8,0xd2,0xca,0xd5,0x59,0xd6,0xad,0x6e,0x00,0x1a,0xf5,0x4e,0xa5,0xea,0x5a,0xa7,0x01,0x71,0x32,0x3f,0x42,0xd4,0xe1,0xfa,0x3d,0x63,0x69,0x9e,0x43};
    if (!ok || std::memcmp(digest.data(),expected,32)!=0 || base!=0x140000000) return false;
    const auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(image.data());
    const auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS64*>(image.data()+dos->e_lfanew);
    const auto* sections=IMAGE_FIRST_SECTION(nt);
    for (const auto range : {std::pair<Ptr,std::size_t>{0x58D340,0x400},{0x6F8890,0x400},{0x6C6C80,17},{0x2888B0,32},{0x72A5F0,64},
        {0x37A2C0,9},{0x375870,121},{0x1D2630,32}}) {
        bool match=false;
        for (unsigned s=0;s<nt->FileHeader.NumberOfSections;++s) {
            const auto& sec=sections[s];
            if (range.first>=sec.VirtualAddress && range.first+range.second<=sec.VirtualAddress+sec.SizeOfRawData) {
                std::vector<unsigned char> live(range.second);
                match=bytes(base+range.first,live.data(),live.size()) &&
                    std::memcmp(live.data(),image.data()+sec.PointerToRawData+range.first-sec.VirtualAddress,live.size())==0;
            }
        }
        if (!match) return false;
    }
    return true;
}
// MinHook 1.3.4 copies the first 10 bytes here, then emits a 14-byte jump.
// Describe only the allocation actually executed in that trampoline.
bool register_unwind() {
    const Ptr t=reinterpret_cast<Ptr>(physical_original);
    unsigned char code[24]{};
    if (!bytes(t,code,sizeof(code)) || std::memcmp(code,reinterpret_cast<void*>(base+0x58D340),10)!=0 ||
        code[10]!=0xFF || code[11]!=0x25) return false;
    struct Metadata { RUNTIME_FUNCTION function; unsigned char unwind[8]; };
    for (Ptr distance=0x10000;distance<0x1000000;distance+=0x10000) {
        const Ptr hint=(t&~Ptr(0xFFFF))-distance;
        auto* m=static_cast<Metadata*>(VirtualAlloc(reinterpret_cast<void*>(hint),4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
        if (!m) continue;
        const Ptr address=reinterpret_cast<Ptr>(m);
        const Ptr origin=std::min(address,t);
        m->function={static_cast<DWORD>(t-origin),static_cast<DWORD>(t-origin+24),
            static_cast<DWORD>(address+offsetof(Metadata,unwind)-origin)};
        const unsigned char unwind[8]={1,10,2,0,10,1,35,0};
        std::memcpy(m->unwind,unwind,sizeof(unwind));
        DWORD old{};
        if (!VirtualProtect(m,4096,PAGE_READONLY,&old)) return false;
        return RtlAddFunctionTable(&m->function,1,origin)!=FALSE;
    }
    return false;
}
DWORD WINAPI worker(void*) {
    wchar_t path[MAX_PATH]{}; GetModuleFileNameW(module,path,MAX_PATH);
    const auto directory=std::filesystem::path(path).parent_path();
    log_file.open(directory/L"SAOHRFix.log",std::ios::app);
    log("initializing_experimental");
    const auto settings=directory/L"SAOHRFix.ini";
    if (!sprint::parse_config(ini(settings,"sprint","enabled","false"),ini(settings,"sprint","mode","hold"),
        ini(settings,"sprint","factor","1.25"),ini(settings,"sprint.keyboard","key","LeftShift"),
        ini(settings,"sprint.controller","button","LeftThumb"),config)) { log("invalid_config_vanilla"); return 0; }
    const auto level=ini(settings,"logging","level","info");
    if (level!="info") { log("unsupported_logging_level_vanilla"); return 0; }
    const auto diagnostic=ini(settings,"diagnostics","enabled","false");
    if (diagnostic!="true" && diagnostic!="false") { log("invalid_diagnostics_vanilla"); return 0; }
    diagnostics=diagnostic=="true";
    const auto activation_seconds=ini(settings,"diagnostics","activation_seconds","0");
#if defined(SAOHRFIX_DEVELOPMENT)
    if (activation_seconds!="0" && activation_seconds!="3") { log("invalid_dev_activation_vanilla"); return 0; }
    const bool development_request=diagnostics && activation_seconds=="3";
    bool development_used=false;
    ULONGLONG development_until=0;
#else
    if (activation_seconds!="0") { log("development_activation_unavailable_vanilla"); return 0; }
#endif
    if (!config.enabled) { log("disabled_no_hooks"); return 0; }
    GetModuleFileNameW(nullptr,path,MAX_PATH); base=reinterpret_cast<Ptr>(GetModuleHandleW(nullptr));
    if (!supported(path)) { log("unsupported_build_or_modified_bindings_vanilla"); return 0; }
    log("build_verified");
    log("hook_init_begin");
    const auto init=MH_Initialize();
    log("hook_init_result",init);
    if (init!=MH_OK) { log("hook_init_failed_vanilla",init); return 0; }
    const auto physics=MH_CreateHook(reinterpret_cast<void*>(base+0x58D340),reinterpret_cast<void*>(&physical),reinterpret_cast<void**>(&physical_original));
    log("physical_hook_prepare_result",physics);
    if (physics!=MH_OK) { log("physical_hook_prepare_failed_vanilla",physics); return 0; }
    const auto animation=MH_CreateHook(reinterpret_cast<void*>(base+0x6C6C80),reinterpret_cast<void*>(&rate),reinterpret_cast<void**>(&rate_original));
    log("animation_hook_prepare_result",animation);
    if (animation!=MH_OK) { log("animation_hook_prepare_failed_vanilla",animation); return 0; }
    if (!register_unwind()) { log("unwind_prepare_failed_vanilla",GetLastError()); return 0; }
    if (MH_QueueEnableHook(reinterpret_cast<void*>(base+0x58D340))!=MH_OK || MH_QueueEnableHook(reinterpret_cast<void*>(base+0x6C6C80))!=MH_OK || MH_ApplyQueued()!=MH_OK) {
        stopped=true; log("hook_enable_failed_forward_only"); return 0;
    }
    log("hooks_installed_resident");
    sprint::Input input;
    unsigned previous_pads=0;
    int previous_reason=-1;
    unsigned previous_input=~0u;
    Ui previous_ui=Ui::unknown;
    std::size_t emitted=0;
    unsigned summaries=0;
    std::uint32_t previous_parameter=0;
    ULONGLONG next_scan=0, next_summary=0, next_reason=0;
    std::shared_ptr<const Binding> last;
    while (!stopped.load()) {
        const auto now=GetTickCount64();
        if (now>=next_scan && (!last || !current(*last))) {
            const auto found=discover();
            std::atomic_store(&binding,found);
            last=found; next_scan=GetTickCount64()+1000;
            requested=false; input={};
            log(found?"reacquired_player_physics_id":"no_unique_player_vanilla",found?static_cast<unsigned>(found->id):0);
            if (found) {
                log("player",found->pc); log("wrapper",found->wrapper); log("kcc",found->kcc);
                log("animation_channel",found->channel);
            }
        }
        const HWND foreground=GetForegroundWindow();
        HWND game{}; const bool focused=read(base+0xC59F08,game) && game==foreground && !IsIconic(game);
        const bool keyboard=(GetAsyncKeyState(VK_LSHIFT)&0x8000)!=0;
        bool thumb=false; unsigned pads=0;
        for (DWORD j=0;j<XUSER_MAX_COUNT;++j) {
            XINPUT_STATE state{};
            if (XInputGetState(j,&state)==ERROR_SUCCESS) {
                pads|=1u<<j; thumb|=(state.Gamepad.wButtons&XINPUT_GAMEPAD_LEFT_THUMB)!=0;
            }
        }
        const bool old=requested.load();
        const auto ui=ui_state();
        if (ui!=previous_ui) { log("ui_state",static_cast<unsigned>(ui)); previous_ui=ui; }
        const unsigned input_flags=(focused?1u:0u)|(keyboard?2u:0u)|(thumb?4u:0u)|(pads<<8);
        if (input_flags!=previous_input) { log("input_flags",input_flags); previous_input=input_flags; }
        // A controller connection transition must not cancel a held keyboard key.
        input.update(config,focused && last && ui==Ui::closed && (keyboard || pads==previous_pads),keyboard||thumb);
        previous_pads=pads;
        bool wanted=input.requested;
#if defined(SAOHRFIX_DEVELOPMENT)
        if (development_request && !development_used && focused && last && ui==Ui::closed &&
            current(*last) && equal<std::uint8_t>(last->pc+0xA9E9,0xFF) && equal<std::uint8_t>(last->pc+0xA9F0,0xFE) &&
            equal<std::uint8_t>(last->pc+0xF8A6,1) && equal<std::uint8_t>(last->pc+0xF8AD,0) && clip122(*last)) {
            development_used=true; development_until=now+3000; log("development_request_begin");
        }
        if (development_until) {
            if (now>=development_until || !focused || !last || ui!=Ui::closed) {
                development_until=0; log("development_request_end");
            } else wanted=true;
        }
#endif
        requested=wanted;
        if (keyboard) activation.hit(Gate::keyboard);
        if (thumb) activation.hit(Gate::controller);
        if (requested.load()) activation.hit(Gate::request);
        if (old!=requested.load()) log(requested.load()?"sprint_requested":"sprint_released");
        const auto bad_parameter=rejected_parameter.load();
        if (bad_parameter!=previous_parameter) { log("rejected_parameter_bits",bad_parameter); previous_parameter=bad_parameter; }
        const int why=reason.load();
        if (why!=previous_reason && now>=next_reason) {
            log("eligibility_reason",static_cast<unsigned>(why)); previous_reason=why; next_reason=now+1000;
        }
        if (now>=next_summary) {
            log("accepted_extra_total",applied.load()); log("animation_corrected_total",animation_applied.load());
            next_summary=now+5000;
            if (diagnostics && summaries++<120) {
                std::lock_guard<std::mutex> output(log_mutex);
                const auto first=activation.first.load();
                log_file << "event=activation_snapshot first_exclusion=" <<
                    (first<static_cast<unsigned>(Gate::count)?sprint::gate_names[first]:"none");
                for (unsigned j=0;j<static_cast<unsigned>(Gate::count);++j)
                    log_file << ' ' << sprint::gate_names[j] << "=" << activation.reached[j].load()
                        << '/' << activation.excluded[j].load();
                log_file << '\n'; log_file.flush();
            }
        }
        if (diagnostics) {
            std::shared_lock<std::shared_mutex> lock(step_mutex,std::try_to_lock);
            if (lock.owns_lock()) while (emitted<witness_count) {
                const auto& w=witnesses[emitted++];
                std::lock_guard<std::mutex> output(log_mutex);
                log_file << "event=extra_witness index=" << emitted << " native_x=" << w.original.x
                    << " native_z=" << w.original.z << " extra_x=" << w.extra.x << " extra_y=" << w.extra.y
                    << " extra_z=" << w.extra.z << " actual_dx=" << w.after.x-w.before.x
                    << " actual_dy=" << w.after.y-w.before.y << " actual_dz=" << w.after.z-w.before.z << '\n';
                log_file.flush();
            }
        }
        Sleep(8);
    }
    requested=false;
    log("stopped_forward_only_until_process_exit");
    return 0;
}
}
extern "C" __declspec(dllexport) void InitializeASI() {
    if (started.exchange(true)) return;
    HMODULE pinned{};
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCWSTR>(&InitializeASI),&pinned)) return;
    HANDLE thread=CreateThread(nullptr,0,&worker,nullptr,0,nullptr);
    if (thread) CloseHandle(thread);
}
extern "C" __declspec(dllexport) void StopSAOHRFix() { stopped=true; requested=false; }
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason_code,LPVOID) {
    if (reason_code==DLL_PROCESS_ATTACH) { module=instance; DisableThreadLibraryCalls(instance); }
    return TRUE;
}
