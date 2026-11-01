#pragma once

#include "pluginterfaces/vst/vsttypes.h"

#include <cstddef>
#include <cstdint>

namespace PyDevices::MPVST {

constexpr Steinberg::Vst::ParamID kBypassParameter = 0;
constexpr Steinberg::Vst::ParamID kReloadParameter = 1;
constexpr Steinberg::Vst::ParamID kEngineReadyParameter = 2;
constexpr Steinberg::Vst::ParamID kEngineErrorParameter = 3;
// Doubles as the ProgramListID for the patch program list (see
// Controller::initialize): VST3 has no native "program change" input
// event, so a host maps an incoming MIDI Program Change message onto
// this kIsProgramChange-flagged parameter instead.
constexpr Steinberg::Vst::ParamID kPatchParameter = 4;
constexpr std::size_t kPatchCount = 128;
// Which MIDI channels the instance listens to: a list parameter whose first
// step is All and whose other sixteen are channels 1 to 16. Added after the
// MIDI controller set, so every parameter that existed before it keeps its
// index as well as its ID.
constexpr Steinberg::Vst::ParamID kMidiChannelParameter = 5;
constexpr Steinberg::Vst::ParamID kFirstMacroParameter = 100;
constexpr std::size_t kMacroParameterCount = 16;
// One controller set, for the selected channel or, on All, for every
// channel at once. Its IDs are the ones channel
// 1's set had when there was one set per channel, so automation recorded on
// channel 1's controllers still lands.
constexpr Steinberg::Vst::ParamID kFirstMidiParameter = 0x10000;
constexpr std::size_t kMidiChannelCount = 16;
constexpr std::size_t kMidiControllerCount = 130;
constexpr Steinberg::int32 kLegacyStateVersion = 1;
// Version 2 added the embedded script. Version 3 added the known-macro mask:
// without it a reload could not tell a macro the user had set to 0.5 from one
// nobody had touched, so it replayed all sixteen and overwrote whatever the
// script had chosen for itself.
constexpr Steinberg::int32 kScriptStateVersion = 2;
// Version 4 added the MIDI channel, 0-15, when one channel was the only
// choice. Version 5 stores the MIDI Channel step instead, so All can be
// saved. Anything older than 4 listens on All, as it did before there was a
// choice.
constexpr Steinberg::int32 kKnownMacroStateVersion = 3;
constexpr Steinberg::int32 kSingleChannelStateVersion = 4;
constexpr Steinberg::int32 kStateVersion = 5;
constexpr Steinberg::int32 kDefaultPipelineBlocks = 4;
constexpr Steinberg::int32 kMaximumPipelineBlocks = 16;
constexpr Steinberg::int32 kMaximumEmbeddedScriptBytes = 1024 * 1024;

constexpr bool isMacroParameter (Steinberg::Vst::ParamID id) noexcept
{
    return id >= kFirstMacroParameter &&
           id < kFirstMacroParameter + kMacroParameterCount;
}

constexpr std::size_t macroIndex (Steinberg::Vst::ParamID id) noexcept
{
    return static_cast<std::size_t> (id - kFirstMacroParameter);
}

constexpr Steinberg::Vst::ParamID midiParameterId (std::size_t controller) noexcept
{
    return kFirstMidiParameter + static_cast<Steinberg::Vst::ParamID> (controller);
}

constexpr bool decodeMidiParameter (Steinberg::Vst::ParamID id,
                                    std::uint16_t& controller) noexcept
{
    if (id < kFirstMidiParameter ||
        id - kFirstMidiParameter >= kMidiControllerCount)
        return false;
    controller = static_cast<std::uint16_t> (id - kFirstMidiParameter);
    return true;
}

// The MIDI Channel parameter's steps: 0 is All, 1-16 are channels 1-16.
constexpr std::uint32_t kMidiListenAll = 0;
constexpr std::uint32_t kMidiListenStepCount = kMidiChannelCount + 1U;

constexpr double midiListenToNormalized (std::uint32_t listen) noexcept
{
    return static_cast<double> (listen) /
           static_cast<double> (kMidiListenStepCount - 1U);
}

constexpr std::uint32_t midiListenFromNormalized (double normalized) noexcept
{
    const auto bounded = normalized < 0.0 ? 0.0 : (normalized > 1.0 ? 1.0 : normalized);
    return static_cast<std::uint32_t> (
        bounded * static_cast<double> (kMidiListenStepCount - 1U) + 0.5);
}

// Whether a step lets through events on a channel, 0-15.
constexpr bool midiListensTo (std::uint32_t listen, std::int32_t channel) noexcept
{
    return channel >= 0 && channel < static_cast<std::int32_t> (kMidiChannelCount) &&
           (listen == kMidiListenAll ||
            static_cast<std::uint32_t> (channel) + 1U == listen);
}

// The channel, 0-15, given to events that reach the plug-in without one of
// their own: controllers and program changes, which the host has already
// turned into parameter changes. On All the host merges every channel's into
// one, and they arrive as channel 1, which is where they arrived before
// there was a choice.
constexpr std::uint16_t midiListenEventChannel (std::uint32_t listen) noexcept
{
    return listen == kMidiListenAll ? std::uint16_t {0}
                                    : static_cast<std::uint16_t> (listen - 1U);
}

} // namespace PyDevices::MPVST
