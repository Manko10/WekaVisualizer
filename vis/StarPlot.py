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

from PyQt5.QtGui import QPainter, QColor, QTransform, QFont, QPen, QCursor, QVector2D, QFontMetrics
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from vis.VisWidget import VisWidget
from data import Relation
import math


class StarPlot(VisWidget):
    """
    Radial star plot with multiple axes.
    """

    canvasAreaChanged = pyqtSignal()
    axisChanged       = pyqtSignal()
    selectionChanged  = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.__bgColor = QColor(255, 255, 255)
        self.scene.setBackgroundBrush(self.__bgColor)

        self.labelFont = QFont('Decorative', 8)

        self.class1Color = Qt.red
        self.class2Color = Qt.blue
        self.class1Pen   = QPen(self.class1Color)
        self.class2Pen   = QPen(self.class2Color)

        self.axes       = []
        self.axisAngles = []
        self.axisLabels = []
        self.lineGroups = []

        self.highlightedItems = set()
        self.highlightedRings = set()
        self.activeClasses    = set()

        # timer for delayed plot update on resize events
        self.resizeUpdateDelay = 150
        self.__resizeDelayTimer = QTimer(self)
        self.__resizeDelayTimer.timeout.connect(self.canvasAreaChanged.emit)

        self.selectionUpdateDelay = 200
        self.__selectionUpdateTimer = QTimer(self)
        self.__selectionUpdateTimer.timeout.connect(self.selectionChanged.emit)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setDragMode(QGraphicsView.RubberBandDrag)

        self.rubberBandChanged.connect(self.selectData)
        self.setCacheMode(QGraphicsView.CacheBackground)

        self.colorDialog = QColorDialog()

    @property
    def bgColor(self):
        return self.__bgColor

    @bgColor.setter
    def bgColor(self, color):
        self.__bgColor = color
        self.scene.setBackgroundBrush(self.__bgColor)

    def getClassColor(self, cls):
        if self.plotPalette is None or cls not in self.plotPalette:
            return QColor()

        return self.plotPalette[cls]

    def setRelation(self, rel: Relation):
        super().setRelation(rel)
        self.activeClasses = self.relation.activeClasses

    def updateWidget(self):
        self.setUpdatesEnabled(False)

        if self.relation is None:
            return

        # save axis rotations, but only if we don't have a new dataset with a different number of axes
        self.axisAngles.clear()
        if len(self.axes) == len(self.relation.fieldNames) - 1:
            for a in self.axes:
                self.axisAngles.append(a.rotation())

        self.lineGroups.clear()
        self.highlightedItems.clear()
        self.highlightedRings.clear()
        self.axisLabels.clear()
        self.axes.clear()
        self.scene.clear()

        self.addAxes()
        self.addPoints()

        if self.axisAngles:
            self.reparentLines()

        self.setUpdatesEnabled(False)

    def addAxes(self):
        numDims = len(self.relation.fieldNames) - 1
        angle = 360 / numDims
        axisDomains = self.relation.axisDomains
        for i in range(numDims):
            axis = PlotAxis(self)
            self.scene.addItem(axis)
            if self.axisAngles and i < len(self.axisAngles):
                axis.setRotation(self.axisAngles[i])
            else:
                axis.setRotation(angle * i)
            self.axes.append(axis)

            domain = axisDomains[i]
            text = PlotAxisLabel("{}\n[{:.2f},{:.2f}]".format(self.relation.fieldNames[i], domain[0], domain[1]))
            text.setFont(self.labelFont)
            self.axisLabels.append(text)
            text.setParentItem(axis)

    def addPoints(self):
        numDims = len(self.relation.fieldNames) - 1
        datasets = self.relation.getScaledDatasets()
        for ds in datasets:
            points = []
            lines = []
            for i in range(numDims):
                p = PlotPoint(self, ds[i], ds[-1])
                p.setParentItem(self.axes[i])
                points.append(p)

                if 0 < i:
                    lines.append(PlotLine(self, points[i - 1], p))
                if i == numDims - 1:
                    lines.append(PlotLine(self, p, points[0]))

            group = self.scene.createItemGroup(lines)
            group.dataClassLabel = points[0].cls
            self.lineGroups.append(group)

    def reparentLines(self):
        for lg in self.lineGroups:
            lines = lg.childItems()
            lines = list(sorted(lines, key=lambda x: x.p1.parentItem().rotation()))

            numDims = len(lines)
            for i, l in enumerate(lines):
                l.p2 = lines[i + 1 if i + 1 < numDims else 0].p1

    def filterClasses(self, classes):
        """
        Filter classes without reloading the dataset.
        L{StarPlot.activeClasses} contains all currently active classes.

        @param classes class names to filter by
        """
        items = self.scene.items()
        for i in items:
            if type(i) == PlotLine or type(i) == PlotPoint:
                i.setVisible(i.cls in classes)

        self.activeClasses = classes

    def mouseDoubleClickEvent(self, event):
        self.colorDialog.setCurrentColor(self.bgColor)
        self.colorDialog.open(self._setBackgroundColor)

    def _setBackgroundColor(self):
        self.bgColor = self.sender().currentColor()

    def resizeEvent(self, event):
        self.setUpdatesEnabled(False)
        # center scene in viewport
        r = self.rect()
        t = QTransform()
        t.translate(-r.width() / 2, -r.height() / 2)
        r = QRectF(QPointF(r.x(), r.y()) * t, QSizeF(r.width(), r.height()))
        self.setSceneRect(r)
        self.__resizeDelayTimer.start(self.resizeUpdateDelay)
        self.setUpdatesEnabled(True)

    def selectData(self, rubberBandRect, fromScenePoint, toScenePoint):
        if fromScenePoint == toScenePoint:
            return

        if QApplication.keyboardModifiers() != Qt.ShiftModifier and QApplication.keyboardModifiers() != Qt.ControlModifier:
            # unselect all currently selected items
            for h in self.highlightedItems:
                h.highlighted = False
            self.highlightedItems.clear()
            self.highlightedRings.clear()

        sel = self.items(rubberBandRect)
        for s in sel:
            if type(s) == PlotLine:
                parent = s.parentItem()
                siblings = parent.childItems()

                if QApplication.keyboardModifiers() == Qt.ControlModifier:
                    for sib in siblings:
                        if sib in self.highlightedItems:
                            sib.highlighted = False
                            self.highlightedItems.remove(sib)
                    if parent in self.highlightedRings:
                        self.highlightedRings.remove(parent)
                else:
                    for sib in siblings:
                        sib.highlighted = True
                        self.highlightedItems.add(sib)
                    self.highlightedRings.add(parent)

        self.__selectionUpdateTimer.start(self.selectionUpdateDelay)

    def sizeHint(self):
        return QSize(1000, 1000)

    def minimumSizeHint(self):
        return QSize(400, 400)


