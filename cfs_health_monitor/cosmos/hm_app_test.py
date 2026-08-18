from openc3.script import *

TARGET = "<%= target_name %>"


def wait_for_hk():
    wait_check_packet(TARGET, "HM_APP_HK", 1, 100)


def main():
    print("HM_APP smoke test: waiting for housekeeping telemetry")
    wait_for_hk()

    # Prove the app command path is alive.
    count = tlm(f"{TARGET} HM_APP_HK COMMAND_COUNTER")
    cmd(f"{TARGET} HM_APP_CMD_NOOP")
    wait_check(f"{TARGET} HM_APP_HK COMMAND_COUNTER == {count + 1}", 100)

    # Reset counters and confirm the command was processed.
    cmd(f"{TARGET} HM_APP_CMD_RESET_COUNTERS")
    wait_check(f"{TARGET} HM_APP_HK COMMAND_COUNTER == 0", 100)

    # Set threshold to 100. ACTION=0 maps to SET_THRESHOLD.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 100, ACTION 0, NOTE 'threshold'")
    wait_check(f"{TARGET} HM_APP_HK THRESHOLD == 100", 100)
    wait_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0", 100)

    # Inject a nominal sample and verify no alarm.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 75, ACTION 1, NOTE 'nominal'")
    wait_check(f"{TARGET} HM_APP_HK CURRENT_SAMPLE == 75", 100)
    wait_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0", 100)

    # Inject an over-threshold sample and verify alarm state.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 125, ACTION 1, NOTE 'alarm'")
    wait_check(f"{TARGET} HM_APP_HK CURRENT_SAMPLE == 125", 100)
    wait_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 1", 100)

    # Raise the threshold above the current sample; alarm should clear immediately.
    cmd(f"{TARGET} HM_APP_CMD_CONTROL with VALUE 150, ACTION 0, NOTE 'clear alarm'")
    wait_check(f"{TARGET} HM_APP_HK THRESHOLD == 150", 100)
    wait_check(f"{TARGET} HM_APP_HK ALARM_ACTIVE == 0", 100)

    print("HM_APP smoke test PASSED")


main()
