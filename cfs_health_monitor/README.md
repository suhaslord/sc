# cFS Health Monitor

A small cFS application derived from NASA `sample_app` and extended with threshold/sample health monitoring. The repository keeps the transformation explicit in `prepare_hm_app.py` so the app is generated from the `sample_app` revision that belongs to the cFS checkout being tested.

## Behavior

HM_APP starts with:

- threshold: `100`
- current sample: `0`
- alarm: inactive

Commands use the command dispatch inherited from `sample_app`:

- `NOOP` — function code `0`
- `RESET_COUNTERS` — function code `1`
- `CONTROL` — function code `3`
  - `ACTION=0`: set `THRESHOLD` to `VALUE`
  - `ACTION=1`: inject `CURRENT_SAMPLE=VALUE`

`ALARM_ACTIVE` is `1` when `CURRENT_SAMPLE > THRESHOLD`, otherwise `0`.

Housekeeping telemetry publishes the command counter, command-error counter, current sample, threshold, and alarm state. The generated C payload contains explicit reserved/alignment bytes so the checked-in OpenC3/COSMOS telemetry layout has a deterministic packet contract.

## cFS integration

`prepare_hm_app.py`:

1. copies the cFS checkout's `apps/sample_app` to `apps/hm_app`;
2. renames the application symbols and build files;
3. assigns HM_APP command/send-HK/HK topics `0xE2/0xE3/0xE3`;
4. adds the health-monitor state and command behavior;
5. adds `hm_app` to the sample mission application list.

The CI startup script loads:

```text
CFE_APP, hm_app, HM_APP_Main, HM_APP, 55, 32768, 0x0, 0;
```

## Validation

`.github/workflows/cfs-health-monitor.yml` performs the reproducible validation gate:

1. clones NASA cFS with its submodules;
2. generates HM_APP inside that mission tree;
3. mechanically checks the generated cFS message/function-code contract against the checked-in COSMOS definitions;
4. runs `native_std.prep`, builds, and installs the mission;
5. verifies the HM_APP binary and cFE executable are staged;
6. boots `core-cpu1` from the staged CPU directory;
7. requires both `Health Monitor Initialized.` and the cFE `OPERATIONAL` state in the boot log;
8. syntax-checks the OpenC3/COSMOS smoke-test procedure;
9. uploads the boot log, startup script, binary-path evidence, and COSMOS files as a workflow artifact.

`verify_cosmos_contract.py` intentionally checks the generated cFS definitions rather than duplicating assumptions in CI. It verifies topic/MID mapping, function codes, command payload width, and housekeeping field order/width.

## OpenC3 / COSMOS

The `cosmos/` directory contains:

- `hm_app_msg_list_patch.rb` — HM_APP command and telemetry MID entries;
- `hm_app_cmd_def.txt` — send-HK, NOOP, reset, and monitor-control commands;
- `hm_app_tlm_def.txt` — housekeeping packet definition;
- `hm_app_test.py` — smoke procedure covering NOOP, counter reset, threshold updates, nominal samples, and alarm transitions.

The static contract is checked in CI. The procedure is syntax-checked in CI, but this repository does **not** claim a live OpenC3-to-cFS network command/telemetry round trip until that procedure is actually run in a configured `nasa/cfs-cosmos-plugin` environment.

## Reproduce the cFS build/boot gate locally

From this repository root on a Linux host with Git, CMake, and build tools:

```bash
git clone --depth 1 --recurse-submodules --shallow-submodules https://github.com/nasa/cFS.git cFS
python3 cfs_health_monitor/prepare_hm_app.py cFS
python3 cfs_health_monitor/verify_cosmos_contract.py cFS
cd cFS
make native_std.prep
make -j2 native_std.install
```

Then add the HM_APP startup record to `build-native_std/exe/cpu1/cf/cfe_es_startup.scr` and launch `build-native_std/exe/cpu1/core-cpu1` from its `cpu1` directory, matching the CI workflow.
