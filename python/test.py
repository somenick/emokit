import emotiv
headset = emotiv.Emotiv()
try:
    while True:
        for packet in headset.dequeue():
            print packet.gyroX, packet.gyroY, packet.F3
finally:
    headset.close()
