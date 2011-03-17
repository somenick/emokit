import math
import numpy
import emotiv

from PyQt4.QtGui import QWidget, QApplication, QVBoxLayout, QPainter, QColor

rhythms = {
    'delta': (0, 4),
    'theta': (4, 8),
    'alpha': (8, 13),
    'beta': (13, 30),
    'gamma': (30, 45),
    'mu': (8, 13)
    }

class RhythmWidget(QWidget):
    def __init__(self, loc):
        QWidget.__init__(self)
        self.loc = loc
        self.strength = 0
        self.resize(500, 100)
        self.repaint()
    
    def paintEvent(self, evt):
        painter = QPainter(self)
        painter.drawText(10, 50, self.loc)
        painter.fillRect(100, 0, self.strength, 100, QColor(0,100,0))
        
    def update(self, v):
        self.strength = 100 + math.log(v) * 10
        self.repaint()

class Viewer(QWidget):
    def __init__(self, loc):
        QWidget.__init__(self)
        self.resize(500, 800)
        self.strengths = {}
        self._src = emotiv.Emotiv()
        
        def read_func():
            results = []
            for packet in self._src.read(1):
                results.append(getattr(packet, loc)[0])
            return numpy.array(results)

        self.read = read_func

        self.widgets = dict(zip(rhythms.keys(), map(RhythmWidget, rhythms.keys())))

        layout = QVBoxLayout()
        for _, widget in self.widgets.items():
            layout.addWidget(widget)

        self.setLayout(layout)
        
    def start(self):
        while True:
            data = self.read() - 4000
            freq_data = numpy.abs(numpy.fft.fft(data)[:len(data)/2])

            for rhythm, (a,b) in rhythms.items():
                self.strengths[rhythm] = sum(freq_data[a:b])

            [self.widgets[rhythm].update(strength) for rhythm, strength in self.strengths.items()]

sensors = "AF3,F7,F3,FC5,T7,P7,O1,O2,P8,T8,FC6,F4,F8,AF4"

if __name__ == '__main__':
    try:
        loc = sys.argv[1]
        assert loc in sensors.split(',')
    except:
        print "Usage: python rhythms.py {%s}" % (sensors)
        sys.exit(0)

    app = QApplication(sys.argv)
    viewer = Viewer(loc)
    viewer.show()
    viewer.start()
    app.exec_()

