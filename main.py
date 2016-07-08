#!/usr/bin/env python3

import sys
from traceback import print_exception
from PyQt5.QtWidgets import *
import os.path
import data
from vis import StarPlot


class WekaVisualizer(QWidget):
    def __init__(self):
        super().__init__()

        self.globalLayout  = QHBoxLayout()
        self.controlLayout = QVBoxLayout()
        self.plotLayout    = QVBoxLayout()
        self.plot          = StarPlot()

        self.initUI()

    def initUI(self):
        self.resize(1024, 768)
        self.center()
        self.setWindowTitle(self.tr("WEKA Visualizer"))

        loadButton = QPushButton(self.tr("Load ARFF"))
        loadButton.clicked.connect(self.showInputFileDialog)

        self.controlLayout.addWidget(loadButton)
        self.controlLayout.addStretch(1)

        self.plotLayout.addWidget(self.plot)

        self.globalLayout.addLayout(self.controlLayout, 1)
        self.globalLayout.addLayout(self.plotLayout, 5)

        self.setLayout(self.globalLayout)

        self.show()

        # TODO: remove this convenience line
        self.plot.setRelation(data.RelationFactory.loadFromFile("/home/janek/University/SS 15/Visualization/VisProject/gutenberg.arff"))

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def showInputFileDialog(self):
        fileName = QFileDialog.getOpenFileName(self, self.tr("Select WEKA ARFF file"),
                                               "", self.tr("WEKA Files (*.arff)"))
        if "" != fileName[0] and os.path.isfile(fileName[0]):
            self.plot.setRelation(data.RelationFactory.loadFromFile(fileName[0]))


# override excepthook to correctly show tracebacks in PyCharm
def excepthook(extype, value, traceback):
    print_exception(extype, value, traceback)
    exit(1)

sys.excepthook = excepthook

if __name__ == '__main__':
    app = QApplication(sys.argv)
    vis = WekaVisualizer()
    sys.exit(app.exec_())

