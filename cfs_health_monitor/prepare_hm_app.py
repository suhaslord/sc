#!/usr/bin/env python3
"""Create a Health Monitor cFS app from NASA sample_app inside a cFS bundle.

This script intentionally starts from the exact sample_app revision checked out by
that cFS bundle, then applies a small, reviewable set of changes.  This keeps the
app aligned with the cFS version being compile-validated.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def replace_text(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_hm_app.py <cFS-root>")

    cfs_root = Path(sys.argv[1]).resolve()
    source = cfs_root / "apps" / "sample_app"
    target = cfs_root / "apps" / "hm_app"

    if not source.exists():
        raise RuntimeError(f"sample_app not found at {source}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    # Rename symbols/text first.  Binary files are ignored.
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        text = (
            text.replace("SAMPLE_APP", "HM_APP")
            .replace("Sample App", "Health Monitor")
            .replace("Sample app", "Health monitor")
            .replace("sample_app", "hm_app")
        )
        path.write_text(text)

    # Rename files/directories after contents so CMake/header references match.
    for path in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        name = path.name.replace("sample_app", "hm_app").replace("SAMPLE_APP", "HM_APP")
        if name != path.name:
            path.rename(path.with_name(name))

    # Give HM_APP its own Software Bus topics rather than colliding with sample_app.
    topic_ids = target / "fsw" / "inc" / "hm_app_topicids.h"
    replace_text(topic_ids, "DEFAULT_HM_APP_MISSION_CMD_TOPICID     0x82", "DEFAULT_HM_APP_MISSION_CMD_TOPICID     0xE2")
    replace_text(topic_ids, "DEFAULT_HM_APP_MISSION_SEND_HK_TOPICID 0x83", "DEFAULT_HM_APP_MISSION_SEND_HK_TOPICID 0xE3")
    replace_text(topic_ids, "DEFAULT_HM_APP_MISSION_HK_TLM_TOPICID  0x83", "DEFAULT_HM_APP_MISSION_HK_TLM_TOPICID  0xE3")

    # Add monitor state to the application data structure.
    app_h = target / "fsw" / "src" / "hm_app.h"
    replace_text(
        app_h,
        "    uint8 CommandErrorCounter;\n",
        "    uint8 CommandErrorCounter;\n\n"
        "    /* Health-monitor state */\n"
        "    uint32 Threshold;\n"
        "    uint32 CurrentSample;\n"
        "    uint8  AlarmActive;\n",
    )

    # Publish monitor state in housekeeping telemetry.
    msgdefs = target / "config" / "default_hm_app_msgdefs.h"
    replace_text(
        msgdefs,
        "    uint8 CommandErrorCounter;\n} HM_APP_HkTlm_Payload_t;",
        "    uint8  CommandErrorCounter;\n"
        "    uint32 CurrentSample;\n"
        "    uint32 Threshold;\n"
        "    uint8  AlarmActive;\n"
        "} HM_APP_HkTlm_Payload_t;",
    )

    # Establish deterministic startup state.
    app_c = target / "fsw" / "src" / "hm_app.c"
    replace_text(
        app_c,
        "    HM_APP_Data.RunStatus = CFE_ES_RunStatus_APP_RUN;\n",
        "    HM_APP_Data.RunStatus     = CFE_ES_RunStatus_APP_RUN;\n"
        "    HM_APP_Data.Threshold     = 100;\n"
        "    HM_APP_Data.CurrentSample = 0;\n"
        "    HM_APP_Data.AlarmActive   = 0;\n",
    )

    cmds = target / "fsw" / "src" / "hm_app_cmds.c"
    replace_text(
        cmds,
        "    HM_APP_Data.HkTlm.Payload.CommandErrorCounter = HM_APP_Data.CommandErrorCounter;\n"
        "    HM_APP_Data.HkTlm.Payload.CommandCounter      = HM_APP_Data.CommandCounter;\n",
        "    HM_APP_Data.HkTlm.Payload.CommandErrorCounter = HM_APP_Data.CommandErrorCounter;\n"
        "    HM_APP_Data.HkTlm.Payload.CommandCounter      = HM_APP_Data.CommandCounter;\n"
        "    HM_APP_Data.HkTlm.Payload.CurrentSample       = HM_APP_Data.CurrentSample;\n"
        "    HM_APP_Data.HkTlm.Payload.Threshold           = HM_APP_Data.Threshold;\n"
        "    HM_APP_Data.HkTlm.Payload.AlarmActive         = HM_APP_Data.AlarmActive;\n",
    )

    # Re-purpose the sample payload command into two explicit health-monitor
    # operations selected by ValI16: 0=set threshold, 1=inject sample.
    signature = "CFE_Status_t HM_APP_DisplayParamCmd(const HM_APP_DisplayParamCmd_t *Msg)\n{"
    text = cmds.read_text()
    start = text.find(signature)
    if start < 0:
        raise RuntimeError("HM_APP_DisplayParamCmd signature not found")
    # This handler is the last function in sample_app_cmds.c.
    replacement = r'''CFE_Status_t HM_APP_DisplayParamCmd(const HM_APP_DisplayParamCmd_t *Msg)
{
    const uint32 value  = Msg->Payload.ValU32;
    const int16  action = Msg->Payload.ValI16;

    HM_APP_Data.CommandCounter++;

    if (action == 0)
    {
        HM_APP_Data.Threshold = value;
        HM_APP_Data.AlarmActive = (HM_APP_Data.CurrentSample > HM_APP_Data.Threshold) ? 1 : 0;
        CFE_EVS_SendEvent(HM_APP_VALUE_INF_EID,
                          CFE_EVS_EventType_INFORMATION,
                          "HM_APP: threshold set to %lu",
                          (unsigned long)HM_APP_Data.Threshold);
    }
    else if (action == 1)
    {
        HM_APP_Data.CurrentSample = value;
        HM_APP_Data.AlarmActive = (HM_APP_Data.CurrentSample > HM_APP_Data.Threshold) ? 1 : 0;

        if (HM_APP_Data.AlarmActive != 0)
        {
            CFE_EVS_SendEvent(HM_APP_VALUE_INF_EID,
                              CFE_EVS_EventType_WARNING,
                              "HM_APP: alarm sample=%lu threshold=%lu",
                              (unsigned long)HM_APP_Data.CurrentSample,
                              (unsigned long)HM_APP_Data.Threshold);
        }
        else
        {
            CFE_EVS_SendEvent(HM_APP_VALUE_INF_EID,
                              CFE_EVS_EventType_INFORMATION,
                              "HM_APP: sample=%lu threshold=%lu nominal",
                              (unsigned long)HM_APP_Data.CurrentSample,
                              (unsigned long)HM_APP_Data.Threshold);
        }
    }
    else
    {
        HM_APP_Data.CommandErrorCounter++;
        CFE_EVS_SendEvent(HM_APP_VALUE_INF_EID,
                          CFE_EVS_EventType_ERROR,
                          "HM_APP: invalid monitor action %d",
                          (int)action);
    }

    return CFE_SUCCESS;
}
'''
    cmds.write_text(text[:start] + replacement)

    # Build the new app on every CPU in the sample mission.
    targets = cfs_root / "sample_defs" / "targets.cmake"
    replace_text(
        targets,
        "list(APPEND MISSION_GLOBAL_APPLIST sample_app sample_lib)",
        "list(APPEND MISSION_GLOBAL_APPLIST sample_app sample_lib hm_app)",
    )

    print(f"Prepared {target}")


if __name__ == "__main__":
    main()