class PlotAxis(QGraphicsObject):
    ItemAxisLenHasChanged = 0x9901

    def __init__(self, view):
        super().__init__()
        self.view = view

        self.p1 = QPoint(0, 0)
        self.p2 = QPoint(0, 0)

        self.paddingHoriz = 30
        self.paddingVert  = 60 + QFontMetrics(self.view.labelFont).height() * 2
        self.__canvasW = view.rect().size().width() - self.paddingHoriz
        self.__canvasH = view.rect().size().height() - self.paddingVert

        self.axesColor = QColor(150, 150, 150)
        self.axesWidth = 1
        self.axesWidthHighl = 3
        self.axisGrabbed = False
        self.axesPen = QPen(self.axesColor, self.axesWidth)

        self.setAcceptHoverEvents(True)
        self.setAcceptDrops(True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        self.__canvasMaxDim = 0
        self.__boundingRect = None

        # save original rotation during axis reordering
        self.__origRotation = self.rotation()
        self.__dragActive = False

        self.axisAnimation = QPropertyAnimation(self, b"relativeRotation")
        self.axisAnimation.setDuration(600)
        self.axisAnimation.setEasingCurve(QEasingCurve.InOutQuad)
        self.__relRotationStartValue = 0

        self.view.canvasAreaChanged.connect(self.updateCanvasGeometry)

    def initRelativeRotation(self):
        """
        When animating rotation using the L{relativeRotation}, call this method before
        starting the animation. Otherwise relative angles will be added up resulting in a much
        larger rotation than intended.
        """
        self.__relRotationStartValue = self.rotation()

    @pyqtProperty(float)
    def relativeRotation(self):
        """
        Q_PROPERTY for animating relative rotations. Fix the initial rotation first using
        L{initRelativeRotation()} before starting the animation.

        @return: current rotation
        """
        return self.rotation()

    @relativeRotation.setter
    def relativeRotation(self, rot):
        """
        Q_PROPERTY for animating relative rotations. Fix the initial rotation first using
        L{initRelativeRotation()} before starting the animation.
        """
        self.setRotation((self.__relRotationStartValue + rot) % 360)

    def hoverEnterEvent(self, event):
        self.axesPen.setWidth(self.axesWidthHighl)
        self.setCursor(Qt.PointingHandCursor)
        self.update()

    def hoverLeaveEvent(self, event):
        self.axesPen.setWidth(self.axesWidth)
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        self.axisGrabbed = True
        self.setCursor(Qt.ClosedHandCursor)

        if not self.__dragActive:
            self.__origRotation = self.rotation()
            self.__dragActive = True

    def mouseMoveEvent(self, event):
        if self.__dragActive:
            mousePos = self.view.mapToScene(self.view.mapFromGlobal(QCursor.pos()))
            vec1 = QVector2D(mousePos)
            vec1.normalize()
            trans = QTransform()
            trans.rotate(self.rotation())
            vec2 = QVector2D(self.p2 * trans)
            vec2.normalize()
            angle = math.acos(max(-1, min(1, QVector2D.dotProduct(vec1, vec2)))) * 180 / math.pi

            # clockwise rotation
            if vec1.y() * vec2.x() < vec1.x() * vec2.y():
                angle *= -1

            angle = (self.rotation() + angle) % 360
            self.setRotation(angle)

    def mouseReleaseEvent(self, event):
        self.axisGrabbed = False
        self.setCursor(Qt.PointingHandCursor)

        if self.__dragActive:
            relRotation = (self.rotation() - self.__origRotation) % 360
            clockwise = (relRotation <= 180)
            angleModifier = 360 - self.__origRotation
            relOwnAngle = (self.rotation() + angleModifier) % 360
            angleDiff = 360 / len(self.view.axes)
            numSteps = 0
            for a in self.view.axes:
                if a == self:
                    continue

                r = a.rotation()
                relAngle = (r + angleModifier) % 360
                if clockwise and relAngle - relOwnAngle < 0:
                    a.axisAnimation.setStartValue(0)
                    a.axisAnimation.setEndValue(-angleDiff)
                    a.initRelativeRotation()
                    a.axisAnimation.start()
                    numSteps += 1
                elif not clockwise and relAngle - relOwnAngle > 0:
                    a.axisAnimation.setStartValue(0)
                    a.axisAnimation.setEndValue(angleDiff)
                    a.initRelativeRotation()
                    a.axisAnimation.start()
                    numSteps -= 1

            newRot = (self.__origRotation + (numSteps * angleDiff)) % 360
            relRotation = newRot - self.rotation()
            # make sure we don't rotate a full circle when crossing 0°
            if relRotation < -180:
                relRotation %= 360

            self.axisAnimation.setStartValue(0)
            self.axisAnimation.setEndValue(relRotation)
            self.initRelativeRotation()
            self.axisAnimation.start()
            self.__origRotation = newRot

            # redraw all lines between points of neighboring axes
            self.view.reparentLines()
        self.__dragActive = False

    def updateCanvasGeometry(self):
        self.view.setUpdatesEnabled(False)
        self.__canvasW = self.view.rect().size().width() - self.paddingHoriz
        self.__canvasH = self.view.rect().size().height() - self.paddingVert
        self.__canvasMaxDim = min(self.__canvasW, self.__canvasH)
        lw = max(self.axesWidth, self.axesWidthHighl) / 2 + 4
        self.__boundingRect = QRectF(QPoint(0 - lw, 0 - lw), QPoint(self.__canvasMaxDim / 2 + lw, lw))
        self.itemChange(self.ItemAxisLenHasChanged, None)
        self.view.setUpdatesEnabled(True)

    def itemChange(self, change, variant):
        if change == self.ItemAxisLenHasChanged or \
                (change == QGraphicsItem.ItemRotationHasChanged and self.view.relation.numDatasets < 200):
            self.view.axisChanged.emit()
        return super().itemChange(change, variant)

    def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget=None):
        qp.setPen(self.axesPen)
        self.p2 = QPoint(min(self.__canvasW, self.__canvasH) / 2, 0)
        qp.drawLine(self.p1, self.p2)

    def boundingRect(self):
        if self.__boundingRect is None:
            self.updateCanvasGeometry()
        return self.__boundingRect


