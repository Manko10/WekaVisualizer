from PyQt5.QtGui import QPainter, QColor, QTransform, QFont, QFontMetrics, QPen, QPolygon, QDrag
from PyQt5.QtCore import QSize, QPoint, QPointF, QLineF, QRect, QRectF, Qt, QSizeF, QTimer, pyqtSignal
from PyQt5.QtWidgets import *
from data import Relation
import abc


class VisWidget(QGraphicsView):
    def __init__(self):
        self.scene = QGraphicsScene()
        super().__init__(self.scene)
        self.relation = None
        self.setRenderHint(QPainter.Antialiasing)

    def setRelation(self, rel: Relation):
        """
        Initialize widget with L{data.Relation}
        @param rel: data to be visualized
        """
        self.relation = rel
        self.updateWidget()

    @abc.abstractmethod
    def updateWidget(self):
        """
        Called when a new relation has been loaded.
        Implement this method in your subclasses.
        """
        pass


class StarPlot(VisWidget):
    """
    Radial star plot with multiple axes.
    """

    canvasAreaChanged = pyqtSignal()
    axisChanged       = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.bgColor        = QColor(220, 220, 220)

        self.labelFont      = QFont('Decorative', 10)

        self.class1Color = Qt.red
        self.class2Color = Qt.blue
        self.class1Pen   = QPen(self.class1Color)
        self.class2Pen   = QPen(self.class2Color)

        self.hoverOutlineWidth = 5
        self.axes              = []
        self.axisLabels        = []
        self.lineGroups        = []

        self.highlightedItems = []

        # timer for delayed plot update on resize events
        self.resizeUpdateDelay = 150
        self.__resizeDelayTimer = QTimer(self)
        self.__resizeDelayTimer.timeout.connect(self.canvasAreaChanged.emit)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scene.setBackgroundBrush(self.bgColor)

        self.setDragMode(QGraphicsView.RubberBandDrag)

        self.rubberBandChanged.connect(self.selectData)
        self.setCacheMode(QGraphicsView.CacheBackground)

    def updateWidget(self):
        for a in self.axes:
            self.scene.removeItem(a)
        self.axes.clear()
        self.axisLabels.clear()
        for l in self.lineGroups:
            self.scene.removeItem(l)
        self.lineGroups.clear()

        self.addAxes()
        self.addPoints()

    def addAxes(self):
        numDims = len(self.relation.fieldNames) - 1
        angle = 360 / numDims
        for i in range(numDims):
            axis = self.PlotAxis(self)
            self.scene.addItem(axis)
            axis.setRotation(angle * i)
            self.axes.append(axis)

            text = self.PlotAxisLabel(self.relation.fieldNames[i])
            text.setFont(self.labelFont)
            self.axisLabels.append(text)
            text.setParentItem(axis)

    def addPoints(self):
        numDims = len(self.relation.fieldNames) - 1
        datasets = self.relation.getNormalizedDatasets()
        for ds in datasets:
            points = []
            lines = []
            for i in range(numDims):
                p = self.PlotPoint(self, ds[i], ds[-1])
                p.setParentItem(self.axes[i])
                points.append(p)

                if 0 < i:
                    lines.append(self.PlotLine(self, p, points[i - 1]))
                if i == numDims - 1:
                    lines.append(self.PlotLine(self, p, points[0]))

            group = self.scene.createItemGroup(lines)
            self.lineGroups.append(group)

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

        sel = self.items(rubberBandRect)
        for s in sel:
            if type(s) == self.PlotLine:
                siblings = s.parentItem().childItems()
                for sib in siblings:
                    if QApplication.keyboardModifiers() == Qt.ControlModifier:
                        if sib in self.highlightedItems:
                            sib.highlighted = False
                            self.highlightedItems.remove(sib)
                    else:
                        sib.highlighted = True
                        self.highlightedItems.append(sib)

    def sizeHint(self):
        return QSize(1000, 1000)

    def minimumSizeHint(self):
        return QSize(400, 400)

    class PlotAxis(QGraphicsItem):
        ItemAxisLenHasChanged = 0x9901

        def __init__(self, view):
            super().__init__()
            self.view = view

            self.padding = 30
            self.__canvasW = view.rect().size().width() - self.padding
            self.__canvasH = view.rect().size().height() - self.padding

            self.axesColor = QColor(150, 150, 150)
            self.axesWidth = 1
            self.axesWidthHighl = 3
            self.axisGrabbed = False
            self.axesPen = QPen(self.axesColor, self.axesWidth)

            self.setAcceptHoverEvents(True)
            self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

            self.__canvasMaxDim = 0
            self.__boundingRect = None

            self.view.canvasAreaChanged.connect(self.updateCanvasGeoemtry)

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

        def mouseReleaseEvent(self, event):
            self.axisGrabbed = False
            self.setCursor(Qt.PointingHandCursor)

        def updateCanvasGeoemtry(self):
            self.view.setUpdatesEnabled(False)
            self.__canvasW = self.view.rect().size().width() - self.padding
            self.__canvasH = self.view.rect().size().height() - self.padding
            self.__canvasMaxDim = min(self.__canvasW, self.__canvasH)
            lw = max(self.axesWidth, self.axesWidthHighl) / 2 + 4
            self.__boundingRect = QRectF(QPoint(0 - lw, 0 - lw), QPoint(self.__canvasMaxDim / 2 + lw, lw))
            self.itemChange(self.ItemAxisLenHasChanged, None)
            self.view.setUpdatesEnabled(True)

        def itemChange(self, change, variant):
            if change == self.ItemAxisLenHasChanged or change == QGraphicsItem.ItemRotationHasChanged:
                self.view.axisChanged.emit()
            return super().itemChange(change, variant)

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget=None):
            qp.setPen(self.axesPen)
            qp.drawLine(QPoint(0, 0), QPoint(min(self.__canvasW, self.__canvasH) / 2, 0))

        def boundingRect(self):
            if self.__boundingRect is None:
                self.updateCanvasGeoemtry()
            return self.__boundingRect

    class PlotAxisLabel(QGraphicsTextItem):
        def __init__(self, text):
            super().__init__(text)
            self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget=None):
            p = self.parentItem()
            pRot = p.rotation()
            pRec = p.boundingRect()
            if 90 < pRot < 270:
                self.setRotation(180)
                self.setPos(pRec.width(), 0)
            else:
                self.setPos(pRec.width() - self.boundingRect().width(), 0)
            super().paint(qp, option, widget)

    class PlotPoint(QGraphicsItem):
        def __init__(self, view, val, cls):
            super().__init__()
            self.val = val
            self.cls = cls
            self.view = view

            self.__axisLen = 0
            self.__boundingRect = None

            view.axisChanged.connect(self.updateAxisLen)

        def updateAxisLen(self):
            self.__axisLen = self.parentItem().boundingRect().width()
            self.__boundingRect = QRectF(QPoint(self.val * self.__axisLen - 2, -2), QPoint(self.val * self.__axisLen + 2, 2))

        def itemChange(self, change, variant):
            if change == StarPlot.PlotAxis.ItemAxisLenHasChanged:
                print("child!")
            return super().itemChange(change, variant)

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
            # TODO: don't hardcode
            pen = QPen(QColor(0, 0, 255, 80))
            if "1" == self.cls:
                pen = QPen(QColor(255, 0, 0, 80))
            pen.setWidth(1)
            qp.setPen(pen)
            qp.drawRect(self.boundingRect())

        def boundingRect(self):
            if self.__boundingRect is None:
                self.updateAxisLen()
            return self.__boundingRect

    class PlotLine(QGraphicsLineItem):
        def __init__(self,  view, p1, p2):
            super().__init__()
            self.p1 = p1
            self.p2 = p2
            self.cls = p1.cls
            self.highlighted = False

            self.__p1Point = None
            self.__p2Point = None

            # TODO: don't hardcode
            self.__pen1 = (QPen(QColor(0, 0, 255, 80)), QPen(QColor(0, 0, 255, 200)))
            self.__pen1[0].setWidth(1)
            self.__pen1[1].setWidth(3)
            self.__pen2 = (QPen(QColor(255, 0, 0, 80)),  QPen(QColor(255, 0, 0, 200)))
            self.__pen2[0].setWidth(1)
            self.__pen2[1].setWidth(3)

            self.updateLine()
            view.axisChanged.connect(self.updateLine)

        def updateLine(self):
            p1 = self.p1.mapToScene(self.p1.boundingRect().center())
            p2 = self.p2.mapToScene(self.p2.boundingRect().center())
            self.setLine(QLineF(p1, p2))

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
            if self.cls == "1":
                self.setPen(self.__pen1[int(self.highlighted)])
            else:
                self.setPen(self.__pen2[int(self.highlighted)])
            super().paint(qp, option, widget)

