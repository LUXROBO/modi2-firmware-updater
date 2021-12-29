from modi_winusb import ModiWinUsbComPort, list_modi_winusb_paths
import time
import threading

stop = False

def handle_received(device):
    global stop

    while not stop:
        recv = device.read()
        if recv == None:
            print("disconnected")
            stop = True
            break
        print(recv)
        time.sleep(1)

    device.close()

modi_paths = list_modi_winusb_paths()

if len(modi_paths) == 0:
    raise Exception("No MODI port is connected")

device = ModiWinUsbComPort(modi_paths[0])
threading.Thread(target=handle_received, daemon=True, args=(device, )).start()

while not stop:
    input_data = input()

    if input_data == "exit":
        stop = True
        break

device.close()