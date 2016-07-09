from PyQt5.QtGui import QPainter, QColor, QTransform, QFont, QFontMetrics, QPen, QPolygon, QDrag, QCursor, QVector2D
from PyQt5.QtCore import QSize, QPoint, QPointF, QLineF, QRect, QRectF, Qt, QSizeF, QTimer, pyqtSignal
from PyQt5.QtWidgets import *
from data import Relation
import abc, math


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
        self.lineGroups.clear()
        self.highlightedItems.clear()
        self.axisLabels.clear()
        self.axes.clear()
        self.scene.clear()

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
                    lines.append(self.PlotLine(self, points[i - 1], p))
                if i == numDims - 1:
                    lines.append(self.PlotLine(self, p, points[0]))

            group = self.scene.createItemGroup(lines)
            self.lineGroups.append(group)

    def reparentLines(self):
        for lg in self.lineGroups:
            lines = lg.childItems()
            lines = list(sorted(lines, key=lambda x: x.p1.parentItem().rotation()))

            numDims = len(lines)
            for i, l in enumerate(lines):
                l.p2 = lines[i + 1 if i + 1 < numDims else 0].p1

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

            self.p1 = QPoint(0, 0)
            self.p2 = QPoint(0, 0)

            self.padding = 30
            self.__canvasW = view.rect().size().width() - self.padding
            self.__canvasH = view.rect().size().height() - self.padding

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
                angle = math.acos(QVector2D.dotProduct(vec1, vec2)) * 180 / math.pi

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
                        a.setRotation((r - angleDiff) % 360)
                        numSteps += 1
                    elif not clockwise and relAngle - relOwnAngle > 0:
                        a.setRotation((r + angleDiff) % 360)
                        numSteps -= 1
                self.setRotation((self.__origRotation + numSteps * angleDiff) % 360)
                self.__origRotation = self.rotation()
                self.view.reparentLines()
            self.__dragActive = False

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
            self.p2 = QPoint(min(self.__canvasW, self.__canvasH) / 2, 0)
            qp.drawLine(self.p1, self.p2)

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
            trans = QTransform()
            trans.rotate(-p.rotation())
            self.setPos(0, 0)

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

            view.axisChanged.connect(self.updateAxisLen)

        def updateAxisLen(self):
            self.__axisLen = self.parentItem().boundingRect().width()
            self.__boundingRect = QRectF(QPoint(self.val * self.__axisLen - 2, -2), QPoint(self.val * self.__axisLen + 2, 2))

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
            self.view = view
            self.highlighted = False

            # TODO: don't hardcode
            self.__pen1 = (QPen(QColor(255, 0, 0, 80)), QPen(QColor(255, 0, 0, 200)))
            self.__pen1[0].setWidth(1)
            self.__pen1[1].setWidth(3)
            self.__pen2 = (QPen(QColor(0, 0, 255, 80)),  QPen(QColor(0, 0, 255, 200)))
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

