# -*- coding: utf-8 -*-
import os, re
from collections import namedtuple
import datetime
import urllib

import numpy as np
import six

import cmmnbuild_dep_manager


def ver2num(ver):
    out=0
    for ii,vv in enumerate(map(int,reversed(ver.split('.')))):
        out+=vv*1000**ii
    return out

def older_jar_than_pro(jars,package):
    regname=re.compile(r'([a-z\-]+)-([0-9.]+)\.jar')
    regxml=re.compile(r'name="([a-z\-]+)" version="([0-9.]+)"')
    url='http://bewww.cern.ch/ap/dist/%s/%s/PRO/product.xml'
    for jar in jars:
        #print(jar)
        name,version=regname.search(jar).groups()
        #print(name,version)
        xml=urllib.urlopen(url%(package,name)).read()
        name2,version2=regxml.search(xml).groups()
        #print(name2,version2)
        v1=ver2num(version)
        v2=ver2num(version2)
        print("Checking version %s vs PRO=%s"%(os.path.basename(jar),version2))
        #print(v1,v2)
        if v1<v2:
            return True
    return False

def check_lsa_version():
    mgr = cmmnbuild_dep_manager.Manager()
    lsajars=[j for j in mgr.jars() if 'lsa' in j ]
    if len(lsajars)==0:
         raise ImportError("LSA jars not (yet) installed")
    elif older_jar_than_pro(lsajars,'lsa'):
           raise ImportError("LSA jar: %s older than PRO version %s. Please update"%(jar,version2))

check_lsa_version()

mgr = cmmnbuild_dep_manager.Manager('pylsa')
jpype=mgr.start_jpype_jvm()


cern=jpype.JPackage('cern')
org=jpype.JPackage('org')
java=jpype.JPackage('java')
System=java.lang.System

null=org.apache.log4j.varia.NullAppender()
org.apache.log4j.BasicConfigurator.configure(null)

# Java classes
ContextService   =cern.lsa.client.ContextService
HyperCycleService=cern.lsa.client.HyperCycleService
ParameterService =cern.lsa.client.ParameterService
ServiceLocator   =cern.lsa.client.ServiceLocator
SettingService   =cern.lsa.client.SettingService
TrimService      =cern.lsa.client.TrimService
LhcService       =cern.lsa.client.LhcService
FidelService     =cern.lsa.client.FidelService
KnobService      =cern.lsa.client.KnobService
OpticService     =cern.lsa.client.OpticService
DeviceService    =cern.lsa.client.DeviceService

BeamProcess          =cern.lsa.domain.settings.BeamProcess
ContextSettings      =cern.lsa.domain.settings.ContextSettings
HyperCycle           =cern.lsa.domain.settings.HyperCycle
Parameter            =cern.lsa.domain.settings.Parameter
ParameterSettings    =cern.lsa.domain.settings.ParameterSettings
Setting              =cern.lsa.domain.settings.Setting
StandAloneBeamProcess=cern.lsa.domain.settings.StandAloneBeamProcess
Knob                 =cern.lsa.domain.settings.Knob
FunctionSetting      =cern.lsa.domain.settings.spi.FunctionSetting
ScalarSetting        =cern.lsa.domain.settings.spi.ScalarSetting

ParametersRequestBuilder = cern.lsa.domain.settings.factory.ParametersRequestBuilder
Device                   = cern.lsa.domain.devices.Device

ParameterTreesRequestBuilder       = cern.lsa.domain.settings.factory.ParameterTreesRequestBuilder
ParameterTreesRequest              = cern.lsa.domain.settings.ParameterTreesRequest
ParameterTreesRequestTreeDirection = jpype.JClass('cern.lsa.domain.settings.ParameterTreesRequest$TreeDirection')

CalibrationFunctionTypes=cern.lsa.domain.optics.CalibrationFunctionTypes

LHC =cern.accsoft.commons.domain.CernAccelerator.LHC
PS  =cern.accsoft.commons.domain.CernAccelerator.PS
SPS =cern.accsoft.commons.domain.CernAccelerator.SPS
LEIR=cern.accsoft.commons.domain.CernAccelerator.LEIR
PSB =cern.accsoft.commons.domain.CernAccelerator.PSB


# Python data descriptors
TrimHeader = namedtuple('TrimHeader',
           ['id','beamProcesses','createdDate','description','clientInfo'])
OpticTableItem = namedtuple('OpticTableItem', ['time', 'id', 'name'])
TrimTuple = namedtuple('TrimTuple', ['time', 'data'])


#
Accelerators={
        'lhc':  LHC, 'ps':   PS, 'sps':  SPS,
        'lear': LEIR, 'psb':  PSB, }


def _build_TrimHeader(th):
    return TrimHeader(
            id = th.id,
            beamProcesses = [str(bp) for bp in th.beamProcesses],
            createdDate = datetime.datetime.fromtimestamp(
                              th.createdDate.getTime()/1000),
            description = th.description,
            clientInfo = th.clientInfo )

