-- Open each macro-default project, render three seconds, quit.
-- Named __startup.lua while it runs and removed afterwards by the harness.
local WORKDIR = os.getenv("MPVST_MACRO_WORKDIR")
local SEP = os.getenv("MPVST_MACRO_SEP") or "/"
local cases = {"A_v3_unknown", "B_v3_known", "C_v2_legacy"}
local report = io.open(WORKDIR .. SEP .. "report.txt", "w")

local function say(line)
    report:write(line .. "\n")
    report:flush()
end

local function render(name)
    reaper.Main_openProject("noprompt:" .. WORKDIR .. SEP .. name .. ".RPP")
    -- The sidecar needs a moment to start and run the script before the
    -- render pulls its first block; a render that outruns it is silence.
    local t0 = reaper.time_precise()
    while reaper.time_precise() - t0 < 4.0 do end
    reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, true)
    reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)
    reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", 0.0, true)
    reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", 3.0, true)
    reaper.GetSetProjectInfo(0, "RENDER_TAILFLAG", 0, true)
    reaper.GetSetProjectInfo(0, "RENDER_SRATE", 48000, true)
    reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 2, true)
    reaper.GetSetProjectInfo(0, "RENDER_ADDTOPROJ", 0, true)
    reaper.GetSetProjectInfo_String(0, "RENDER_FILE", WORKDIR, true)
    reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", name, true)
    reaper.Main_OnCommand(41824, 0)
    say("RENDERED " .. name)
end

for _, name in ipairs(cases) do
    render(name)
end
say("DONE")
report:close()
reaper.Main_OnCommand(40004, 0)
