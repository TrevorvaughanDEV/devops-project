"""An imitation Linux shell for bots that "guess" a weak password.

Nothing typed here is ever executed. Every command is looked up in a small table of
canned answers (or answered with "command not found"), so the worst an attacker can
do is read made-up files. Downloads are never fetched: wget and curl pretend DNS
failed, and the URL is kept as evidence.

The aim is to look real enough that a bot carries on with its script, because what
it does next (fingerprinting the CPU, fetching a miner, adding an SSH key) is the
interesting part.
"""

import re
import shlex

HOSTNAME = "srv-mad-01"
KERNEL = "6.8.0-45-generic"
KERNEL_VERSION = "#45-Ubuntu SMP PREEMPT_DYNAMIC Fri Aug 30 12:02:04 UTC 2024"
MAX_OUTPUT = 8000
URL = re.compile(r"\b(?:https?|ftp|tftp)://[^\s'\"`;|&<>)]+", re.I)
# wget 1.2.3.4/x.sh with no scheme is common in bot scripts. Both patterns are linear:
# no nested or overlapping repeats, so hostile input can't make them backtrack.
FETCHER = re.compile(r"\b(?:wget|curl|tftp|ftpget)\b")
BARE_HOST = re.compile(r"(?<![\w/:.])((?:\d{1,3}\.){3}\d{1,3}(?::\d+)?/[^\s'\"`;|&<>)]*)")

HOME = {"root": "/root"}

FILES = {
    "/etc/os-release": (
        'PRETTY_NAME="Ubuntu 24.04.1 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\n'
        'VERSION="24.04.1 LTS (Noble Numbat)"\nVERSION_CODENAME=noble\nID=ubuntu\n'
        'ID_LIKE=debian\nHOME_URL="https://www.ubuntu.com/"\n'
    ),
    "/etc/issue": "Ubuntu 24.04.1 LTS \\n \\l\n\n",
    "/etc/hostname": f"{HOSTNAME}\n",
    "/etc/passwd": (
        "root:x:0:0:root:/root:/bin/bash\n"
        "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
        "bin:x:2:2:bin:/bin:/usr/sbin/nologin\n"
        "sys:x:3:3:sys:/dev:/usr/sbin/nologin\n"
        "www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n"
        "sshd:x:106:65534::/run/sshd:/usr/sbin/nologin\n"
        "ubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash\n"
    ),
    "/etc/shadow": None,  # exists, but only readable as root; see _cat
    "/proc/version": (
        f"Linux version {KERNEL} (buildd@lcy02-amd64-028) (x86_64-linux-gnu-gcc-13 "
        f"(Ubuntu 13.2.0-23ubuntu4) 13.2.0, GNU ld 2.42) {KERNEL_VERSION}\n"
    ),
    "/proc/meminfo": (
        "MemTotal:        3977280 kB\nMemFree:         2154812 kB\n"
        "MemAvailable:    3312604 kB\nBuffers:           94512 kB\nCached:          1102868 kB\n"
        "SwapTotal:             0 kB\nSwapFree:              0 kB\n"
    ),
    "/proc/uptime": "1234567.89 2345678.12\n",
    "/root/.bash_history": "apt update\napt upgrade -y\nsystemctl status nginx\n",
    "/root/.ssh/authorized_keys": "",
}

CPU_BLOCK = (
    "processor\t: {n}\nvendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 85\n"
    "model name\t: Intel(R) Xeon(R) Platinum 8272CL CPU @ 2.60GHz\nstepping\t: 7\n"
    "cpu MHz\t\t: 2593.906\ncache size\t: 36608 KB\ncpu cores\t: 2\n"
    "flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 "
    "clflush mmx fxsr sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc rep_good "
    "nopl xtopology cpuid pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 movbe popcnt aes "
    "xsave avx f16c rdrand hypervisor lahf_lm abm 3dnowprefetch avx2 avx512f\n\n"
)
FILES["/proc/cpuinfo"] = "".join(CPU_BLOCK.format(n=i) for i in range(2))

