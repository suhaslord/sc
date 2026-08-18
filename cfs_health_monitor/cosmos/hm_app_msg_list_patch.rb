# Add these entries to $CFS_CMD_TLM_LIST in
# targets/CFS/lib/cfs_cmd_tlm_list.rb in nasa/cfs-cosmos-plugin.
#
# The IDs intentionally use a separate topic pair from SAMPLE_APP:
#   command MID    0x18E2
#   send-HK MID    0x18E3
#   housekeeping   0x08E3

"HM_APP_CMD" => FswMsgInfo.new(
    base_stream_id: 0x18E2,
    packet_names: [
        "HM_APP_CMD_NOOP",
        "HM_APP_CMD_RESET_COUNTERS",
        "HM_APP_CMD_PROCESS",
        "HM_APP_CMD_CONTROL",
    ]
),
"HM_APP_SEND_HK_CMD" => FswMsgInfo.new(
    base_stream_id: 0x18E3,
    packet_names: [
        "HM_APP_SEND_HK_CMD",
    ]
),
"HM_APP_HK" => FswMsgInfo.new(
    base_stream_id: 0x08E3,
    packet_names: [
        "HM_APP_HK",
    ]
),
