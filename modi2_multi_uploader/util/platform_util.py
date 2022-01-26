def is_raspberrypi():
    import platform
    return platform.uname().node == 'raspberrypi'