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
                fieldNames = []
                fieldTypes = []
                dataPart = False
                datasets = []
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
                                fieldNames.append(fields[1])
                                if "NUMERIC" == fields[2].upper():
                                    fieldTypes.append(float)
                                else:
                                    fieldTypes.append(str)
                            elif "@DATA" == fields[0].upper():
                                dataPart = True
                                rel.relName = relName
                                rel.fieldNames = fieldNames
                    elif dataPart:
                        fields = re.split(",", l.strip())
                        for i, t in enumerate(fieldTypes):
                            fields[i] = t(fields[i])

                        rel.classes.add(fields[-1])
                        datasets.append(fields)
                rel.datasets = datasets
            except:
                raise Exception("ARFF parsing error!")

        return rel


class Relation(QObject):
    dataChanged = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.relName         = ""
        self.__fieldNames    = []
        self.__fieldNamesAll = []
        self.__datasets      = []
        self.__datasetsAll   = []
        self.classes         = set()

        self.__normed_datasets = None

        self.__minVals = None
        self.__maxVals = None

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
        self.dataChanged.emit()

    def getMinVals(self):
        if self.__minVals is None:
            self.__calcMinMaxVals()
        return self.__minVals

    def getMaxVals(self):
        if self.__maxVals is None:
            self.__calcMinMaxVals()
        return self.__maxVals

    def __calcMinMaxVals(self):
        minVals = [float("inf")] * len(self.fieldNames)
        maxVals = [float("-inf")] * len(self.fieldNames)
        for ds in self.datasets:
            for i, d in enumerate(ds):
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

        self.__normed_datasets = None

        self.dataChanged.emit()

    def setClassFilter(self, includeClasses):
        self.__datasets = [d for d in self.__datasetsAll if d[-1] in includeClasses]
        self.__normed_datasets = None
        self.dataChanged.emit()

    def getNormalizedDatasets(self, normGlobally=False, minOffset=.1, maxOffset=.1):
        if self.__normed_datasets is None:
            self.__normed_datasets = []

            if normGlobally:
                minVals = [min(self.getMinVals())] * len(self.fieldNames)
                maxVals = [max(self.getMaxVals())] * len(self.fieldNames)
            else:
                minVals = self.getMinVals()
                maxVals = self.getMaxVals()

            minVals = [x - maxVals[i] * minOffset for i, x in enumerate(minVals)]
            maxVals = [x + x * maxOffset for x in maxVals]

            for ds in self.datasets:
                self.__normed_datasets.append([(x - minVals[i]) / (maxVals[i] - minVals[i]) if type(x) == float else x for i, x in enumerate(ds)])
        return self.__normed_datasets
