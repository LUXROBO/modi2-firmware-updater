import sys
import argparse

from PyQt5 import QtWidgets

from modi2_firmware_updater.modi2_firmware_updater import Form

def run_gui(debug=False, multi=True):
    if multi:
        print("Running MODI+ Multi Firmware Updater")
    else:
        print("Running MODI+ Firmware Updater")

    app = QtWidgets.QApplication(sys.argv)
    w = Form(debug=debug, multi=multi)
    ret = app.exec()

    if multi:
        print(f"Terminating MODI+ Firmware Multi Updater")
    else:
        print(f"Terminating MODI+ Firmware Updater")

    sys.exit(ret)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug', type=str, default="False",
        choices=["False", "True"],
        help='debug mode'
    )
    parser.add_argument(
        '--multi', type=str, default="False",
        choices=["False", "True"],
        help='multi updater'
    )

    args = parser.parse_args()
    debug = (args.debug == 'True')
    multi = (args.multi == 'True')

    run_gui(debug, multi)
