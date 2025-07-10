import inspect
import linecache
import re
import sys

from cleversheep3.Test.Tester import Coordinator
from cleversheep3.Test.Tester import log

rProcCall = re.compile(r' *(?P<name>[a-zA-Z0-9_.]+)\(')
rFuncCall = re.compile(r'[^=]*= *(?P<name>[a-zA-Z0-9_.]+)\(')
rStepComment = re.compile(r'^ *#> (.*)')
rComment = re.compile(r'^ *#(.*)')


#{ Public
class TestSpecDB:
    def __init__(self):
        self._callMap = {}
        self._stepMap = {}

    def gatherTestSteps(self, func):
        f = TestMap.getTestMap(func)
        #self.dump(f)
        self.getMap(f)

    def getThing(self, func):
        return self._callMap[func.func.__code__]

    def getMap(self, func):
        getSteps = lambda func: dict(((func.code, stepLine), step.lines)
                                     for stepLine, step in func.steps)
        callMap = {func.func.__code__: func}
        stepMap = getSteps(func)
        for level, p in func.walk(select=lambda l, c: c.type == "func"):
            callMap[p.func.__code__] = p
            stepMap.update(getSteps(p))
        self._callMap.update(callMap)
        self._stepMap.update(stepMap)

    def dump(self, func):
        for level, p in func.walk():
            pad = "  " * level
            if p.type == "step":
                lines = str(p).splitlines()
                for i, line in enumerate(lines):
                    print("%s%s" % (pad, line))

    def runAndTrace(self, func, *args, **kwargs):
        runTracer = RunTracer(self._callMap, self._stepMap)
        runTracer.run(func, args, kwargs)
#}

#{ Internal
class PointOfInterest:
    def dump(self, ind=0):
        pass

    def walk(self, level=0, select=lambda l, c: True):
        return []

    @property
    def levelAdjust(self):
        return 0


class Step(PointOfInterest):
    sortV = 50
    type = "step"

    def __init__(self, lines):
        self.lines = list(lines)

    def __str__(self):
        return "\n".join(self.lines)


def isMethodOrFunc(obj):
    return inspect.isfunction(obj) or inspect.ismethod(obj)


def unwrapFunc(func):
    while hasattr(func, "undecorated"):
        func = func.undecorated
    return func


class TestMap(PointOfInterest):
    """Mapping of a test function (direct or indirect) to useful information.

    :Ivariables:
      func
        The function in question.
      code
        The code of the function.
      lines, startLine
        The text lines of the functions and the number of the line where the
        function's definition begins.
      invocations
        NOT SURE YET.
      steps
        The detailed steps extracted from the source code.

    """
    sortV = 100
    type = "func"
    _known = {}
    _classMap = {}

    def __init__(self, func):
        linecache.checkcache()
        self.func = func
        self.code = func.__code__
        try:
            func = unwrapFunc(func)
            self.lines, self.startLine = inspect.getsourcelines(func)
        except:
            self.startLine = 0
            self.lines = []
        self.invocations = []
        self.steps = []

    @property
    def levelAdjust(self):
        if getattr(self.func, "_cs_inline", None):
            return -1
        return 0

    def processInvocation(self, lineIdx, line, emitStep, module, klass):
        m = rProcCall.match(line) or rFuncCall.match(line)
        if m:
            emitStep()
            invokeName = m.group("name")
            if invokeName.startswith("self."):
                invokeName = invokeName[5:]
            calledFunc = getattr(module, invokeName, None)
            if calledFunc is None and klass is not None:
                calledFunc = klass.__dict__.get(invokeName, None)
                if calledFunc is None:
                    for base in klass.__bases__:
                        calledFunc = getattr(base, invokeName, None)
                        if calledFunc is not None:
                            break
            if calledFunc is None:
                return True
            self._classMap[calledFunc] = klass
            if not (isMethodOrFunc(calledFunc)
                    or hasattr(calledFunc, "_cs_isProcedural")):
                return True

            calledFunc = self.getTestMap(calledFunc)
            self.invocations.append((self.startLine + lineIdx, calledFunc))
            return True

    def getStepsAndCalls(self):
        """Find all test steps and function invocations for this function.

        """
        def emitStep():
            while step and not step[0].strip():
                step.pop(0)
            while step and not step[-1].strip():
                step.pop()
            if step:
                self.steps.append((self.startLine + lineIdx, Step(step)))
            step[:] = []

        step = []
        module = inspect.getmodule(self.func)
        klass = getattr(self.func, "__class__", None)
        if klass is None:
            klass = self._classMap.get(self.func, None)
        for lineIdx, line in enumerate(self.lines):
            m = rStepComment.match(line)
            if m:
                step.append(m.group(1))
                continue

            if rComment.match(line):
                continue

            if self.processInvocation(lineIdx, line, emitStep, module, klass):
                continue

            if line.strip():
                emitStep()
            else:
                step.append(line.rstrip())
        emitStep()

    def walk(self, level=0, select=lambda l, c: True):
        for i, p in sorted(self.invocations + self.steps,
                           key=lambda el: (el[0], el[1].sortV, el[1])):
            if p is self:
                continue
            if select(level, p):
                yield level, p
            for child in p.walk(level + 1 + p.levelAdjust, select=select):
                yield child

    def walkSteps(self):
        n = []
        for level, p in self.walk():
            if p.type == "step":
                while len(n) > level + 1:
                    n.pop()
                while len(n) <= level:
                    n.append(0)
                n[-1] += 1
                pad = "  " * level
                yield n, p.lines

    @classmethod
    def getTestMap(cls, func):
        if func not in cls._known:
            funcMap = TestMap(func)
            cls._known[func] = funcMap
            funcMap.getStepsAndCalls()
        return cls._known[func]


