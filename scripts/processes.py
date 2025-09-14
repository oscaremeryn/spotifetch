import os
import signal
import subprocess


def execute_script(command: str | list[str], timeout: float | None = None, raise_on_statuscode: bool = True) -> int:
    # Start the process in a new process group
    process = subprocess.Popen(
        command,
        shell=isinstance(command, str),
        preexec_fn=os.setsid
    )

    try:
        # Wait for completion or timeout
        process.wait(timeout=timeout)
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        # First try to terminate the whole process group
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)

        try:
            # Give it some time to shut down cleanly
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Process group did not exit, sending SIGKILL..")
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait()

    if raise_on_statuscode and process.returncode != 0:
        raise ValueError(f'Process returned non-zero exit code ({process.returncode})')

    return process.returncode
