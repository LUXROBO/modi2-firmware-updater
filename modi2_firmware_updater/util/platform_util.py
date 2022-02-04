import time

delay_option = False

def is_raspberrypi():
    import platform
    return platform.uname().node == 'raspberrypi'

def set_delay_option(option):
    global delay_option
    delay_option = option

def delay(span):
    global delay_option
    
    if delay_option:
        time.sleep(span)
    else:
        init_time = time.perf_counter()
        while time.perf_counter() - init_time < span:
            pass