DIRS = {
    "/": "bin boot dev etc home lib lib64 media mnt opt proc root run sbin srv sys tmp usr var",
    "/root": "",
    "/root/.ssh": "authorized_keys",
    "/home": "ubuntu",
    "/home/ubuntu": "",
    "/tmp": "snap-private-tmp systemd-private-3f1c-nginx.service-Rk2a1x",
    "/var": "backups cache lib local lock log mail opt run spool tmp www",
    "/var/tmp": "",
    "/var/www": "html",
    "/var/www/html": "index.nginx-debian.html",
    "/etc": "hostname hosts issue nginx os-release passwd shadow ssh systemd",
    "/dev/shm": "",
    "/usr": "bin games include lib lib64 libexec local sbin share src",
    "/usr/bin": "bash cat curl ls perl python3 wget",
    "/proc": "cpuinfo meminfo uptime version",
}

PS = (
    "    PID TTY          TIME CMD\n"
    "      1 ?        00:00:04 systemd\n"
    "    612 ?        00:00:00 sshd\n"
    "    701 ?        00:00:12 nginx\n"
    "    702 ?        00:00:03 nginx\n"
    "   1388 ?        00:00:01 cron\n"
    "  41022 pts/0    00:00:00 bash\n"
    "  41077 pts/0    00:00:00 ps\n"
)

INSTALLED = {
    "bash", "sh", "cat", "ls", "echo", "uname", "id", "whoami", "pwd", "cd", "wget",
    "curl", "chmod", "rm", "mkdir", "ps", "free", "nproc", "uptime", "python3", "perl",
    "crontab", "grep", "head", "tail", "wc", "awk", "sed", "sort", "uniq", "base64",
    "hostname", "df", "w", "lscpu", "top", "kill", "pkill", "nohup", "passwd", "useradd",
}  # fmt: skip

# Commands that succeed quietly: changing files and processes we don't model.
SILENT = {
    "chmod", "chown", "chattr", "rm", "mkdir", "touch", "mv", "cp", "kill", "pkill",
    "killall", "export", "unset", "history", "clear", "sleep", "true", ":", "cd",
    "nohup", "ulimit", "set", "source", ".", "service", "systemctl", "iptables", "ufw",
    "sync", "alias", "unalias", "disown", "umask", "setenforce", "useradd", "usermod",
    "chpasswd", "tee", "dd", "ln",
}  # fmt: skip
FILTERS = {"grep", "head", "tail", "wc", "awk", "sed", "sort", "uniq", "cut", "tr", "xargs"}


def defang(url: str) -> str:
    """Make a captured URL safe to show: not clickable, not auto-linked."""
    url = re.sub(r"^(\w+)://", lambda m: m.group(1).replace("tt", "xx") + "[://]", url)
    return url.replace(".", "[.]")


def urls_in(command: str) -> list[str]:
    found = URL.findall(command)
    if FETCHER.search(command):
        found += ["http://" + m for m in BARE_HOST.findall(command)]
    seen: list[str] = []
    for u in found:
        u = u.rstrip(".,")
        if u not in seen:
            seen.append(u)
    return seen[:5]


def defang_urls(text: str) -> str:
    """Defang every URL inside a command, for display."""
    text = URL.sub(lambda m: defang(m.group(0)), text)
    if FETCHER.search(text):
        text = BARE_HOST.sub(lambda m: m.group(0).replace(".", "[.]"), text)
    return text


