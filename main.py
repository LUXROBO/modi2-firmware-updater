import sys
import argparse

from PyQt5 import QtWidgets

from modi2_multi_uploader.gui_firmware_upload import Form


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug', type=str, default="False",
        choices=["False", "True"],
        help='debug mode'
    )
    args = parser.parse_args()
    debug = (args.debug == 'True')
    print("Running MODI2 Multi Uploader")
    app = QtWidgets.QApplication(sys.argv)
    w = Form(debug=debug)
    ret = app.exec()
    print("Terminating MODI2 Multi Uploader")
    sys.exit(ret)
