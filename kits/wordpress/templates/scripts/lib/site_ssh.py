"""Site-pinned SSH, SFTP and rsync, with the Conclave password passed to sshpass through a private pipe.

Generalised from rizonetech-com and jmrgroup-coza by the Conclave-SDK WordPress kit. The site, the vault item and
the expected identity all come from `.conclave/wordpress-site.json` (scripts/lib/wp_site.py). The item is refused when
any pinned field drifts, so a swapped or edited item can never point a command at another site. The password never
reaches an argument, the environment, the output or a log.
"""
import os
import shlex
import signal
import subprocess

import wp_site

LOCAL_HOME = os.path.expanduser("~").rstrip("/") + "/"
OPTIONS = ["-F", "/dev/null", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15",
           "-o", "NumberOfPasswordPrompts=1", "-o", "PreferredAuthentications=password",
           "-o", "PubkeyAuthentication=no", "-o", "ForwardAgent=no", "-o", "ClearAllForwardings=yes"]


def connection(pin=None):
    """The pinned SSH fields and password, or a refusal when the vault item is not this site's."""
    pin = pin or wp_site.load()
    item_id, expected = wp_site.ssh_identity(pin)
    fields = wp_site.vault_fields(item_id)
    if any(fields.get(key) != value for key, value in expected.items()):
        raise ValueError("SSH identity mismatch: the vault item does not match .conclave/wordpress-site.json")
    wp_site.secret(fields)
    return {**fields, "ssh_host": expected["ssh_hostname"]}


def command(kind, arguments, fields):
    """Build the transport command line. Only the pinned user and hosts can appear in it."""
    if kind == "ssh":
        return ["ssh", *OPTIONS, "-T", "-p", fields["port"], fields["username"] + "@" + fields["ssh_host"], *arguments]
    if kind == "sftp":
        if arguments:
            raise ValueError("supply SFTP batch commands through stdin")
        return ["sftp", *OPTIONS, "-o", "BatchMode=no", "-P", fields["port"], "-b", "-",
                fields["username"] + "@" + fields["hostname"]]
    if kind == "rsync":
        # An argument "remote:PATH" names PATH on the pinned site; the caller never
        # spells the user or host, so it cannot point rsync anywhere else.
        if any(":" in arg and not arg.startswith("remote:") for arg in arguments if not arg.startswith("-")):
            raise ValueError("rsync remote paths must use the remote: prefix")
        destination = fields["username"] + "@" + fields["ssh_host"]
        shell = shlex.join(["ssh", *OPTIONS, "-p", fields["port"]])
        return ["rsync", "-e", shell, *(destination + ":" + arg[7:] if arg.startswith("remote:") else arg for arg in arguments)]
    raise ValueError("expected ssh, sftp or rsync")


def run(kind, arguments=(), *, input=None, timeout=90, pin=None):
    if kind not in ("ssh", "sftp", "rsync"):
        raise ValueError("expected ssh, sftp or rsync")
    fields = connection(pin)
    argv = command(kind, list(arguments), fields)
    password = fields.pop("password")
    reader, writer = os.pipe()
    try:
        os.write(writer, (password + "\n").encode())
        os.close(writer)
        writer = None
        del password
        wrapped = ["sshpass", "-d", str(reader), *argv]
        process = subprocess.Popen(wrapped, pass_fds=(reader,), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(input=input, timeout=timeout)
        except BaseException:
            # Collect the entire owned transport group, including SSH beneath sshpass.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


def remote_arg(arg):
    """Quote one argument for the remote shell, mapping home-relative paths to the server's home."""
    for prefix in ("~/", LOCAL_HOME):
        if arg.startswith(prefix):
            return '"$HOME"/' + shlex.quote(arg[len(prefix):])
        if "=" in arg:
            key, _, rest = arg.partition("=")
            if rest.startswith(prefix):
                return shlex.quote(key + "=") + '"$HOME"/' + shlex.quote(rest[len(prefix):])
    return shlex.quote(arg)


def wp_command(arguments, pin):
    """The remote shell line that runs WP-CLI in the site's WordPress root (ssh.wp_path, validated by wp_site)."""
    (wp_path,) = wp_site.require(pin, "ssh.wp_path")
    return "cd " + wp_path + " && wp " + " ".join(remote_arg(arg) for arg in arguments)


def wp(arguments, *, input=None, timeout=600, pin=None):
    pin = pin or wp_site.load()
    return run("ssh", [wp_command(arguments, pin)], input=input, timeout=timeout, pin=pin)
