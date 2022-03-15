import os
from shutil import rmtree
from argparse import ArgumentParser

def make_clean():
    cwd = os.path.dirname(__file__)
    dirnames = ['__pycache__', 'build', 'dist']
    for d in dirnames:
        dirpath = os.path.join(cwd, d)
        if os.path.isdir(dirpath):
            rmtree(dirpath)

def make_executable(mode):
    make_clean()

    install_cmd = f"pyinstaller modi_single_updater.spec" if mode == "single" else f"pyinstaller modi_multi_updater.spec"

    result = os.system(install_cmd)

    if result != 0:
        exit(1)

    import platform
    if platform.system() == "Darwin":
        dmg_path = f"./dist/MODI+ Firmware Updater.dmg" if mode == "single" else f"./dist/MODI+ Firmware Multi Updater.dmg"

        if os.path.exists(dmg_path):
            os.remove(dmg_path)

        create_dmg_cmd = """create-dmg \
            --volname "MODI+ Firmware Updater" \
            --volicon "modi2_firmware_updater/assets/component/network_module.ico" \
            --window-pos 200 120 \
            --window-size 800 300 \
            --icon-size 100 \
            --icon "MODI+ Firmware Updater.app" 200 100 \
            --hide-extension "MODI+ Firmware Updater.app" \
            --app-drop-link 600 100 \
            "./dist/MODI+ Firmware Updater.dmg" \
            "./dist/MODI+ Firmware Updater.app"
        """

        if mode == "multi":
            create_dmg_cmd = """create-dmg \
                --volname "MODI+ Firmware Multi Updater" \
                --volicon "modi2_firmware_updater/assets/component/network_module.ico" \
                --window-pos 200 120 \
                --window-size 800 300 \
                --icon-size 100 \
                --icon "MODI+ Firmware Multi Updater.app" 200 100 \
                --hide-extension "MODI+ Firmware Multi Updater.app" \
                --app-drop-link 600 100 \
                "./dist/MODI+ Firmware Multi Updater.dmg" \
                "./dist/MODI+ Firmware Multi Updater.app"
            """

        result = os.system(create_dmg_cmd)

        if result != 0:
            exit(1)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        '--mode', type=str, default='single',
        choices=['single', 'multi']
    )
    args = parser.parse_args()
    mode = args.mode
    make_executable(mode)