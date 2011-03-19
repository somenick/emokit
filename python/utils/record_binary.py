import time
import emotiv
import multiprocessing
import sys

from PyQt4.QtGui import QApplication, QWidget, QLabel, QPainter, QColor, QFileDialog
from PyQt4.QtCore import Qt

class ClassifyGUI(QWidget):
    def __init__(self, conn, proc):
        QWidget.__init__(self)
        self.resize(640, 480)
        self.on = False
        self.conn = conn
        self.proc = proc

    def paintEvent(self, evt):
        color = QColor(0, 100, 0) if self.on else QColor(255, 0, 0)
        painter = QPainter(self)
        painter.fillRect(0,0,self.width(), self.height(), color)
        
    def keyPressEvent(self, evt):
        if evt.key() == Qt.Key_Space:
            self.on = True
            self.conn.send('1')
            self.repaint()

        elif evt.key() == Qt.Key_Escape:
            fn = QFileDialog.getSaveFileName(self, "Save the data",  '../../samples')
            self.conn.send('end,%s' % (fn))

    def keyReleaseEvent(self, evt):
        time.sleep(1./20)
        if evt.key() == Qt.Key_Space:
            self.on = False
            self.repaint()
            self.conn.send('0')

    def start(self):
        self.proc.start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    conn1, conn2 = multiprocessing.Pipe()

    headset = emotiv.Emotiv()
    
    def receive_data():
        on = False
        buf = ''
        
        while True:
            if conn1.poll():
                msg = conn1.recv()
                if msg == '1':
                    on = True
                elif msg == '0':
                    on = False
                elif msg.split(',')[0] == 'end':
                    open(msg.split(',')[1],'w').write(buf)

            if on:
                buf += headset.read().tostring()+'1\n'
            else:
                buf += headset.read().tostring()+'0\n'

            time.sleep(1./128)

    proc = multiprocessing.Process(target=receive_data)
    bl = ClassifyGUI(conn2, proc)
    bl.show()
    bl.start()
    app.exec_()


