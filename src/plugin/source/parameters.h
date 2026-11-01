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
// Which of the 16 MIDI channels the instance listens to: a list parameter
// whose steps are channels 1 to 16. Added after the MIDI controller set, so
// every parameter that existed before it keeps its index as well as its ID.
constexpr Steinberg::Vst::ParamID kMidiChannelParameter = 5;
constexpr Steinberg::Vst::ParamID kFirstMacroParameter = 100;
constexpr std::size_t kMacroParameterCount = 16;
// One controller set, for the selected channel. Its IDs are the ones channel
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
// Version 4 added the MIDI channel. Anything older listens on channel 1.
constexpr Steinberg::int32 kKnownMacroStateVersion = 3;
constexpr Steinberg::int32 kStateVersion = 4;
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

// The list parameter's normalized value for a channel index 0-15, and back.
constexpr double midiChannelToNormalized (std::size_t channel) noexcept
{
    return static_cast<double> (channel) /
           static_cast<double> (kMidiChannelCount - 1U);
}

constexpr std::uint16_t midiChannelFromNormalized (double normalized) noexcept
{
    const auto bounded = normalized < 0.0 ? 0.0 : (normalized > 1.0 ? 1.0 : normalized);
    return static_cast<std::uint16_t> (
        bounded * static_cast<double> (kMidiChannelCount - 1U) + 0.5);
}

} // namespace PyDevices::MPVST