def _toJavaDate(t):
    """Date from string, datetime, unixtimestamp to java date
    """
    Date = java.util.Date
    if isinstance(t, six.string_types):
        return java.sql.Timestamp.valueOf(t)
    elif isinstance(t, datetime.datetime):
        return java.sql.Timestamp.valueOf(t.strftime('%Y-%m-%d %H:%M:%S.%f'))
    elif t is None:
        return None
    elif isinstance(t,Date):
        return t
    else:
        return Date(int(t*1000))


def _toJavaList(lst):
    res=java.util.LinkedList()
    for ii in lst:
        res.add(ii)
    return res

class LSAClient(object):
    def __init__(self,server='gpn'):
        System.setProperty("lsa.server", server)
        #System.setProperty("lsa.mode", "3")
        self._contextService = ServiceLocator.getService(ContextService)
        self._trimService = ServiceLocator.getService(TrimService)
        self._settingService = ServiceLocator.getService(SettingService)
        self._parameterService = ServiceLocator.getService(ParameterService)
        self._contextService = ServiceLocator.getService(ContextService)
        self._lhcService = ServiceLocator.getService(LhcService)
        self._hyperCycleService = ServiceLocator.getService(HyperCycleService)
        self._knobService = ServiceLocator.getService(KnobService)
        self._opticService = ServiceLocator.getService(OpticService)
        self._deviceService = ServiceLocator.getService(DeviceService)
        self._fidelService = ServiceLocator.getService(FidelService)

    def _findHyperCycles(self):
        return list(self._hyperCycleService.findHyperCycles())

    def findHyperCycles(self):
        return map(str,self._findHyperCycles())

    def _getHyperCycle(self,hypercycle=None):
        if hypercycle is None:
            return self._hyperCycleService.findActiveHyperCycle()
        else:
            return self._hyperCycleService.findHyperCycle(hypercycle)

    def getUsers(self,hypercycle=None):
        hp=self._getHyperCycle(hypercycle=hypercycle)
        return sorted([str(u) for u in hp.getUsers()])

    def findBeamProcesses(self,regexp='',accelerator='lhc'):
        acc=Accelerators.get(accelerator,accelerator)
        bps=self._contextService.findStandAloneBeamProcesses(acc)
        reg=re.compile(regexp,re.IGNORECASE)
        return sorted(filter(reg.search,[str(bp) for bp in bps]))

    def _getBeamProcess(self, bp):
        if isinstance(bp, BeamProcess):
            return bp
        else:
            return self._contextService.findStandAloneBeamProcess(bp)

    def _getBeamProcessByUser(self,user, hypercycle=None):
        hp=self._getHyperCycle(hypercycle=hypercycle)
        return hp.getBeamProcessByUser(user)

    def getResidentBeamProcess(self, category):
        return str(self._getHyperCycle().getResidentBeamProcess(category))

    def getResidentBeamProcesses(self):
        return [str(p) for p in list(self._getHyperCycle().getResidentBeamProcesses())]

    def findParameterNames(self,deviceName,regexp=''):
        req=ParametersRequestBuilder().setDeviceName(deviceName)
        lst=self._parameterService.findParameters(req.build())
        reg=re.compile(regexp,re.IGNORECASE)
        return sorted(filter(reg.search,[pp.getName() for pp in lst ]))

    def _getParameter(self, param):
        if isinstance(param, Parameter):
            return param
        else:
            return self._parameterService.findParameterByName(param)

    def _getParameterList(self,deviceName):
        req=ParametersRequestBuilder().setDeviceName(deviceName)
        lst=self._parameterService.findParameters(req.build())
        return lst

    def _getRawTrimHeaders(self, beamprocess, param, start=None, end=None):
        bp = self._getBeamProcess(beamprocess)
        thrb = cern.lsa.domain.settings.TrimHeadersRequestBuilder()
        thrb.beamProcesses(java.util.Collections.singleton(bp))
        thrb.parameters(param)
        if start is not None:
           thrb.startingFrom(_toJavaDate(start).toInstant())
        trimHeadersRequest = thrb.build()
        raw_headers = self._trimService.findTrimHeaders(trimHeadersRequest)
        raw_headers = list(raw_headers)
        if start is not None:
            raw_headers = [th for th in raw_headers if not th.createdDate.before(_toJavaDate(start))]
        if end is not None:
            raw_headers = [th for th in raw_headers if not th.createdDate.after(_toJavaDate(end))]
        return raw_headers

    def _buildParameterList(self, parameter):
        if type(parameter) in [str,BeamProcess]:
            param = self._getParameter(parameter)
            param = java.util.Collections.singleton(param)
        else:
            param = java.util.LinkedList()
            for pp in parameter:
                param.add(self._getParameter(pp))
        return param

    def getTrimHeaders(self, beamprocess, parameter, start=None, end=None):
        return [_build_TrimHeader(th) for th in
                   self._getRawTrimHeaders(
                            beamprocess,
                            self._buildParameterList(parameter), start, end)]

    def getTrims(self, beamprocess, parameter, start=None, end=None, part='value'):
        parameterList = self._buildParameterList(parameter)
        bp = self._getBeamProcess(beamprocess)

        timestamps = {}
        values = {}
        for th in self._getRawTrimHeaders(bp, parameterList, start, end):
            csrb = cern.lsa.domain.settings.ContextSettingsRequestBuilder()
            csrb.standAloneContext(bp)
            csrb.parameters(parameterList)
            csrb.at(th.createdDate.toInstant())
            contextSettings =  self._settingService.findContextSettings(csrb.build())
            for pp in parameterList:
              parameterSetting = contextSettings.getParameterSettings(pp)
              if parameterSetting is None:
                continue

              setting = parameterSetting.getSetting(bp)
              value = setting
              if part is not None:
                if type(setting) is ScalarSetting:
                  if part == 'value':
                    value = setting.getScalarValue().getDouble()
                  elif part == 'target':
                    value = setting.getTargetScalarValue().getDouble()
                  elif part == 'correction':
                    value = setting.getCorrectionScalarValue().getDouble()
                  else:
                    raise ValueError('Invalid Setting Part: ' + part)
                elif type(setting) is FunctionSetting:
                  if part == 'value':
                    df = setting.getFunctionValue()
                  elif part == 'target':
                    df = setting.getTargetFunctionValue()
                  elif part == 'correction':
                    df = setting.getCorrectionFunctionValue()
                  else:
                    raise ValueError('Invalid Setting Part: ' + part)
                  value = np.array([df.toXArray()[:], df.toYArray()[:]])
                else:
                  # for now, return the java type (to be extended)
                  value = setting

              timestamps.setdefault(pp.getName(),[]).append(
                                          th.createdDate.getTime()/1000)
              values.setdefault(pp.getName(),[]).append(value)
        out={ }
        for name in values:
            out[name]=TrimTuple(time=timestamps[name], data=values[name])
        return out

    def getLastTrim(self,beamprocess, parameter, part='value'):
        th = self.getTrimHeaders(beamprocess,parameter)[-1]
        res = self.getTrims(beamprocess, parameter, part=part, start=th.createdDate)[parameter]
        return TrimTuple(res.time[-1],res.data[-1])

    def getOpticTable(self, beamprocess):
        bp = self._getBeamProcess(beamprocess)
        opticTable = list(self._opticService.findContextOpticsTables(bp))[0].getOpticsTableItems()
        return [ OpticTableItem(time=o.getTime(),
                 id=o.getOpticId(),
                 name=o.getOpticName() ) for o in opticTable ]

    def getKnobFactors(self, knob, optic):
        if isinstance(optic, OpticTableItem):
            optic = optic.name
        k = self._knobService.findKnob(knob)
        factors = list(k.getKnobFactors().getFactorsForOptic(optic))
        return { f.getComponentName(): f.getFactor() for f in factors }

    def getParameterHierarchy(self, parameter, direction='dependent'):
        req = ParameterTreesRequestBuilder()
        if direction=='dependent':
            req.setTreeDirection(ParameterTreesRequestTreeDirection.DEPENDENT_TREE)
        elif direction=='source':
            req.setTreeDirection(ParameterTreesRequestTreeDirection.SOURCE_TREE)
        else:
            raise ValueError('invalid direction, expecting "dependent" or "source"')
        req.setParameter(self._getParameter(parameter))
        tree = self._parameterService.findParameterTrees(req.build())
        params = {}
        for t in tree:
            for p in t.getParameters():
                params.setdefault(str(p.getParameterType()),[]).append(str(p))
        return params

    def getOpticStrength(self,optic):
        if not hasattr(optic,'name'):
           optic=self._opticService.findOpticByName(optic)
        out=  [ (st.logicalHWName,st.strength)
                for st in optic.getOpticStrengths() ]
        return dict(out)

    def getOptics(self,name):
        return self._opticService.findOpticByName(name)


    def dump_calibrations(self, outdir='calib'):
        """ Dump all calibration in directory <outdir>
        """
        os.mkdir(outdir)
        cals=self._fidelService.findAllCalibrations();
        for cc in cals:
          name=cc.getName()
          ff=cc.getCalibrationFunctionByType(CalibrationFunctionTypes.B_FIELD)
          if ff is not None:
             field=ff.toXArray()
             current=ff.toYArray()
             fn=os.path.join(outdir,'%s.txt'%name)
             print(fn)
             fh=open(fn,'w')
             fh.write('\n'.join(["%s %s"%(i,f) for i,f in zip(current,field)]))
             fh.close()

