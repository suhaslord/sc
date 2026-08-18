#!/usr/bin/env python3
"""Verify that generated HM_APP interfaces match the checked-in COSMOS contract.

Run after ``prepare_hm_app.py`` has injected HM_APP into a cFS checkout:

    python3 cfs_health_monitor/verify_cosmos_contract.py cFS

This is intentionally a static contract check. It does not claim a live network
round-trip through OpenC3/COSMOS.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"required contract file is missing: {path}")
    return path.read_text()


def require_regex(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE) is None:
        raise RuntimeError(f"contract mismatch: {label}")


def require_absent(text: str, value: str, label: str) -> None:
    if value in text:
        raise RuntimeError(f"contract mismatch: {label}")


def require_in_order(text: str, values: list[str], label: str) -> None:
    cursor = 0
    for value in values:
        position = text.find(value, cursor)
        if position < 0:
            raise RuntimeError(f"contract mismatch: {label}: missing/out-of-order {value!r}")
        cursor = position + len(value)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_cosmos_contract.py <cFS-root>")

    cfs_root = Path(sys.argv[1]).resolve()
    project_root = Path(__file__).resolve().parent
    hm_root = cfs_root / "apps" / "hm_app"

    topic_ids = read(hm_root / "fsw" / "inc" / "hm_app_topicids.h")
    msgdefs = read(hm_root / "config" / "default_hm_app_msgdefs.h")
    fcncodes = read(hm_root / "config" / "default_hm_app_fcncode_values.h")
    interface_cfg = read(hm_root / "fsw" / "inc" / "hm_app_interface_cfg.h")

    cosmos_root = project_root / "cosmos"
    msg_list = read(cosmos_root / "hm_app_msg_list_patch.rb")
    cmd_def = read(cosmos_root / "hm_app_cmd_def.txt")
    tlm_def = read(cosmos_root / "hm_app_tlm_def.txt")

    # cFS topic IDs generated for HM_APP.
    require_regex(topic_ids, r"DEFAULT_HM_APP_MISSION_CMD_TOPICID\s+0xE2\b", "command topic ID must be 0xE2")
    require_regex(topic_ids, r"DEFAULT_HM_APP_MISSION_SEND_HK_TOPICID\s+0xE3\b", "send-HK topic ID must be 0xE3")
    require_regex(topic_ids, r"DEFAULT_HM_APP_MISSION_HK_TLM_TOPICID\s+0xE3\b", "HK telemetry topic ID must be 0xE3")

    # Command function codes inherited from sample_app and used by HM_APP.
    require_regex(fcncodes, r"HM_APP_NOOP_CC\s*=\s*0\b", "NOOP function code must be 0")
    require_regex(fcncodes, r"HM_APP_RESET_COUNTERS_CC\s*=\s*1\b", "reset function code must be 1")
    require_regex(fcncodes, r"HM_APP_DISPLAY_PARAM_CC\s*=\s*3\b", "monitor-control function code must be 3")
    require_regex(interface_cfg, r"HM_APP_STRING_VAL_LEN\s+10\b", "control NOTE/string width must be 10 bytes")

    # Generated C payloads. Explicit reserved bytes make the HK wire contract
    # deterministic for the COSMOS definition rather than relying on implicit
    # compiler padding.
    require_in_order(
        msgdefs,
        [
            "uint8 CommandCounter;",
            "uint8 CommandErrorCounter;",
            "uint8 AlignmentPad[2];",
            "uint32 CurrentSample;",
            "uint32 Threshold;",
            "uint8 AlarmActive;",
            "uint8 Reserved[3];",
        ],
        "HM_APP housekeeping payload",
    )
    require_in_order(
        msgdefs,
        [
            "uint32 ValU32;",
            "int16 ValI16;",
            "char ValString[HM_APP_STRING_VAL_LEN];",
        ],
        "HM_APP monitor-control payload",
    )

    # cFS topic IDs map to the expected command/telemetry MIDs in the COSMOS
    # message list used by nasa/cfs-cosmos-plugin.
    require_regex(msg_list, r"base_stream_id:\s*0x18E2\b", "COSMOS HM command MID must be 0x18E2")
    require_regex(msg_list, r"base_stream_id:\s*0x18E3\b", "COSMOS send-HK MID must be 0x18E3")
    require_regex(msg_list, r"base_stream_id:\s*0x08E3\b", "COSMOS HK telemetry MID must be 0x08E3")
    require_absent(msg_list, "HM_APP_CMD_PROCESS", "packet list must not advertise an undefined PROCESS command")
    for packet_name in ("HM_APP_CMD_NOOP", "HM_APP_CMD_RESET_COUNTERS", "HM_APP_CMD_CONTROL"):
        if packet_name not in msg_list:
            raise RuntimeError(f"contract mismatch: COSMOS packet list missing {packet_name}")

    # COSMOS command definitions must match the generated function codes and
    # HM_APP_DisplayParamCmd payload.
    require_regex(cmd_def, r"cfs_cmd_hdr\(target_name,\s*'HM_APP_CMD_NOOP',\s*0\b", "COSMOS NOOP function code")
    require_regex(cmd_def, r"cfs_cmd_hdr\(target_name,\s*'HM_APP_CMD_RESET_COUNTERS',\s*1\b", "COSMOS reset function code")
    require_regex(cmd_def, r"cfs_cmd_hdr\(target_name,\s*'HM_APP_CMD_CONTROL',\s*3\b", "COSMOS control function code")
    require_regex(cmd_def, r"APPEND_PARAMETER\s+VALUE\s+32\s+UINT\b", "COSMOS VALUE must be uint32")
    require_regex(cmd_def, r"APPEND_PARAMETER\s+ACTION\s+16\s+INT\b", "COSMOS ACTION must be int16")
    require_regex(cmd_def, r"APPEND_PARAMETER\s+NOTE\s+80\s+STRING\b", "COSMOS NOTE must be 10 bytes")

    # COSMOS housekeeping fields must mirror the explicit generated C layout.
    require_in_order(
        tlm_def,
        [
            "APPEND_ITEM COMMAND_COUNTER 8 UINT",
            "APPEND_ITEM COMMAND_ERROR_COUNTER 8 UINT",
            "APPEND_ITEM ALIGNMENT_PAD 16 UINT",
            "APPEND_ITEM CURRENT_SAMPLE 32 UINT",
            "APPEND_ITEM THRESHOLD 32 UINT",
            "APPEND_ITEM ALARM_ACTIVE 8 UINT",
            "APPEND_ITEM RESERVED 24 UINT",
        ],
        "COSMOS housekeeping telemetry layout",
    )

    print("cFS ↔ COSMOS contract verified")


if __name__ == "__main__":
    main()
