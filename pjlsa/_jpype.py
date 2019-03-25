import cmmnbuild_dep_manager
import re
from datetime import datetime
from enum import Enum
import numpy as np
from typing import Set, List, Tuple, Mapping, Type, TypeVar

# ------ JPype SETUP ------
mgr = cmmnbuild_dep_manager.Manager('pjlsa')
jpype = mgr.start_jpype_jvm()


# Monkey-Patcher for LSA Java Domain Objects
class LsaCustomizer(jpype._jclass.JClassCustomizer):
    _PATCHES = {
        '__repr__': lambda self: '<' + self.__str__() + '>'
    }

    def canCustomize(self, name, jc):
        return name.startswith('cern.lsa.domain.') or name.startswith('cern.accsoft.commons.domain.')

    def customize(self, name, jc, bases, members, fields):
        members.update(LsaCustomizer._PATCHES)
        # delete accessors to fields
        for k in [k for k in members.keys() if type(members[k]) is property]:
            del members[k]
        # expose getters and setters in a more pythonic way
        getters = {re.sub('^(get|is)(.)(.*)', lambda g: g.group(2).lower() + g.group(3), k): k
                   for k in members.keys() if k.startswith('get') or k.startswith('is')}
        setters = {re.sub('^(set)(.)(.*)', lambda g: g.group(2).lower() + g.group(3), k): k
                   for k in members.keys() if k.startswith('set')}
        for m, getter in getters.items():
            if '=> EXACT' not in members[getter].matchReport(jc):
                continue
            setter = setters[m] if m in setters else None
            wrapped_getter = LsaCustomizer._from_java(members[getter])
            wrapped_setter = LsaCustomizer._to_java(members[setter]) if setter is not None else None
            members[m] = property(wrapped_getter, wrapped_setter)
            del members[getter]
            if setter is not None:
                del members[setter]
        for methodName in members.keys():
            if isinstance(members[methodName], jpype._jclass._jpype._JavaMethod):
                members[methodName] = LsaCustomizer._from_to_java(members[methodName])

    @classmethod
    def _from_to_java(cls, accessor):
        return lambda *args: javaToPython(accessor(*[pythonToJava(a) for a in args]))

    @classmethod
    def _from_java(cls, accessor):
        return lambda *args: javaToPython(accessor(*args))

    @classmethod
    def _to_java(cls, accessor):
        return lambda *args: accessor(*[pythonToJava(a) for a in args])


def javaToPython(value):
    if isinstance(value, java.util.Set):
        return set([javaToPython(v) for v in value])
    if isinstance(value, java.util.List):
        return list([javaToPython(v) for v in value])
    if isinstance(value, java.util.Map):
        return {javaToPython(i.getKey()): javaToPython(i.getValue()) for i in value.entrySet()}
    if isinstance(value, java.util.Optional):
        return javaToPython(value.orElse(None))
    if isinstance(value, java.sql.Timestamp):
        return datetime.fromtimestamp(value.getTime() / 1000)
    if isinstance(value, java.lang.Boolean):
        return value.booleanValue()
    if isinstance(type(value), jpype._jarray._JavaArray):
        return np.array(value[:])
    if type(value) in _pyEnumMapping:
        return _pyEnumMapping[type(value)]._from_java(value)
    return value


def pythonToJava(value):
    if isinstance(value, Set):
        hs = java.util.HashSet()
        for v in value:
            hs.add(pythonToJava(v))
        return hs
    if isinstance(value, List) or isinstance(value, Tuple):
        hs = java.util.ArrayList()
        for v in value:
            hs.add(pythonToJava(v))
        return hs
    if isinstance(value, Mapping):
        hs = java.util.HashMap()
        for k, v in value.items():
            hs.put(pythonToJava(k), pythonToJava(v))
        return hs
    if isinstance(value, datetime):
        return java.sql.Timestamp(int(value.timestamp() * 1000))
    if isinstance(value, Enum):
        return value.__javavalue__
    return value


# possible future - even more opportunistic - conversion
# overloads = [m for m in jpype.java.lang.Class.forName(jc.getName()).getMethods() if m.getName()==accessor.getName()]
# params = overloads[0].getParameterTypes()
# params[0].isAssignableFrom(java.lang.String)

