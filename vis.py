from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QTransform, QFont, QFontMetrics, QPen, QPolygon
from PyQt5.QtCore import QSize, QPoint, QPointF, QLineF, QRect, QRectF, Qt, QSizeF, pyqtSignal
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem, QStyleOptionGraphicsItem, QGraphicsTextItem, QGraphicsLineItem, QGraphicsItemGroup
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

    geometryChanged = pyqtSignal()

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

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scene.setBackgroundBrush(self.bgColor)

        self.setDragMode(QGraphicsView.RubberBandDrag)

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
                p = self.PlotPoint(ds[i], ds[-1])
                p.setParentItem(self.axes[i])
                points.append(p)

                if 0 < i:
                    lines.append(self.PlotLine(self, p, points[i - 1]))
                if i == numDims - 1:
                    lines.append(self.PlotLine(self, p, points[0]))

            group = self.scene.createItemGroup(lines)
            self.lineGroups.append(group)

    def resizeEvent(self, event):
        # center scene in viewport
        r = self.rect()
        t = QTransform()
        t.translate(-r.width() / 2, -r.height() / 2)
        r = QRectF(QPointF(r.x(), r.y()) * t, QSizeF(r.width(), r.height()))
        self.setSceneRect(r)

    def paintEvent(self, event):
        super().paintEvent(event)
        self.geometryChanged.emit()

    def sizeHint(self):
        return QSize(1000, 1000)

    def minimumSizeHint(self):
        return QSize(400, 400)

    class PlotAxis(QGraphicsItem):
        def __init__(self, view):
            super().__init__()
            self.view = view

            self.padding = 30
            self.canvasW = view.rect().size().width() - self.padding
            self.canvasH = view.rect().size().height() - self.padding

            self.axesColor = QColor(150, 150, 150)
            self.axesWidth = 1
            self.axesWidthHighl = 3
            self.axisGrabbed = False
            self.axesPen = QPen(self.axesColor, self.axesWidth)

            self.setAcceptHoverEvents(True)

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

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget=None):
            self.canvasW = self.view.rect().size().width() - self.padding
            self.canvasH = self.view.rect().size().height() - self.padding

            qp.setPen(self.axesPen)
            qp.drawLine(QPoint(0, 0), QPoint(min(self.canvasW, self.canvasH) / 2, 0))

        def boundingRect(self):
            lw = max(self.axesWidth, self.axesWidthHighl) / 2 + 4   # make bounding box slightly larger to increase click area
            return QRectF(QPoint(0 - lw, 0 - lw), QPoint(min(self.canvasW, self.canvasH) / 2 + lw, lw))

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
        def __init__(self, val, cls):
            super().__init__()
            self.val = val
            self.cls = cls

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
            # TODO: don't hardcode
            pen = QPen(QColor(0, 0, 255, 80))
            if "1" == self.cls:
                pen = QPen(QColor(255, 0, 0, 80))
            pen.setWidth(1)
            qp.setPen(pen)
            qp.drawRect(self.boundingRect())

        def boundingRect(self):
            axisLen = self.parentItem().boundingRect().width()
            return QRectF(QPoint(self.val * axisLen - 2, -2), QPoint(self.val * axisLen + 2, 2))

    class PlotLine(QGraphicsLineItem):
        def __init__(self,  view, p1, p2):
            super().__init__()
            self.p1 = p1
            self.p2 = p2
            self.cls = p1.cls
            view.geometryChanged.connect(self.updateLine)
            self.updateLine()

        def pointPos(self, point):
            return point.mapToScene(point.boundingRect().center())

        def updateLine(self):
            self.setLine(QLineF(self.pointPos(self.p1), self.pointPos(self.p2)))

        def paint(self, qp: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
            # TODO: don't hardcode
            pen = QPen(QColor(0, 0, 255, 80))
            if "1" == self.cls:
                pen = QPen(QColor(255, 0, 0, 80))
            pen.setWidth(1)
            self.setPen(pen)
            super().paint(qp, option, widget)

