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
                        rel.datasets.append(fields)
            except:
                raise Exception("ARFF parsing error!")

        return rel


class Relation(object):
    def __init__(self):
        self.relName    = ""
        self.fieldNames = []
        self.datasets   = []
        self.classes    = set()

        self.__normed_datasets = None

        self.__minVals = None
        self.__maxVals = None

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
