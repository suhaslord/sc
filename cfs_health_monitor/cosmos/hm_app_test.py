from openc3.script import *

TARGET = "<%= target_name %>"


def request_hk():
    """Request a fresh HM_APP housekeeping packet.

    HM_APP is added to the sample mission without changing the scheduler table,
    so the smoke test must not assume periodic HM housekeeping already exists.
    """
    cmd(f"{TARGET} HM_APP_SEND_HK_CMD")


def wait_for_hk():
    request_hk()
    wait_check_packet(TARGET, "HM_APP_HK", 1, 100)


def refresh_and_check(expression):
    request_hk()
    wait_check(expression, 100)


def main():
    print("HM_APP smoke test: requesting housekeeping telemetry")
    wait_for_hk()

    # Prove the app command path is alive.
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
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 150, ACTION 0, NOTE 'clear alarm'")
    refresh_and_check(f"{TARGET} HM_APP_HK THRESHOLD == 150")
    refresh_and_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0")

    print("HM_APP smoke test PASSED")


main()