jpype._jclass.registerClassCustomizer(LsaCustomizer())

_pyEnumMapping = {}

T = TypeVar('T')


def pyEnum(jc, base: Type[T] = None) -> T:
    if isinstance(jc, str):
        jc = jpype.JClass(jc)
    global _pyEnumMapping
    if jc in _pyEnumMapping:
        return _pyEnumMapping[jc]
    name = jc.__javaclass__.getName().split('.')[-1].split('$')[0]
    java_values = {str(e): e for e in jc.values()}
    enum = Enum(name, {v: v for v in java_values.keys()}, type=base)
    enum.__javaclass__ = jc
    enum.__repr__ = enum.__str__
    enum._from_java = lambda v: [e for e in enum if e.__javavalue__ == v][0]
    for e in enum:
        e.__javavalue__ = java_values[e.name]
    _pyEnumMapping[jc] = enum
    return enum


def toJavaDate(value):
    Date = java.util.Date
    if isinstance(value, str):
        return java.sql.Timestamp.valueOf(value)
    elif isinstance(value, datetime):
        return java.sql.Timestamp.valueOf(value.strftime('%Y-%m-%d %H:%M:%S.%f'))
    elif value is None:
        return None
    elif isinstance(value, Date):
        return value
    else:
        return Date(int(value * 1000))


def toJavaList(value, converter=lambda x: x):
    res = java.util.ArrayList()
    if isinstance(value, List) or isinstance(value, Set) or isinstance(value, Tuple):
        for item in value:
            res.add(pythonToJava(converter(item)))
    elif isinstance(value, java.util.Collection):
        res.addAll(value)
    else:
        res.add(pythonToJava(converter(value)))
    return res


def toAccelerator(value):
    from .domain import CernAccelerator
    return toJavaEnum(CernAccelerator(value))


def toJavaEnum(value):
    if isinstance(value, Enum) and hasattr(value, '__javavalue__'):
        return value.__javavalue__
    else:
        raise ValueError('"{}" is not a (java) compatible enum - missing __javavalue__')


def setupLog4j(logLevel):
    log4j = org.apache.log4j
    if log4j.BasicConfigurator is not None and callable(log4j.BasicConfigurator.configure):
        log4j.BasicConfigurator.configure()
    if logLevel is not None:
        log4j.Logger.getRootLogger().setLevel(log4j.Level.toLevel(logLevel))
    else:
        log4j.Logger.getRootLogger().setLevel(log4j.Level.WARN)


# ------ IMPORTS ------
cern = jpype.JPackage('cern')
org = jpype.JPackage('org')
java = jpype.JPackage('java')

# General Java
System = java.lang.System

# LSA Services
ServiceLocator = cern.lsa.client.ServiceLocator

AcceleratorService = cern.lsa.client.AcceleratorService
AdService = cern.lsa.client.AdService
ArchiveReferenceService = cern.lsa.client.ArchiveReferenceService
CacheService = cern.lsa.client.CacheService
ContextService = cern.lsa.client.ContextService
DeviceService = cern.lsa.client.DeviceService
ElenaService = cern.lsa.client.ElenaService
ExploitationService = cern.lsa.client.ExploitationService
FidelService = cern.lsa.client.FidelService
GenerationService = cern.lsa.client.GenerationService
HyperCycleService = cern.lsa.client.HyperCycleService
JapcService = cern.lsa.client.JapcService
KnobService = cern.lsa.client.KnobService
LhcService = cern.lsa.client.LhcService
LktimService = cern.lsa.client.LktimService
OpticService = cern.lsa.client.OpticService
ParameterService = cern.lsa.client.ParameterService
SettingService = cern.lsa.client.SettingService
SpsService = cern.lsa.client.SpsService
TestService = cern.lsa.client.TestService
TimingService = cern.lsa.client.TimingService
TransactionService = cern.lsa.client.TransactionService
TrimService = cern.lsa.client.TrimService
WorkingSetService = cern.lsa.client.WorkingSetService
