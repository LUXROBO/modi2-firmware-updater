import os
import sys
import json
import shutil
from functools import cmp_to_key


def compare_version(left, right):
    from packaging import version
    if version.parse(left) > version.parse(right):
        return 1
    elif version.parse(left) == version.parse(right):
        return 0
    else:
        return -1

def rmtree(top):
    import stat
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)

build_path = os.path.join(os.path.dirname(__file__), "build")

def build(release_version):

    module_list = [
        "battery",
        "button",
        "dial",
        "display",
        "env",
        "imu",
        "joystick",
        "led",
        "motor",
        "speaker",
        "tof",
        "network"
    ]

    def build_version(release_version):
        root = os.path.dirname(__file__)
        file_list = os.listdir(root)
        latest_version = {}

        for ele in file_list:
            if not os.path.isfile(ele) and ele != ".git":
                module_type = ele
                if module_type in module_list:
                    # modules - barrey, button, ...., network
                    version_dir = os.path.join(root, module_type)
                    version_list = os.listdir(version_dir)
                    version_list = sorted(version_list, key=cmp_to_key(compare_version), reverse=True)
                    if len(version_list):
                        latest_version[module_type] = version_list[0]
                        if module_type == "button":
                            version_path =  os.path.join(root, module_type, latest_version[module_type], "version.txt")
                            with open(version_path, "r") as version_file:
                                version_info = version_file.read()
                                version = json.loads(version_info)
                                latest_version["os_e230"] = version["os"]
                        if module_type == "display":
                            version_path =  os.path.join(root, module_type, latest_version[module_type], "version.txt")
                            with open(version_path, "r") as version_file:
                                version_info = version_file.read()
                                version = json.loads(version_info)
                                latest_version["os_e103"] = version["os"]
                elif module_type == "bootloader":
                    # check e230
                    bootloader_e230_version_dir = os.path.join(root, ele, "e230")
                    bootloader_e230_version_list = os.listdir(bootloader_e230_version_dir)
                    bootloader_e230_version_list = sorted(bootloader_e230_version_list, key=cmp_to_key(compare_version), reverse=True)
                    if len(bootloader_e230_version_list):
                        latest_version["bootloader_e230"] = bootloader_e230_version_list[0]
                    # check e103
                    bootloader_e103_version_dir = os.path.join(root, ele, "e103")
                    bootloader_e103_version_list = os.listdir(bootloader_e103_version_dir)
                    bootloader_e103_version_list = sorted(bootloader_e103_version_list, key=cmp_to_key(compare_version), reverse=True)
                    if len(bootloader_e103_version_list):
                        latest_version["bootloader_e103"] = bootloader_e103_version_list[0]
                elif module_type == "esp32":
                    # check esp32 app
                    esp32_app_version_dir = os.path.join(root, ele, "app")
                    esp32_app_version_list = os.listdir(esp32_app_version_dir)
                    esp32_app_version_list = sorted(esp32_app_version_list, key=cmp_to_key(compare_version), reverse=True)
                    if len(esp32_app_version_list):
                        latest_version["esp32_app"] = esp32_app_version_list[0]
                    # check esp32 ota
                    esp32_ota_version_dir = os.path.join(root, ele, "ota")
                    esp32_ota_version_list = os.listdir(esp32_ota_version_dir)
                    esp32_ota_version_list = sorted(esp32_ota_version_list, key=cmp_to_key(compare_version), reverse=True)
                    if len(esp32_ota_version_list):
                        latest_version["esp32_ota"] = esp32_ota_version_list[0]

        if len(latest_version) != 0:
            latest_version["release"] = release_version
            version_path = os.path.join(build_path, "version.txt")
            data = json.dumps(latest_version, indent=4, sort_keys=True)
            with open(version_path, "w") as version_file:
                version_file.write(data)
            return True
        else:
            return False

    def build_release_notes():
        release_notes_path = os.path.join(build_path, "release_notes.md")
        shutil.copy("README.md", release_notes_path)
        return True

    def build_firmware():
        root = os.path.dirname(__file__)

        # read version info
        version_path = os.path.join(build_path, "version.txt")
        with open(version_path, "r") as version_file:
            read_data = version_file.read()
            if len(read_data):
                version_info = json.loads(read_data)
            else:
                return False

        # mkdir build/module_firmware
        firmware_path = os.path.join(build_path, "firmware")
        if os.path.exists(firmware_path):
            rmtree(firmware_path)
        os.mkdir(firmware_path)

        modules_path = os.path.join(firmware_path, "modules")
        esp32_path = os.path.join(firmware_path, "esp32")
        os.mkdir(modules_path)
        os.mkdir(esp32_path)

        for key in version_info.keys():
            # modules
            if key in module_list:
                module_name = key
                version_name = version_info[key]
                bin_name = module_name + ".bin"

                bin_path = os.path.join(root, module_name, version_name, bin_name)
                dest_path = os.path.join(modules_path, bin_name)
                shutil.copy(bin_path, dest_path)
                print(f"copy {module_name} {version_name}")
            elif key in ["esp32_app", "esp32_ota"]:
                module_name = "esp32"
                version_name = version_info[key]
                bin_names = [
                    "bootloader.bin",
                    "esp32.bin",
                    "ota_data_initial.bin",
                    "partitions.bin",
                ] if key == "esp32_app" else ["modi_ota_factory.bin"]

                for bin_name in bin_names:
                    sub_name = "app" if key == "esp32_app" else "ota"
                    bin_path = os.path.join(root, module_name, sub_name, version_name, bin_name)
                    dest_path = os.path.join(esp32_path, bin_name)
                    shutil.copy(bin_path, dest_path)
                    print(f"copy esp {sub_name} {version_name}")
            elif key in ["bootloader_e103", "bootloader_e230"]:
                module_name = "bootloader"
                chip_version = key.split("_")[1]
                version_name = version_info[key]
                bin_names = [
                    key + ".bin",
                    "second_" + key + ".bin",
                ]

                for bin_name in bin_names:
                    bin_path = os.path.join(root, module_name, chip_version, version_name, bin_name)
                    dest_path = os.path.join(modules_path, bin_name)
                    shutil.copy(bin_path, dest_path)
                    print(f"copy bootloader {chip_version} {version_name}")

        owd = os.getcwd()
        os.chdir(build_path)
        shutil.make_archive("firmware", "zip", firmware_path)
        os.chdir(owd)

        if os.path.exists(firmware_path):
            rmtree(firmware_path)

        shutil.make_archive(release_version, "zip", build_path)
        shutil.move(f"{release_version}.zip", os.path.join(build_path, f"{release_version}.zip"))

        return True

    if not build_version(release_version):
        print("build version fail")
        return False

    if not build_release_notes():
        print("build release_notes fail")
        return False

    if not build_firmware():
        print("build firmware fail")
        return False

    return True

if __name__ == "__main__":

    # remove build path first
    if os.path.exists(build_path):
        rmtree(build_path)
    os.mkdir(build_path)

    if len(sys.argv) == 2:
        release_version = sys.argv[1]
    else:
        release_version = ""

    # build firmware, version, release notes
    ret = build(release_version)

    if ret:
        print(f"build {release_version} success")
        sys.exit(0)
    else:
        print(f"build {release_version} fail")
        sys.exit(1)