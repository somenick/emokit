import numpy as np
import matplotlib
matplotlib.use('WXagg') # do this before importing pylab

import matplotlib.pyplot as plt
import emotiv
import wx

headset = emotiv.Emotiv()

X_BOUND = 1000

fig = plt.figure()
lines = {}
for sig in ['O1', 'P7', 'T7', 'FC5', 'F7', 'F3', 'AF3', 'FC6', 'T8', 'F8', 'P8', 'AF4', 'F4', 'O2']:
        ax = fig.add_subplot(111)
        t = np.arange(0, X_BOUND, 1)
        lines[sig], = ax.plot(t, [0]*len(t))
        lines[sig].set_label(sig)
        ax.set_ylabel(sig)
        ax.autoscale(False)
        ax.set_ybound(4000, 14000)

plt.legend()

def update_line(event):
        try:
                count = 0
                while True:
                        packet = headset.read(no_wait=True)
                        if packet == None:
                                print "%s packets in batch" % count
                                break
                        count += 1
                        for sig in lines.iterkeys():
                                data = lines[sig].get_ydata()
                                if len(data) >= X_BOUND:
                                        data = np.delete(data, 0)
                                data = np.append(data, getattr(packet, sig)[0])
                                lines[sig].set_ydata(data)
                fig.canvas.draw()
        finally:
                pass

id = wx.NewId()
actor = fig.canvas.manager.frame
timer = wx.Timer(actor, id=id)
timer.Start(100)
wx.EVT_TIMER(actor, id, update_line)

def on_close(event):
        timer.Stop()
        actor.Destroy()

wx.EVT_CLOSE(actor, on_close)

plt.show()