class PlotAxisLabel(QGraphicsTextItem):
    def __init__(self, text):
        super().__init__(text)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget=None):
        p = self.parentItem()
        pRot = p.rotation()
        trans = QTransform()
        trans.rotate(-p.rotation())

        p2Scene = p.mapToScene(p.p2)
        if 0 <= pRot < 90:
            trans.translate(p2Scene.x() - self.boundingRect().width(), p2Scene.y())
        elif 90 <= pRot < 180:
            trans.translate(p2Scene.x(), p2Scene.y())
        elif 180 <= pRot < 270:
            trans.translate(p2Scene.x(), p2Scene.y() - self.boundingRect().height())
        elif 270 <= 360:
            trans.translate(p2Scene.x() - self.boundingRect().width(), p2Scene.y() - self.boundingRect().height())
        self.setTransform(trans)

        super().paint(qp, option, widget)


class PlotPoint(QGraphicsItem):
    def __init__(self, view, val, cls):
        super().__init__()
        self.val = val
        self.cls = cls
        self.view = view

        self.__axisLen = 0
        self.__boundingRect = None

        self._pen = None

        self.updateColor()
        view.plotPaletteChanged.connect(self.updateColor)
        view.axisChanged.connect(self.updateAxisLen)

    def updateColor(self):
        self._pen = QPen(self.view.getClassColor(self.cls))

    def updateAxisLen(self):
        self.__axisLen = self.parentItem().boundingRect().width()
        self.__boundingRect = QRectF(QPoint(self.val * self.__axisLen - 2, -2), QPoint(self.val * self.__axisLen + 2, 2))

    def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        qp.setPen(self._pen)
        qp.drawRect(self.boundingRect())

    def boundingRect(self):
        if self.__boundingRect is None:
            self.updateAxisLen()
        return self.__boundingRect


class PlotLine(QGraphicsLineItem):
    def __init__(self, view, p1, p2):
        super().__init__()
        self.p1 = p1
        self.p2 = p2
        self.cls = p1.cls
        self.view = view
        self.highlighted = False
        self.lineWidth = 1
        self.lineWidthHighl = 4
        self._pen = None
        self._penHighl = None

        self.updateColor()
        self.updateLine()
        view.plotPaletteChanged.connect(self.updateColor)
        view.axisChanged.connect(self.updateLine)

    def updateColor(self):
        color = self.view.getClassColor(self.cls)
        self._pen = QPen(color)
        self._pen.setWidth(self.lineWidth)
        colorHighl = QColor(color)
        colorHighl.setAlpha(255)
        self._penHighl = QPen(colorHighl)
        self._penHighl.setWidth(self.lineWidthHighl)

    def updateLine(self):
        p1 = self.p1.mapToScene(self.p1.boundingRect().center())
        p2 = self.p2.mapToScene(self.p2.boundingRect().center())
        self.setLine(QLineF(p1, p2))

    def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        self.setPen(self._pen if not self.highlighted else self._penHighl)
        super().paint(qp, option, widget)