def _split(line: str, seps: tuple[str, ...]) -> list[str]:
    """Split a command line on separators that are outside quotes."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        else:
            sep = next((s for s in seps if line.startswith(s, i)), None)
            if sep:
                parts.append("".join(buf))
                buf = []
                i += len(sep)
                continue
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _words(command: str) -> list[str]:
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        words = command.split()
    # Drop redirections (2>/dev/null, > out.txt, >>log); output still goes to the bot.
    out, skip = [], False
    for w in words:
        if skip:
            skip = False
            continue
        if re.fullmatch(r"\d?>>?|&>|<", w):
            skip = True
            continue
        if re.match(r"^(\d?>>?|&>|<)\S", w) or w in ("&",):
            continue
        out.append(w)
    return out


class FakeShell:
    def __init__(self, username: str = "root"):
        self.user = username if re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username) else "root"
        self.home = HOME.get(self.user, f"/home/{self.user}")
        self.cwd = self.home
        self.done = False
        self._depth = 0

    @property
    def prompt(self) -> str:
        where = "~" if self.cwd == self.home else self.cwd
        return f"{self.user}@{HOSTNAME}:{where}{'#' if self.user == 'root' else '$'} "

    def motd(self) -> str:
        return (
            "Welcome to Ubuntu 24.04.1 LTS (GNU/Linux 6.8.0-45-generic x86_64)\n\n"
            " * Documentation:  https://help.ubuntu.com\n"
            " * Management:     https://landscape.canonical.com\n\n"
            "  System load:  0.08              Processes:             118\n"
            "  Usage of /:   23.4% of 28.89GB   Users logged in:       0\n"
            "  Memory usage: 17%               IPv4 address for eth0: 10.0.0.4\n\n"
            "Last login: Mon Oct  5 08:14:22 2026 from 10.0.0.2\n"
        )

    def run(self, line: str) -> str:
        """Run one command line and return what a terminal would show."""
        out, size = [], 0
        for chunk in _split(line.replace("\r", ""), ("\n", ";", "&&", "||")):
            piece = self._pipeline(chunk)
            out.append(piece)
            size += len(piece)
            if self.done or size >= MAX_OUTPUT:
                break
        return "".join(out)[:MAX_OUTPUT]

    def _pipeline(self, chunk: str) -> str:
        stages = _split(chunk, ("|",))
        if not stages:
            return ""
        text = self._command(_words(stages[0]))
        for stage in stages[1:]:
            text = self._filter(_words(stage), text)
        return text

    def _path(self, p: str) -> str:
        if p.startswith("~"):
            p = self.home + p[1:]
        if not p.startswith("/"):
            p = f"{self.cwd.rstrip('/')}/{p}"
        parts: list[str] = []
        for seg in p.split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(seg)
        return "/" + "/".join(parts)

    def _command(self, words: list[str]) -> str:
        # Strip wrappers that just run the rest of the line
        while words and words[0] in ("sudo", "nohup", "busybox", "command", "exec", "env"):
            words = words[1:]
        while words and re.fullmatch(r"\w+=\S*", words[0]):
            words = words[1:]  # FOO=bar cmd
        if not words:
            return ""
        cmd, args = words[0].rsplit("/", 1)[-1], words[1:]

        if cmd in ("exit", "logout", "quit"):
            self.done = True
            return ""
        if cmd == "cd":
            target = self._path(args[0]) if args else self.home
            if target in DIRS:
                self.cwd = target
                return ""
            return f"-bash: cd: {args[0]}: No such file or directory\n"
        if cmd in SILENT:
            return ""
        handler = getattr(self, f"_c_{cmd.replace('-', '_')}", None)
        if handler and re.fullmatch(r"[a-z0-9_-]+", cmd):
            return handler(args)
        if cmd in ("sh", "bash", "ash", "dash"):
            if "-c" in args and args.index("-c") + 1 < len(args) and self._depth < 3:
                self._depth += 1
                try:
                    return self.run(args[args.index("-c") + 1])
                finally:
                    self._depth -= 1
            return ""
        if cmd in ("python", "python3", "perl"):
            return ""
        return f"-bash: {cmd[:60]}: command not found\n"

    # --- commands -------------------------------------------------------------

    def _c_uname(self, args: list[str]) -> str:
        flags = "".join(a.lstrip("-") for a in args if a.startswith("-")) or "s"
        if "a" in flags:
            return f"Linux {HOSTNAME} {KERNEL} {KERNEL_VERSION} x86_64 x86_64 x86_64 GNU/Linux\n"
        parts = {"s": "Linux", "n": HOSTNAME, "r": KERNEL, "v": KERNEL_VERSION,
                 "m": "x86_64", "p": "x86_64", "i": "x86_64", "o": "GNU/Linux"}  # fmt: skip
        return " ".join(parts[f] for f in "snrvmpio" if f in flags) + "\n"

    def _c_whoami(self, args: list[str]) -> str:
        return f"{self.user}\n"

    def _c_id(self, args: list[str]) -> str:
        if self.user == "root":
            return "uid=0(root) gid=0(root) groups=0(root)\n"
        return f"uid=1000({self.user}) gid=1000({self.user}) groups=1000({self.user}),27(sudo)\n"

    def _c_hostname(self, args: list[str]) -> str:
        return f"{HOSTNAME}\n" if not args or args[0] != "-I" else "10.0.0.4\n"

    def _c_pwd(self, args: list[str]) -> str:
        return f"{self.cwd}\n"

    def _c_echo(self, args: list[str]) -> str:
        if args and args[0] == "-n":
            return " ".join(args[1:])
        return " ".join(a for a in args if a not in ("-e", "-E")) + "\n"

    def _c_printf(self, args: list[str]) -> str:
        return args[0].replace("\\n", "\n") if args else ""

    def _c_nproc(self, args: list[str]) -> str:
        return "2\n"

    def _c_uptime(self, args: list[str]) -> str:
        return " 08:31:07 up 14 days,  6:56,  1 user,  load average: 0.08, 0.05, 0.01\n"

    def _c_w(self, args: list[str]) -> str:
        return (
            self._c_uptime(args)
            + "USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT\n"
            + f"{self.user:<8} pts/0    10.0.0.2         08:31    0.00s  0.01s  0.00s w\n"
        )

    def _c_free(self, args: list[str]) -> str:
        if "-h" in args:
            return (
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:           3.8Gi       662Mi       2.1Gi       1.0Mi       1.1Gi       3.2Gi\n"
                "Swap:             0B          0B          0B\n"
            )
        div = 1024 if "-m" in args else 1
        t, u, f, c, a = (int(x / div) for x in (3977280, 678104, 2154812, 1197380, 3312604))
        return (
            "               total        used        free      shared  buff/cache   available\n"
            f"Mem:      {t:>10}  {u:>10}  {f:>10}  {1024 // div:>10}  {c:>10}  {a:>10}\n"
            f"Swap:     {0:>10}  {0:>10}  {0:>10}\n"
        )

    def _c_df(self, args: list[str]) -> str:
        return (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/root        29G  6.8G   22G  24% /\n"
            "tmpfs           1.9G     0  1.9G   0% /dev/shm\n"
            "/dev/sda15      105M  6.1M   99M   6% /boot/efi\n"
        )

    def _c_lscpu(self, args: list[str]) -> str:
        return (
            "Architecture:             x86_64\n  CPU op-mode(s):         32-bit, 64-bit\n"
            "CPU(s):                   2\nVendor ID:                GenuineIntel\n"
            "  Model name:             Intel(R) Xeon(R) Platinum 8272CL CPU @ 2.60GHz\n"
            "    Thread(s) per core:   2\n    Core(s) per socket:   1\n"
            "Hypervisor vendor:        Microsoft\n"
        )

    def _c_ps(self, args: list[str]) -> str:
        return PS

    def _c_ls(self, args: list[str]) -> str:
        paths = [a for a in args if not a.startswith("-")] or [self.cwd]
        out = []
        for p in paths:
            full = self._path(p)
            if full in DIRS:
                names = DIRS[full].split()
                if any("a" in a for a in args if a.startswith("-")):
                    names = [".", "..", *names]
                out.append("  ".join(names) + ("\n" if names else ""))
            elif full in FILES:
                out.append(p + "\n")
            else:
                out.append(f"ls: cannot access '{p}': No such file or directory\n")
        return "".join(out)

    def _c_cat(self, args: list[str]) -> str:
        out = []
        for p in (a for a in args if not a.startswith("-")):
            full = self._path(p)
            if full == "/etc/shadow" and self.user != "root":
                out.append(f"cat: {p}: Permission denied\n")
            elif full == "/etc/shadow":
                out.append("root:*:19800:0:99999:7:::\nubuntu:!:19800:0:99999:7:::\n")
            elif full in FILES:
                out.append(FILES[full] or "")
            elif full in DIRS:
                out.append(f"cat: {p}: Is a directory\n")
            else:
                out.append(f"cat: {p}: No such file or directory\n")
            if sum(map(len, out)) >= MAX_OUTPUT:
                break
        return "".join(out)

    def _c_which(self, args: list[str]) -> str:
        return "".join(f"/usr/bin/{a}\n" for a in args if a in INSTALLED)

    def _c_crontab(self, args: list[str]) -> str:
        return f"no crontab for {self.user}\n" if "-l" in args else ""

    def _c_wget(self, args: list[str]) -> str:
        target = next((a for a in args if not a.startswith("-")), None)
        if not target:
            return "wget: missing URL\n"
        host = re.sub(r"^\w+://", "", target).split("/")[0].split(":")[0]
        if re.fullmatch(r"[\d.]+", host):
            return (
                f"--2026-10-05 08:31:12--  {target}\n"
                f"Connecting to {host}:80... failed: Connection timed out.\nRetrying.\n"
            )
        return (
            f"--2026-10-05 08:31:12--  {target}\n"
            f"Resolving {host} ({host})... failed: Temporary failure in name resolution.\n"
            f"wget: unable to resolve host address ‘{host}’\n"
        )

    def _c_curl(self, args: list[str]) -> str:
        target = next((a for a in args if not a.startswith("-") and ("." in a or "/" in a)), "")
        host = re.sub(r"^\w+://", "", target).split("/")[0].split(":")[0]
        return f"curl: (6) Could not resolve host: {host}\n" if host else ""

    def _c_tftp(self, args: list[str]) -> str:
        return "tftp: timeout\n"

    def _c_passwd(self, args: list[str]) -> str:
        return "passwd: password updated successfully\n"

    def _c_top(self, args: list[str]) -> str:
        return self._c_uptime(args) + "Tasks: 118 total,   1 running, 117 sleeping\n"

    def _c_base64(self, args: list[str]) -> str:
        return ""

    def _c_lspci(self, args: list[str]) -> str:
        return "0000:00:08.0 VGA compatible controller: Microsoft Corporation Hyper-V virtual VGA\n"

    def _c_nvidia_smi(self, args: list[str]) -> str:
        return "-bash: nvidia-smi: command not found\n"

    # --- pipes --------------------------------------------------------------

    def _filter(self, words: list[str], text: str) -> str:
        if not words:
            return text
        cmd, args = words[0], words[1:]
        lines = text.splitlines()
        if cmd == "grep":
            flags = "".join(a.lstrip("-") for a in args if a.startswith("-"))
            pats = [a for a in args if not a.startswith("-")]
            if not pats:
                return text
            pat = pats[0].lower() if "i" in flags else pats[0]
            invert = "v" in flags
            match = [ln for ln in lines if (pat in (ln.lower() if "i" in flags else ln)) != invert]
            if "c" in flags:
                return f"{len(match)}\n"
            return "".join(ln + "\n" for ln in match)
        if cmd in ("head", "tail"):
            n = 10
            for i, a in enumerate(args):
                if a == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
                    n = int(args[i + 1])
                elif re.fullmatch(r"-n?\d+", a):
                    n = int(a.lstrip("-n"))
            picked = lines[:n] if cmd == "head" else lines[-n:] if n else []
            return "".join(ln + "\n" for ln in picked)
        if cmd == "wc":
            if "-l" in args:
                return f"{len(lines)}\n"
            return f"{len(lines):>7} {len(text.split()):>7} {len(text):>7}\n"
        if cmd == "sort":
            return "".join(ln + "\n" for ln in sorted(lines))
        if cmd == "uniq":
            return "".join(ln + "\n" for i, ln in enumerate(lines) if i == 0 or lines[i - 1] != ln)
        if cmd in FILTERS:
            return text  # awk/sed/cut/tr: close enough to show the input unchanged
        return self._command(words)
