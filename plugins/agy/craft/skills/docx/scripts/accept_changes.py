"""Accept all tracked changes in a DOCX file using LibreOffice.

Requires LibreOffice (soffice) to be installed.
"""

import argparse
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from office.soffice import run_soffice

logger = logging.getLogger(__name__)

ACCEPT_CHANGES_MACRO = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">
    Sub AcceptAllTrackedChanges()
        Dim document As Object
        Dim dispatcher As Object

        document = ThisComponent.CurrentController.Frame
        dispatcher = createUnoService("com.sun.star.frame.DispatchHelper")

        dispatcher.executeDispatch(document, ".uno:AcceptAllTrackedChanges", "", 0, Array())
        ThisComponent.store()
        ThisComponent.close(True)
    End Sub
</script:module>"""


def accept_changes(
    input_file: str,
    output_file: str,
) -> tuple[None, str]:
    input_path = Path(input_file)
    output_path = Path(output_file)

    if not input_path.exists():
        return None, f"Error: Input file not found: {input_file}"

    if not input_path.suffix.lower() == ".docx":
        return None, f"Error: Input file is not a DOCX file: {input_file}"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return None, f"Error: Failed to create output directory: {e}"

    with tempfile.TemporaryDirectory(
        prefix="accept-lo-profile-", ignore_cleanup_errors=True
    ) as profile_dir:
        profile_path = Path(profile_dir)
        profile_url = profile_path.as_uri()
        if not _setup_libreoffice_macro(profile_path, profile_url):
            return None, "Error: Failed to setup LibreOffice macro"

        fd, tmp_name = tempfile.mkstemp(
            prefix=output_path.name + ".", suffix=".docx", dir=output_path.parent
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            shutil.copy2(input_path, tmp_path)
            result = run_soffice(
                [
                    f"-env:UserInstallation={profile_url}",
                    "--headless",
                    "--norestore",
                    "vnd.sun.star.script:Standard.Module1.AcceptAllTrackedChanges?language=Basic&location=application",
                    str(tmp_path.resolve()),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                return None, f"Error: LibreOffice failed: {result.stderr}"
            os.replace(tmp_path, output_path)
        except subprocess.TimeoutExpired:
            return None, f"Error: LibreOffice timed out while accepting tracked changes in {input_file}"
        except OSError as e:
            return None, f"Error: Failed to write output file: {e}"
        finally:
            tmp_path.unlink(missing_ok=True)

    return (
        None,
        f"Successfully accepted all tracked changes: {input_file} -> {output_file}",
    )


def _setup_libreoffice_macro(profile_path: Path, profile_url: str) -> bool:
    macro_dir = profile_path / "user" / "basic" / "Standard"
    macro_file = macro_dir / "Module1.xba"

    if macro_file.exists() and "AcceptAllTrackedChanges" in macro_file.read_text(encoding="utf-8"):
        return True

    if not macro_dir.exists():
        try:
            run_soffice(
                [
                    f"-env:UserInstallation={profile_url}",
                    "--headless",
                    "--terminate_after_init",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to initialize LibreOffice profile: {e}")
            return False
        macro_dir.mkdir(parents=True, exist_ok=True)

    try:
        macro_file.write_text(ACCEPT_CHANGES_MACRO, encoding="utf-8")
        return True
    except OSError as e:
        logger.warning(f"Failed to setup LibreOffice macro: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Accept all tracked changes in a DOCX file"
    )
    parser.add_argument("input_file", help="Input DOCX file with tracked changes")
    parser.add_argument(
        "output_file", help="Output DOCX file (clean, no tracked changes)"
    )
    args = parser.parse_args()

    _, message = accept_changes(args.input_file, args.output_file)
    print(message)

    if "Error" in message:
        raise SystemExit(1)
