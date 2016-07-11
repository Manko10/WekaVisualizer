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

from PyQt5.QtCore import QObject, pyqtSignal
import re


class RelationFactory(object):
    @staticmethod
    def loadFromFile(fileName):
        rel = Relation()

        with open(fileName, "r") as f:
            lines = f.readlines()

            try:
                relName = ""
                fieldNames   = []
                fieldTypes   = []
                dataPart     = False
                datasets     = []
                classColName = None
                skipCols     = []
                skipCounter  = 0
                for l in lines:
                    l = l.strip()
                    if "" == l or "%" == l[0]:
                        continue

                    if "@" == l[0]:
                        if not dataPart:
                            fields = re.split("\s+", l.strip())
                            if "@RELATION" == fields[0].upper():
                                relName = fields[1]
                            elif "@ATTRIBUTE" == fields[0].upper():
                                if "NUMERIC" == fields[2].upper() or "REAL" == fields[2].upper():
                                    fieldTypes.append(float)
                                    fieldNames.append(fields[1])
                                else:
                                    classColName = fields[1]
                                    skipCols.append(skipCounter)
                                skipCounter += 1
                            elif "@DATA" == fields[0].upper():
                                if len(fieldNames) != 0:
                                    if classColName is None:
                                        # class column is numeric, but we need a string
                                        classColName = fieldNames[-1]
                                        fieldTypes[-1] = str
                                    else:
                                        skipCols.pop()  # last column is class column, don't skip it
                                        fieldNames.append(classColName)
                                        fieldTypes.append(str)
                                    dataPart = True
                                    rel.relName = relName
                                    rel.fieldNames = fieldNames
                    elif dataPart:
                        fieldsTmp = re.split(",", l.strip())
                        fields = []
                        for i, f_ in enumerate(fieldsTmp):
                            if i not in skipCols:
                                fields.append(f_)

                        for i, t in enumerate(fieldTypes):
                            fields[i] = t(fields[i])

                        if len(fields) > 1:
                            rel.allClasses.add(fields[-1])
                            datasets.append(fields)
                rel.datasets = datasets
                rel.numDatasets = len(datasets)
                rel.activeClasses = set(rel.allClasses)
            except:
                raise Exception("ARFF parsing error!")

        return rel


class Relation(QObject):
    dataChanged = pyqtSignal()

    ScaleModeGlobal = 0
    ScaleModeLocal  = 2

    def __init__(self):
        super().__init__()

        self.relName            = ""
        self.__fieldNames       = []
        self.__fieldNamesAll    = []
        self.__datasets         = []
        self.__datasetsAll      = []
        self.__datasetsPerClass = {}
        self.allClasses         = set()
        self.activeClasses      = set()
        self.numDatasets        = 0

        self.__scaled_datasets = None
        self.__scale_mode       = self.ScaleModeLocal

        self.__minVals = None
        self.__maxVals = None

        self.__axisDomains = None

    @property
    def fieldNames(self):
        """
        Getter for field names. DO NOT use direct list access operations on the returned list as it will
        mess up data filtering. Use the setter to replace the full list instead.
        """
        return self.__fieldNames

    @fieldNames.setter
    def fieldNames(self, names):
        self.__fieldNamesAll = names
        self.__fieldNames = list(names)
        self.dataChanged.emit()

    @property
    def datasets(self):
        return self.__datasets

    @datasets.setter
    def datasets(self, datasets):
        """
        Getter for fdatasets. DO NOT use direct list access operations on the returned list as it will
        mess up data filtering. Use the setter to replace the full list instead.
        """
        self.__datasetsAll = datasets
        self.__datasets = list(datasets)
        self.__axisDomains = None
        for ds in self.__datasetsAll:
            self.__datasetsPerClass[ds[-1]] = self.__datasetsPerClass.get(ds[-1], 0) + 1
        self.dataChanged.emit()

    @property
    def axisDomains(self):
        if self.__axisDomains is None:
            if self.__scale_mode == self.ScaleModeLocal:
                self.__axisDomains = list(zip(self.minVals(), self.maxVals()))
            else:
                self.__axisDomains = [(min(self.minVals()), max(self.maxVals()))] * (len(self.fieldNames) - 1)

        return self.__axisDomains

    def numDatasetsForClass(self, cls):
        return self.__datasetsPerClass.get(cls, 0)

    def minVals(self):
        if self.__minVals is None:
            self.__calcMinMaxVals()
        return self.__minVals

    def maxVals(self):
        if self.__maxVals is None:
            self.__calcMinMaxVals()
        return self.__maxVals

    def __calcMinMaxVals(self):
        minVals = [float("inf")] * (len(self.fieldNames) - 1)
        maxVals = [float("-inf")] * (len(self.fieldNames) - 1)
        for ds in self.datasets:
            for i, d in enumerate(ds[:-1]):
                if type(d) != float:
                    continue

                minVals[i] = min(minVals[i], d)
                maxVals[i] = max(maxVals[i], d)

        if minVals[0] < float("inf"):
            self.__minVals = minVals
            self.__maxVals = maxVals

    def resetFilters(self):
        if len(self.__fieldNames) != len(self.__fieldNamesAll):
            self.__fieldNames = list(self.__fieldNames)

        if len(self.__datasets) != len(self.__datasetsAll):
            self.__datasets = list(self.__datasets)

        self.activeClasses = set(self.allClasses)
        self.__scaled_datasets = None

        self.dataChanged.emit()

    def setClassFilter(self, includeClasses):
        """
        Filter data by given class names.
        This method is kept here for preservation, but is basically obsolete. Filtering is done by toggling the
        visibility state of the drawn graphics items.

        @param includeClasses: class names to filter by
        """
        self.__datasets = [d for d in self.__datasetsAll if d[-1] in includeClasses]
        self.__scaled_datasets = None
        self.activeClasses = includeClasses
        self.dataChanged.emit()

    def setScaleMode(self, mode):
        """
        Set axis normalization/scaling mode
        @param mode: mode, L{ScaleModeLocal} or L{ScaleModeGlobal}
        """
        if mode != self.__scale_mode and mode in (self.ScaleModeGlobal, self.ScaleModeLocal):
            self.__scale_mode = mode
            self.__scaled_datasets = None
            self.__axisDomains = None
            self.dataChanged.emit()

    def getScaledDatasets(self, minOffset=.1, maxOffset=.1):
        if self.__scaled_datasets is None:
            self.__scaled_datasets = []

            if self.__scale_mode == self.ScaleModeGlobal:
                minVals = [min(self.minVals())] * (len(self.fieldNames) - 1)
                maxVals = [max(self.maxVals())] * (len(self.fieldNames) - 1)
            else:
                minVals = self.minVals()
                maxVals = self.maxVals()

            minVals = [x - maxVals[i] * minOffset for i, x in enumerate(minVals)]
            maxVals = [x + x * maxOffset for x in maxVals]

            for ds in self.datasets:
                self.__scaled_datasets.append([(x - minVals[i]) / (maxVals[i] - minVals[i]) if type(x) == float else x for i, x in enumerate(ds)])

        return self.__scaled_datasets
