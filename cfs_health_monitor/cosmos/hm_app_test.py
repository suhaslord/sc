import time

from openc3.script import *

TARGET = "<%= target_name %>"
INTERFACE = f"{TARGET}_INTF"
TLM_OUTPUT_IP = "<%= global_tlm_output_ip %>"
HM_HK_STREAM_ID = <%= get_cfs_pkt_msg_id('HM_APP_HK', cfs_cpu_num_from_target_name(target_name)) %>


def wait_for_command_interface(timeout=45):
    """Wait until OpenC3's target interface and command handler are ready.

    Plugin installation creates the interface microservice asynchronously. A
    target command published before its command-handler thread has subscribed
    to the Redis command stream can be skipped, which surfaces as OpenC3's
    30-second "waiting for cmd ack" timeout even though cFS is healthy.
    """
    deadline = time.time() + timeout
    last_state = "not-created"
    last_error = None

    while time.time() < deadline:
        try:
            info = get_interface(INTERFACE)
            last_state = info.get("state", "UNKNOWN")
            if last_state == "CONNECTED":
                # The handler thread is created before the interface connection
                # loop. Give it one scheduling turn, then prove it can consume
                # and acknowledge an interface directive before sending any cFS
                # target command.
                time.sleep(1)
                details = interface_details(INTERFACE)
                print(
                    f"OpenC3 interface ready: {INTERFACE} "
                    f"state={last_state} details={details}"
                )
                return
        except Exception as error:
            last_error = error
        time.sleep(1)

    raise RuntimeError(
        f"OpenC3 interface {INTERFACE} was not command-ready within {timeout}s; "
        f"last_state={last_state}, last_error={last_error}"
    )


def enable_live_telemetry_path():
    """Enable TO_LAB output and subscribe it to HM_APP housekeeping."""
    print(f"Enabling TO_LAB telemetry output to {TLM_OUTPUT_IP}")
    cmd(f"{TARGET} TO_LAB_CMD_ENABLE_OUTPUT with DEST_IP '{TLM_OUTPUT_IP}'")
    wait_check_packet(TARGET, "TO_LAB_HK", 1, 100)

    to_cmd_count = tlm(f"{TARGET} TO_LAB_HK COMMAND_COUNTER")
    cmd(
        f"{TARGET} TO_LAB_CMD_ADD_PACKET with STREAM_VALUE {HM_HK_STREAM_ID}, "
        "FLAGS_PRIORITY 0, FLAGS_RELIABILITY 0, BUF_LIMIT 4"
    )
    wait_check(f"{TARGET} TO_LAB_HK COMMAND_COUNTER == {to_cmd_count + 1}", 100)


def request_hk():
    """Request a fresh HM_APP housekeeping packet.

    HM_APP is added to the sample mission without changing the scheduler table,
    so the smoke test explicitly requests housekeeping rather than assuming a
    periodic scheduler entry exists.
    """
    cmd(f"{TARGET} HM_APP_SEND_HK_CMD")


def wait_for_hk():
    request_hk()
    wait_check_packet(TARGET, "HM_APP_HK", 1, 100)


def refresh_and_check(expression):
    request_hk()
    wait_check(expression, 100)


def main():
    print("HM_APP live OpenC3/cFS round-trip test")
    wait_for_command_interface()
    enable_live_telemetry_path()

    print("Requesting HM_APP housekeeping through COSMOS")
    wait_for_hk()

    # Prove the app command path is alive end-to-end.
    count = tlm(f"{TARGET} HM_APP_HK COMMAND_COUNTER")
    cmd(f"{TARGET} HM_APP_CMD_NOOP")
    refresh_and_check(f"{TARGET} HM_APP_HK COMMAND_COUNTER == {count + 1}")

    # Reset counters and confirm the command was processed.
    cmd(f"{TARGET} HM_APP_CMD_RESET_COUNTERS")
    refresh_and_check(f"{TARGET} HM_APP_HK COMMAND_COUNTER == 0")

    # Set threshold to 100. ACTION=0 maps to SET_THRESHOLD.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 100, ACTION 0, NOTE 'threshold'")
    refresh_and_check(f"{TARGET} HM_APP_HK THRESHOLD == 100")
    refresh_and_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0")

    # Inject a nominal sample and verify no alarm.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 75, ACTION 1, NOTE 'nominal'")
    refresh_and_check(f"{TARGET} HM_APP_HK CURRENT_SAMPLE == 75")
    refresh_and_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0")

    # Inject an over-threshold sample and verify alarm state.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 125, ACTION 1, NOTE 'alarm'")
    refresh_and_check(f"{TARGET} HM_APP_HK CURRENT_SAMPLE == 125")
    refresh_and_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 1")

    # Raise the threshold above the current sample; alarm should clear immediately.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 150, ACTION 0, NOTE 'clear'")
    refresh_and_check(f"{TARGET} HM_APP_HK THRESHOLD == 150")
    refresh_and_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0")

    print("HM_APP live OpenC3/cFS round-trip PASSED")


main()
