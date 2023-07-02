import subprocess
import glob
import random
import os as oslib
import linux
import windows

MOUNT = "/mnt/iamroot-{os}-{rng}/"

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
    mounts = get_mounts(device)
    if mounts:
        return mounts[0]
    target = MOUNT.format(os=os, rng=random.randint(1, 256))
    oslib.makedirs(target, exist_ok=True)
    run("mount "+device+" "+target)
    return target

def is_readonly(mountpoint):
    with open("/proc/mounts") as f:
        for line in f:
            device, mount, driver, tags, _, _ = line.split(" ", maxsplit=6)
            if mount == mountpoint.rstrip("/"):
                tags = tags.split(",")
                if "ro" in tags:
                    return True
                else:
                    return False
    raise ValueError("Mountpoint not found in /proc/mounts")

def main():
    if oslib.getuid() != 0:
        print("Not root")
        print("You need to run this from a live usb on the computer you want to roothack")
        print("You can either do this through BIOS (Google: \"<device manufacturer> boot from USB\")")
        print("Or by pressing Shift+Reboot in windows start menu")
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
                oses.append(("Linux_self", device))
                continue
            if linux.is_linux(device):
                print("Linux on", device)
                oses.append(("Linux", device))
        elif type == "Microsoft basic data":
            print("Windows compatible filesystem on", device)
            if windows.is_windows(device):
                print("Windows on", device)
                oses.append(("Windows", device))
    print("=== OSs ===")
    for ind, osdata in enumerate(oses):
        os, device = osdata
        if os == "Linux_self":
            os = "Linux (current)"
        print(f"[{ind}]", os, "on", device)
    osid = int(input("Select os to roothack: "))
    os, device = oses[osid]
    mountpoint = mount_device(os, device)
    
    print("Mounted as", mountpoint)
    if os == "Windows":
        if is_readonly(mountpoint):
            print("The filesystem was mounted as readonly")
            print("This could mean that windows was not shut down properly")
            print("To fully shutdown Windows press Shift+PowerOff in the start menu")
            exit(1)
        windows.roothack_windows(mountpoint)
    elif os.startswith("Linux"):
        linux.roothack_linux(mountpoint)
    

if __name__ == "__main__":
    main()