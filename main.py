import subprocess
import glob
import random
import os as oslib
import argparse
import sys

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

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-w", "--windows", action="store_true", help = "Apply actions to a Windows installation")
    parser.add_argument("-l", "--linux", action="store_true", help = "Apply actions to a Linux installation")
    parser.add_argument("-a", "--any", action="store_true", help = "Apply actions to any installation")
    parser.add_argument("-d", "--device", type=str, required=False, help = "Apply actions to an installation on <device>")
    parser.add_argument("-o", "--os", choices=["windows", "linux", "w", "l"], required=False, help = "Manually select the OS (use only with --device)")

    parser.add_argument("-r", "--roothack", choices=["enable", "disable", "toggle", "e", "d", "t"], required=False, help = "Roothack the selected installation")
    parser.add_argument("-s", "--shell", action="store_true", help = "Run a shell on the selected installation (Linux only)")
   # parser.add_argument("-c", "--custom", type=str, required=False, help = "Apply a custom action to the selected installation") Coming soon

    parser.add_argument("-n", "--no-updates", action="store_true", help = "Do not check for updates")

    args = parser.parse_args()

    argserror = False
    if [args.windows, args.linux, args.any, args.device].count(True) > 1:
        print("error: only use os flag")
        argserror = True
    
    if bool(args.os) != bool(args.device):
        print("error: use --os only with --device")
        argserror = True
    
    if [args.roothack, args.shell].count(True) > 1:
        print("error: only use 1 action flag")
        argserror = True
    
    if argserror: exit(1)

    if oslib.getuid() != 0:
        print("Not root")
        print("You need to run this from a live usb on the computer you want to roothack")
        print("You can either do this through BIOS (Google: \"<device manufacturer> boot from USB\")")
        print("Or by pressing Shift+Reboot in windows start menu")
        exit(subprocess.Popen(["sudo", sys.executable, __file__], stdout=sys.stdout, stdin=sys.stdin, stderr=sys.stderr).wait())

    if not args.no_updates:
        try:
            print("Checking for updates...")
            print("Press Ctrl+C to cancel")
            subprocess.Popen(["git", "pull"], stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin).wait()
        except KeyboardInterrupt:
            print("Canceled.")

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

    if not args.device:
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
                    oses.append(("linux_self", device))
                    continue
                if linux.is_linux(device):
                    print("Linux on", device)
                    oses.append(("linux", device))
            elif type == "Microsoft basic data":
                print("Windows compatible filesystem on", device)
                if windows.is_windows(device):
                    print("Windows on", device)
                    oses.append(("windows", device))
    
    if not (args.windows or args.linux or args.any or args.device):
        print("=== OSs ===")
        for ind, osdata in enumerate(oses):
            os, device = osdata

            display_os = {
                "linux": "Linux",
                "linux_self": "Linux (current)",
                "windows": "Windows"
            }[os]

            print(f"[{ind}]", display_os, "on", device)

        osid = int(input("Select os to roothack: "))
        os, device = oses[osid]
    else:
        if args.device:
            os = {
                "w": "windows",
                "l": "linux"
            }.get(args.os, args.os)
            device = args.device
        else:
            if args.any:
                selected = oses
                if len(selected) > 1:
                    raise ValueError("Multiple installations found")
                if not selected:
                    raise ValueError("No installations found")

            if args.linux:
                selected = list(filter(lambda x: args.linux and x[0].startswith("linux"), oses))
                if len(selected) > 1:
                    raise ValueError("Multiple Linux installations found")
                if not selected:
                    raise ValueError("No Linux installations found")

            if args.windows:
                selected = list(filter(lambda x: args.windows and x[0] == "windows", oses))
                if len(selected) > 1:
                    raise ValueError("Multiple Windows installations found")
                if not selected:
                    raise ValueError("No Windows installations found")
            
            select = selected[0]
            os, device = select

    mountpoint = mount_device(os, device)
    
    print("Mounted as", mountpoint)
    if os == "windows":
        tools = windows.TOOLS
        roothack = windows.roothack
        shell = windows.shell
    elif os.startswith("linux"):
        tools = linux.TOOLS
        roothack = linux.roothack
        shell = linux.shell

    if not (args.roothack or args.shell):
        for ind, title in enumerate(tools.keys()):
            print(f"[{ind}] {title}")
        ind = int(input("Select: "))
        tool = list(tools.values())[ind]
        tool(mountpoint)
    elif args.roothack:
        action = {
            "e": "enable",
            "d": "disable",
            "t": "toggle"
        }.get(args.roothack, args.roothack)
        roothack(mountpoint, action)
    elif args.shell:
        shell(mountpoint)
    

if __name__ == "__main__":
    main()