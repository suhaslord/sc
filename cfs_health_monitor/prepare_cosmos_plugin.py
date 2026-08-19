#!/usr/bin/env python3
"""Inject HM_APP command/telemetry support into nasa/cfs-cosmos-plugin.

Usage:
    python3 cfs_health_monitor/prepare_cosmos_plugin.py cfs-cosmos-plugin

The script is intentionally idempotent so the same checkout can be prepared
more than once during local debugging or CI retries.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"missing HM_APP integration source: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_cosmos_plugin.py <cfs-cosmos-plugin-root>")

    plugin_root = Path(sys.argv[1]).resolve()
    if not (plugin_root / "plugin.txt").is_file():
        raise RuntimeError(f"not a cfs-cosmos-plugin checkout: {plugin_root}")

    project_root = Path(__file__).resolve().parent
    cosmos = project_root / "cosmos"

    copy_file(cosmos / "hm_app_cmd_def.txt", plugin_root / "targets/CFS/cmd_tlm/hm_app_cmd_def.txt")
    copy_file(cosmos / "hm_app_tlm_def.txt", plugin_root / "targets/CFS/cmd_tlm/hm_app_tlm_def.txt")
    copy_file(cosmos / "hm_app_test.py", plugin_root / "targets/CFS/procedures/hm_app_test.py")

    msg_list_path = plugin_root / "targets/CFS/lib/cfs_cmd_tlm_list.rb"
    msg_list = msg_list_path.read_text()
    if '"HM_APP_CMD" => FswMsgInfo.new(' not in msg_list:
        snippet = (cosmos / "hm_app_msg_list_patch.rb").read_text()
        marker = "$CFS_CMD_TLM_LIST = {\n"
        if marker not in msg_list:
            raise RuntimeError("unable to locate $CFS_CMD_TLM_LIST hash")
        msg_list = msg_list.replace(marker, marker + "\n" + snippet + "\n", 1)
        msg_list_path.write_text(msg_list)

    required = (
        plugin_root / "targets/CFS/cmd_tlm/hm_app_cmd_def.txt",
        plugin_root / "targets/CFS/cmd_tlm/hm_app_tlm_def.txt",
        plugin_root / "targets/CFS/procedures/hm_app_test.py",
    )
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"failed to stage {path}")

    patched = msg_list_path.read_text()
    for token in ("HM_APP_CMD", "HM_APP_SEND_HK_CMD", "HM_APP_HK"):
        if token not in patched:
            raise RuntimeError(f"message list patch missing {token}")

    print(f"Prepared HM_APP support in {plugin_root}")


if __name__ == "__main__":
    main()