class RunTracer:
    def __init__(self, callMap, stepMap):
        self.traceTable = {
            "call": self.handleCall,
            "line": self.handleLine,
            "return": self.handleReturn,
        }
        self.code = self.func = None
        self.stack = []
        self.n = []
        self._callMap = callMap
        self._stepMap = stepMap
        self._prevKey = None

    def run(self, func, args, kwargs):
        self.oldTrace = sys.gettrace()
        self.lineTrace = None
        sys.settrace(self.trace)
        _cs_preamble_ = None
        try:
            func(*args, **kwargs)
        finally:
            sys.settrace(self.oldTrace)

    def _fallback(self, frame, event, arg):
        if self.oldTrace:
            return self.oldTrace(frame, event, arg)

    def trace(self, frame, event, arg):
        return self.traceTable.get(event, self._fallback)(frame, event, arg)

    def handleCall(self, frame, event, arg):
        lineTrace = None
        if self.oldTrace:
            lineTrace = self.oldTrace(frame, event, arg)
        func = self._callMap.get(frame.f_code, None)
        if func is not None:
            code = frame.f_code
            self.stack.append((self.code, self.func, list(self.n),
                               self.lineTrace))
            self.lineTrace = lineTrace
            self.code, self.func = code, self._callMap[code]
            self.n.append(0)
            return self.trace
        return lineTrace

    def handleLine(self, frame, event, arg):
        if self.lineTrace:
            ret = self.lineTrace(frame, event, arg)
        stepKey = self.code, frame.f_lineno
        step = self._stepMap.get(stepKey, None)
        if step is not None:
            if stepKey == self._prevKey:
                return
            self._prevKey = stepKey
            self.n[-1] += 1
            ind = "  " * (len(self.stack) - 1)
            nStr = ".".join(str(v) for v in self.n) + "."
            self.update_commentary([nStr] + step)
            return self.trace
            for i, line in enumerate(step):
                if i == 0:
                    print()
                print("%s%s %s" % (ind, nStr, line))
                if i == 0:
                    nStr = " " * len(nStr)

    def handleReturn(self, frame, event, arg):
        if self.lineTrace:
            self.lineTrace(frame, event, arg)
        self.code, self.func, self.n, self.lineTrace = self.stack.pop()
        return self.trace

    def update_commentary(self, lines):
        descr = " ".join(lines)
        status = Coordinator.getServiceProvider("status")
        status.setField("commentary", descr)
        log.info("#> %s", descr)
#}
