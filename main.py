#!/usr/bin/env python3
#
# Copyright (c) 2016 Janek Bevendorff
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import sys
from traceback import print_exception
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, QSize
import os.path
import data
from vis import StarPlot
from data import Relation


class WekaVisualizer(QWidget):
    defaultPalette = [
        QColor(255, 30, 0, 100),
        QColor(61, 28, 227, 100),
        QColor(255, 205, 0, 100),
        QColor(0, 232, 61, 100),
        QColor(240, 63, 40, 100),
        QColor(65, 45, 166, 100),
        QColor(240, 200, 40, 100),
        QColor(30, 179, 69, 100)
    ]

    def __init__(self):
        super().__init__()

        self._plotPalette = {}

        self.globalLayout         = QHBoxLayout()
        self.controlLayout        = QVBoxLayout()
        self.dynamicControlLayout = QVBoxLayout()
        self.plotLayout           = QVBoxLayout()
        self.plot                 = StarPlot()

        self.colorDialog = QColorDialog()
        self.colorDialog.setOption(QColorDialog.ShowAlphaChannel, True)

        self.activeSwatch = None

        self.selectionStatBars = []

        self.initUI()

    def initUI(self):
        self.resize(1024, 768)
        self.center()
        self.setWindowTitle(self.tr("WEKA Visualizer"))

        loadButton = QPushButton(self.tr("Load ARFF"))
        loadButton.clicked.connect(self.showInputFileDialog)

        self.controlLayout.addWidget(loadButton)
        self.controlLayout.addLayout(self.dynamicControlLayout)
        self.controlLayout.addStretch(1)

        self.plotLayout.addWidget(self.plot)

        self.globalLayout.addLayout(self.controlLayout, 1)
        self.globalLayout.addLayout(self.plotLayout, 5)

        self.setLayout(self.globalLayout)

        self.show()

        # TODO: remove this convenience line
        self.plot.setRelation(data.RelationFactory.loadFromFile("/home/janek/University/SS 15/Visualization/VisProject/gutenberg.arff"))
        self.addControlArea()
        self.plot.updateWidget()

    def addControlArea(self):
        # clear layout first
        for i in reversed(range(self.dynamicControlLayout.count())):
            self.dynamicControlLayout.itemAt(i).widget().setParent(None)

        self._addPlotControls()
        self._addPlotSelectionStats()
        self._addOptions()

    def _addPlotControls(self):
        # classes selector
        groupClasses = QGroupBox(self.tr("Classes"))
        classesVBox = QVBoxLayout()
        groupClasses.setLayout(classesVBox)

        self._plotPalette.clear()

        for i, c in enumerate(self.plot.relation.allClasses):
            hbox = QHBoxLayout()
            hbox.setAlignment(Qt.AlignLeft)

            checkBox = QCheckBox()
            checkBox.dataClassLabel = c
            checkBox.setObjectName("class" + str(i))
            checkBox.setChecked(True)
            checkBox.stateChanged.connect(self.toggleClassState)
            hbox.addWidget(checkBox)

            swatch = QPushButton()
            swatch.dataClassLabel = c
            swatch.setObjectName("swatch_class" + str(i))
            swatch.setFocusPolicy(Qt.NoFocus)
            swatch.setFixedSize(QSize(30, 30))
            swatch.clicked.connect(self.selectClassColor)
            pal = swatch.palette()
            color = self.defaultPalette[i % len(self.defaultPalette)]
            pal.setColor(QPalette.Button, color)
            self._plotPalette[c] = color
            swatch.setPalette(pal)
            hbox.addWidget(swatch)

            label = QLabel(c)
            label.dataClassLabel = c
            label.setTextFormat(Qt.PlainText)
            label.setObjectName("label_class" + str(i))
            label.setBuddy(swatch)
            hbox.addWidget(label)

            classesVBox.addLayout(hbox)

        self.plot.setPlotPalette(self._plotPalette)
        self.dynamicControlLayout.addWidget(groupClasses)

    def toggleClassState(self, state):
        s = self.sender()
        p = s.parent()
        name = s.objectName()
        state = (state != Qt.Unchecked)
        p.findChild(QWidget, "swatch_" + name).setEnabled(state)
        p.findChild(QWidget, "label_" + name).setEnabled(state)

        if state:
            self.plot.relation.setClassFilter(self.plot.relation.activeClasses | {s.dataClassLabel})
        else:
            self.plot.relation.setClassFilter(self.plot.relation.activeClasses - {s.dataClassLabel})

        self.updateSelectionStats()

    def _addPlotSelectionStats(self):
        self.selectionStatBars.clear()

        groupStats = QGroupBox(self.tr("Selection by Class"))
        statsVBox = QVBoxLayout()
        groupStats.setLayout(statsVBox)

        for c in self.plot.relation.allClasses:
            bar = QProgressBar()
            bar.dataClassLabel = c
            bar.setTextVisible(True)
            bar.setValue(0)
            self.selectionStatBars.append(bar)

            label = QLabel(c)
            label.setBuddy(bar)

            vbox = QVBoxLayout()
            vbox.addWidget(label)
            vbox.addWidget(bar)
            statsVBox.addLayout(vbox)

        self.plot.selectionChanged.connect(self.updateSelectionStats)
        self.updateSelectionStats()
        self.dynamicControlLayout.addWidget(groupStats)

    def updateSelectionStats(self):
        highlightsPerClass = {}
        for s in self.plot.highlightedRings:
            highlightsPerClass[s.dataClassLabel] = highlightsPerClass.get(s.dataClassLabel, 0) + 1

        for b in self.selectionStatBars:
            num = self.plot.relation.numDatasetsForClass(b.dataClassLabel)
            if 0 != num:
                b.setValue(highlightsPerClass.get(b.dataClassLabel, 0) / num * 100)
            pal = b.palette()
            pal.setColor(QPalette.Highlight, self._plotPalette[b.dataClassLabel])
            b.setPalette(pal)

    def _addOptions(self):
        groupOpts = QGroupBox(self.tr("Options"))
        optsVBox = QVBoxLayout()
        groupOpts.setLayout(optsVBox)

        # feature scaling
        scaleHBox = QHBoxLayout()
        scaleHBox.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        scaleOpt = QCheckBox()
        scaleOpt.setChecked(True)
        scaleOpt.stateChanged.connect(self.toggleScaleMode)
        scaleLabel = QLabel(self.tr("&Scale features"))
        scaleLabel.setBuddy(scaleOpt)
        scaleHBox.addWidget(scaleOpt)
        scaleHBox.addWidget(scaleLabel)
        optsVBox.addLayout(scaleHBox)

        self.dynamicControlLayout.addWidget(groupOpts)

    def toggleScaleMode(self, state):
        self.plot.relation.setScaleMode(Relation.ScaleModeLocal if state != Qt.Unchecked else Relation.ScaleModeGlobal)

    def selectClassColor(self):
        s = self.sender()
        self.activeSwatch = s
        self.colorDialog.setCurrentColor(s.palette().color(QPalette.Button))
        self.colorDialog.open(self.setNewClassColor)

    def setNewClassColor(self):
        color = self.sender().currentColor()
        if self.activeSwatch is not None:
            pal = self.activeSwatch.palette()
            pal.setColor(QPalette.Button, color)
            self.activeSwatch.setPalette(pal)

            className = self.activeSwatch.dataClassLabel
            self._plotPalette[className] = color
            self.plot.setPlotPalette(self._plotPalette)
            self.plot.updateWidget()

            self.updateSelectionStats()

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
            self.addControlArea()
            self.plot.updateWidget()


# override excepthook to correctly show tracebacks in PyCharm
def excepthook(extype, value, traceback):
    print_exception(extype, value, traceback)
    exit(1)

sys.excepthook = excepthook

if __name__ == '__main__':
    app = QApplication(sys.argv)
    vis = WekaVisualizer()
    sys.exit(app.exec_())

