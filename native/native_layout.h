#pragma once

#include "engine_compat_profile.h"

#ifdef FM27_XBOX_27_1_1
#include "xbox_27_1_1_rvas.h"
#elif defined(FM27_STEAM_27_1_1)
#include "steam_27_1_1_rvas.h"
#elif defined(FM27_STEAM_27_1)
#include "steam_27_1_rvas.h"
#endif

// Object offsets are independent of the absolute DLL locations above.
namespace native_layout {
#ifdef FM27_XBOX_27_1_1
constexpr bool xbox_27_1_1 = true;
#else
constexpr bool xbox_27_1_1 = false;
#endif
#ifdef FM27_STEAM_27_1_1
constexpr bool steam_27_1_1 = true;
#else
constexpr bool steam_27_1_1 = false;
#endif
#ifdef FM27_STEAM_27_1
constexpr bool steam_27_1 = true;
#else
constexpr bool steam_27_1 = false;
#endif

constexpr uintptr_t rva(uintptr_t value) {
#ifdef FM27_XBOX_27_1_1
    return xbox_27_1_1_rva(value);
#elif defined(FM27_STEAM_27_1_1)
    return steam_27_1_1_rva(value);
#elif defined(FM27_STEAM_27_1)
    return steam_27_1_rva(value);
#else
    return value;
#endif
}

constexpr unsigned manager(unsigned offset) { return offset + (steam_27_1 ? 8 : 0); }
constexpr unsigned player_input(unsigned offset) { return offset + (steam_27_1 ? 0x598 : 0); }
constexpr unsigned player_runtime(unsigned offset) { return offset + (steam_27_1 ? 0x5a0 : 0); }
constexpr unsigned player_statistics(unsigned offset) { return offset + (steam_27_1 ? 4 : 0); }
constexpr unsigned tactic_version = steam_27_1 ? 0x1b010000u : 0x1b000000u;
constexpr unsigned execution_build_stack = xbox_27_1_1 ? 0x118 : 0x138;
constexpr unsigned execution_sample_stack = steam_27_1 ? 0x108 : 0x88;
}
