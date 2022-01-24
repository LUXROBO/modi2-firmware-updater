import sys
import argparse

from PyQt5 import QtWidgets

from modi2_multi_uploader.gui_firmware_upload import Form

def run_gui(debug=False, multi=True, develop=False):
    if multi:
        print("Running MODI+ Multi Uploader")
    else:
        print("Running MODI+ Uploader")

    app = QtWidgets.QApplication(sys.argv)
    w = Form(debug=debug, multi=multi, develop=develop)
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
    parser.add_argument(
        '--develop', type=str, default="False",
        choices=["False", "True"],
        help='develop mode'
    )
    args = parser.parse_args()
    debug = (args.debug == 'True')
    multi = (args.multi == 'True')
    develop = (args.develop == 'True')

    run_gui(debug, multi, develop)