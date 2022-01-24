import sys
import argparse

from PyQt5 import QtWidgets

from modi2_multi_uploader.gui_firmware_upload import Form

def run_gui(debug=False, multi=True):
    if multi:
        print("Running MODI+ Multi Uploader")
    else:
        print("Running MODI+ Uploader")

    app = QtWidgets.QApplication(sys.argv)
    w = Form(debug=debug, multi=multi)
    ret = app.exec()

    if multi:
        print(f"Terminating MODI+ Multi Uploader")
    else:
        print(f"Terminating MODI+ Uploader")

    sys.exit(ret)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug', type=str, default="False",
        choices=["False", "True"],
        help='debug mode'
    )
    parser.add_argument(
        '--multi', type=str, default="True",
        choices=["False", "True"],
        help='multi uploader'
    )

    args = parser.parse_args()
    debug = (args.debug == 'True')
    multi = (args.multi == 'True')

    run_gui(debug, multi)