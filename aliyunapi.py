#!/usr/bin/python
# -*- coding:utf-8 -*-
import hmac
import time
import uuid
import json
import base64
import os
import sys
import hashlib
import threading
import urllib, urllib2
from hashlib     import sha1
from optparse    import OptionParser
from prettytable import PrettyTable
import ConfigParser

db_type = (('rds.mys2.small'    , '240RAM    60CONN    150IOPS'),
           ('rds.mys2.mid'      , '600RAM    150CONN   300IOPS'),
           ('rds.mys2.standard' , '1200RAM   300CONN   600IOPS'),
           ('rds.mys2.large'    , '2400RAM   600CONN   1200IOPS'),
           ('rds.mys2.xlarge'   , '6000RAM   1500CONN  3000IOPS'),
           ('rds.mys2.2xlarge'  , '12000RAM  2000CONN  6000IOPS'),
           ('rds.mys2.4xlarge'  , '24000RAM  2000CONN  12000IOPS'),
           ('rds.mys2.8xlarge'  , '48000RAM  2000CONN  14000IOPS'),
           ('rds.mysql.st.d13'  , '225280RAM 10000CONN 20000IOPS'))

db_engine = (('Engine'            , 'MySQL           SQLServer          PostgreSQL       PPAS'),
             ('EngineVersion'     , 'MySQL：5.5/5.6; SQLServer：2008r2; PostgreSQL：9.4; PPAS：9.3'))

rds_action = ['CreateDBInstance', 
              'DeleteDBInstance', 
              'RestartDBInstance', 
              'DescribeDBInstanceAttribute', 
              'DescribeDBInstances', 
              'ModifyDBInstanceSpec', 
              'AllocateInstancePublicConnection', 
              'ReleaseInstancePublicConnection', 
              'SwitchDBInstanceNetType', 
              'DescribeDBInstanceNetInfo', 
              'ModifyDBInstanceConnectionString', 
              'ModifyDBInstanceConnectionMode', 
              'ModifyDBInstanceNetworkType', 
              'DescribeDBInstanceIPArrayList', 
              'ModifySecurityIps', 
              'DescribeDBInstanceHAConfig', 
              'MigrateToOtherZone', 
              'PurgeDBInstanceLog', 
              'UpgradeDBInstanceEngineVersion', 
              'ModifyDBInstanceDescription', 
              'ModifyDBInstanceMaintainTime', 
              'ModifyDBInstanceHAConfig', 
              'SwitchDBInstanceHA', 
              'CreateReadonlyDBInstance', 
              'CreateDatabase', 
              'DeleteDatabase', 
              'DescribeDatabases', 
              'ModifyDBDescription', 
              'CreateAccount', 
              'DeleteAccount', 
              'DescribeAccounts', 
              'GrantAccountPrivilege', 
              'RevokeAccountPrivilege', 
              'ModifyAccountDescription', 
              'ResetAccountPassword', 
              'ResetAccount', 
              'CreateBackup', 
              'DescribeBackups', 
              'CreateTempDBInstance', 
              'DescribeBackupPolicy', 
              'ModifyBackupPolicy', 
              'RestoreDBInstance', 
              'DescribeResourceUsage', 
              'DescribeDBInstancePerformance', 
              'DescribeDBInstanceMonitor', 
              'ModifyDBInstanceMonitor', 
              'DescribeParameterTemplates', 
              'DescribeParameters', 
              'ModifyParameter', 
              'DescribeSlowLogs', 
              'DescribeSlowLogRecords', 
              'DescribeErrorLogs', 
              'DescribeBinlogFiles', 
              'DescribeSQLCollectorPolicy', 
              'ModifySQLCollectorPolicy', 
              'DescribeSQLLogRecords', 
              'CreateUploadPathForSQLServer', 
              'DescribeFilesForSQLServer', 
              'ImportDataForSQLServer', 
              'DescribeImportsForSQLServer', 
              'ImportDatabaseBetweenInstances', 
              'CancelImport', 
              'DescribeSQLLogReports', 
              'DescribeSQLLogRecords', 
              'DescribeOptimizeAdviceOnMissIndex']

access_key_id       = '';
access_key_secret   = '';
CONFIGFILE    = os.path.dirname(os.path.abspath(__file__)) + '/.aliyuncredentials'
CONFIGSECTION = 'Credentials'

def percent_encode(str):
    res = urllib.quote(str.decode(sys.stdin.encoding).encode('utf8'), '')
    res = res.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    return res

def compute_signature(parameters, access_key_secret):
    sortedParameters = sorted(parameters.items(), key=lambda parameters: parameters[0])

    canonicalizedQueryString = ''
    for (k,v) in sortedParameters:
        canonicalizedQueryString += '&' + percent_encode(k) + '=' + percent_encode(v)

    stringToSign = 'GET&%2F&' + percent_encode(canonicalizedQueryString[1:])

    h = hmac.new(access_key_secret + '&', stringToSign, sha1)
    signature = base64.encodestring(h.digest()).strip()
    return signature

def compose_url(user_params):
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if user_params['Action'] in rds_action: tmp = '2014-08-15'
    else: tmp = '2014-05-26'
    parameters = { \
            'Format'        : 'JSON', \
            'Version'       : tmp, \
            'AccessKeyId'   : access_key_id, \
            'SignatureVersion'  : '1.0', \
            'SignatureMethod'   : 'HMAC-SHA1', \
            'SignatureNonce'    : str(uuid.uuid1()), \
            'TimeStamp'         : timestamp, \
    }

    if user_params['Action'] in ['CreateDBInstance', 'CreateReadonlyDBInstance']:
        user_params['ClientToken'] = str(uuid.uuid1())
    for key in user_params.keys():
        parameters[key] = user_params[key]

    signature = compute_signature(parameters, access_key_secret)
    parameters['Signature'] = signature
    if user_params['Action'] in rds_action: server_address = 'https://rds.aliyuncs.com'
    else: server_address  = 'https://ecs.aliyuncs.com'
    url = server_address + '/?' + urllib.urlencode(parameters)
    print(url)
    return url

def make_request(user_params, quiet=False):
    url = compose_url(user_params)
    request = urllib2.Request(url)

    try:
        conn = urllib2.urlopen(request)
        response = conn.read()
    except urllib2.HTTPError, e:
        print(e.read().strip())
        raise SystemExit(e)

    try:
        obj = json.loads(response)
        if quiet:
            return obj
    except ValueError, e:
        raise SystemExit(e)
    json.dump(obj, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write('\n')

def make_request_thread(queue1, queue2):
    while 1:
        try:
            user_params = queue1.pop()
            queue2.append(make_request(user_params, 1))
        except IndexError:
            break

def configure_accesskeypair(accesskeyid,  accesskeysecret):
    config = ConfigParser.RawConfigParser()
    config.add_section(CONFIGSECTION)
    config.set(CONFIGSECTION, 'accesskeyid',     accesskeyid)
    config.set(CONFIGSECTION, 'accesskeysecret', accesskeysecret)
    cfgfile = open(CONFIGFILE, 'w+')
    config.write(cfgfile)
    cfgfile.close()

def setup_credentials():
    config = ConfigParser.ConfigParser()
    try:
        config.read(CONFIGFILE)
        global access_key_id
        global access_key_secret
        access_key_id     = config.get(CONFIGSECTION, 'accesskeyid')
        access_key_secret = config.get(CONFIGSECTION, 'accesskeysecret')
    except Exception, e:
        print('can not get access key pair, use --config --id=[accesskeyid] --secret=[accesskeysecret] to setup')
        sys.exit(1)

def describe_instances(regionid, quiet=True):
    queue1, queue2, thread_list = [], [], []
    user_params = {}
    user_params['Action']   = 'DescribeZones'
    user_params['PageSize'] = '100'
    user_params['RegionId'] = regionid
    obj = make_request(user_params, quiet=True)

    table = PrettyTable(['InstanceId', 'ZoneId', 'InstanceName', 'Status', 'InstanceType', 'CreationTime', 'ExpiredTime', 'InstanceChargeType', 'InnerIpAddress', 'PublicIpAddresses', 'NetworkIn', 'NetworkOut', 'Cpu', 'Memory'])
    table.align['InnerIpAddress'] = "l"
    table.align['PublicIpAddresses'] = "l"
    for zone in obj['Zones']['Zone']:
        pagenum = 1
        while 1:
            user_params = {}
            user_params['ZoneId']     = zone['ZoneId']
            user_params['Action']     = 'DescribeInstances'
            user_params['RegionId']   = regionid
            user_params['PageSize']   = '100'
            user_params['PageNumber'] = str(pagenum)
            instances = make_request(user_params, quiet=True)
            if len(instances) > 0:
                for i in instances['Instances']['Instance']:
                    params = {}
                    params['Action'] = 'DescribeInstanceAttribute' 
                    params['InstanceId'] = i['InstanceId']
                    queue1.append(params)
            if pagenum <= (instances['TotalCount']/instances['PageSize']): pagenum += 1
            else: break
    for _ in xrange(50): thread_list.append(threading.Thread(target=make_request_thread, args=(queue1, queue2,)))
    for tmp in thread_list: tmp.start()
    for tmp in thread_list: tmp.join()
    for res in queue2:
        table.add_row([res['InstanceId'], res['ZoneId'], res['InstanceName'], res['Status'], res['InstanceType'], 
                       res['CreationTime'], res['ExpiredTime'], res['InstanceChargeType'], ';'.join(res['InnerIpAddress']['IpAddress']),
                       ';'.join(res['PublicIpAddress']['IpAddress']), res['InternetMaxBandwidthIn'], res['InternetMaxBandwidthOut'], res['Cpu'], res['Memory']])
    print(table)

def describe_zones(regionid, quiet=True):
    user_params = {}
    user_params['Action'] = 'DescribeZones'
    user_params['RegionId'] = regionid
    obj = make_request(user_params, quiet=True)
    if quiet:
        return obj
    else:
        table = PrettyTable(['ZoneId'])  
        table.align['ZoneId'] = "l"
        for tmp in obj['Zones']['Zone']: table.add_row([tmp['ZoneId']])
        print(table)

def change_network(instanceid = [], out = 0, quiet = True):
    for tmp in instanceid:
        user_params = {}
        user_params['Action'] = 'ModifyInstanceNetworkSpec'
        user_params['InstanceId'] = tmp
        user_params['InternetMaxBandwidthOut'] = out
        make_request(user_params, quiet=True)

def describe_types(regionid, quiet=True):
    user_params = {}
    user_params['Action'] = 'DescribeInstanceTypes'
    user_params['RegionId'] = regionid
    obj = make_request(user_params, quiet=True)
    if quiet:
        return obj
    else:
        table = PrettyTable(['InstanceTypeId', 'CpuCoreCount', 'MemorySize'])  
        table.align['InstanceTypeId'] = "l"
        for tmp in obj['InstanceTypes']['InstanceType']: table.add_row([tmp['InstanceTypeId'], tmp['CpuCoreCount'], tmp['MemorySize']])
        print(table)

def describe_create(regionid = None, zoneid = None, instancename = None, description = None, hostname = None,
                    password = None, securitygroupid = None, instancetype = None, imageid = None, instancechargetype = None,
                    period = None, iooptimized = None, AllocatePublicIpAddress = None, InternetMaxBandwidthOut = None, 
                    InternetChargeType = None, systemdiskcategory = None, DataDiskSize = None, DataDiskCategory = None, quiet=True):
    user_params = {}
    user_params['Action'] = 'CreateInstance'
    user_params['RegionId'] = regionid
    if zoneid:        user_params['ZoneId']       = zoneid
    if instancename : user_params['InstanceName'] = instancename
    if description  : user_params['Description']  = description
    if hostname     : user_params['HostName']     = hostname
    if password     : user_params['Password']     = password
    user_params['ImageId']            = imageid
    if instancetype: user_params['InstanceType']       = instancetype
    user_params['SecurityGroupId']    = securitygroupid
    if instancechargetype == 'PostPaid':
        user_params['InstanceChargeType'] = instancechargetype
    elif instancechargetype == 'PrePaid':
        user_params['InstanceChargeType'] = 'PrePaid'
        if not period or int(period) not in [1,2,3,4,5,6,7,8,9,12,24,36]:
            exit("ERROR: PrePaid instances Must have a predefined period, in month [ 1-9, 12, 24, 36 ]")
        else: 
            user_params['Period'] = period
    else:
        exit("InstanceChargeType is null. It is either PrePaid, or PostPaid")
    if iooptimized == 'none' : pass
    else: user_params['IoOptimized'] = iooptimized
    user_params['SystemDisk.Category'] = systemdiskcategory
    if InternetMaxBandwidthOut: user_params['InternetMaxBandwidthOut'] = InternetMaxBandwidthOut
    if DataDiskSize: user_params['DataDisk.1.Size'] = DataDiskSize 
    if DataDiskCategory: user_params['DataDisk.1.Category'] = DataDiskCategory 
    obj = make_request(user_params, quiet=True)
    print(obj)
    if AllocatePublicIpAddress:
        user_params = {}
        user_params['Action'] = 'AllocatePublicIpAddress'
        user_params['InstanceId'] = obj['InstanceId']
        make_request(user_params, quiet=True)

def describe_allocatepublicipaddress(instanceid = [], quiet=True):
    for tmp in instanceid:
        user_params = {}
        user_params['Action'] = 'AllocatePublicIpAddress'
        user_params['InstanceId'] = tmp
        make_request(user_params, quiet=True)
    
def describe_start(instanceid = [], quiet=True):
    for tmp in instanceid:
        user_params = {}
        user_params['Action'] = 'StartInstance'
        user_params['InstanceId'] = tmp
        make_request(user_params, quiet=True)

def describe_stop(instanceid = [], quiet=True, force='true'):
    for tmp in instanceid:
        user_params = {}
        user_params['Action']     = 'StopInstance'
        user_params['ForceStop']  = force
        user_params['InstanceId'] = tmp
        make_request(user_params, quiet=True)

def describe_reboot(instanceid = [], quiet=True, force='true'):
    for tmp in instanceid:
        user_params = {}
        user_params['Action']     = 'RebootInstance'
        user_params['ForceStop']  = force
        user_params['InstanceId'] = tmp
        make_request(user_params, quiet=True)

def describe_delete(instanceid = [], quiet=True):
    for tmp in instanceid:
        user_params = {}
        user_params['Action']     = 'DeleteInstance'
        user_params['InstanceId'] = tmp
        make_request(user_params, quiet=True)

def describe_regions(quiet=True):
    user_params = {}
    user_params['Action'] = 'DescribeRegions'
    obj = make_request(user_params, quiet=True)
    print(obj)
    if quiet:
        return obj
    else:
        table = PrettyTable(['RegionId', 'LocalName'])  
        table.align['RegionId']  = "l"
        table.align['LocalName'] = "l"
        for tmp in obj['Regions']['Region']: 
            table.add_row([tmp['RegionId'], tmp['LocalName']])
        print(table)

def describe_images(regionid, quiet=True):
    user_params = {}
    user_params['Action']   = 'DescribeImages'
    user_params['PageSize'] = '100'
    user_params['PageNumber'] = '1'
    user_params['RegionId'] = regionid
    obj = make_request(user_params, quiet=True)
    if quiet:
        return obj
    else:
        table = PrettyTable(['ImageOwnerAlias', 'CreationTime', 'ImageId', 'Description'])  
        table.align['ImageId'] = "l"
        table.align['Description'] = "l"
        table.align['ImageOwnerAlias'] = "l"
        for image in obj['Images']['Image']:
            table.add_row([image['ImageOwnerAlias'], image['CreationTime'], image['ImageId'], image['Description']])
        print(table)

def show_db(regionid, quiet=True):
    #table = PrettyTable(['RegionId', 'ZoneId', 'DBId', 'DBDescription', 'Engine', 'EngineV', 'DBType', 'DBMemory', 'DBStorage', 'DBStatus', 'MaxIOPS', 'ConnectionString', 'Port', 'MasterId', 'DBNetType', 'CreateTime', 'ExpiredTime', 'PayType'])
    table = PrettyTable(['ZoneId', 'DBInstanceId', 'DBDescription', 'EngineV', 'DBType', 'DBMemStorIOPS', 'DBStatus', 'ConnectionString', 'Port', 'MasterId', 'DBNetType', 'CreateTime', 'ExpiredTime', 'PayType'])
    table.align['DBInstanceId'] = "l"
    table.align['DBDescription'] = "l"
    table.align['ConnectionString'] = "r"
    pagenum, result_list = 1, []
    while 1:
        user_params = {}
        user_params['Action']   = 'DescribeDBInstances'
        user_params['PageSize'] = '100'
        user_params['PageNumber'] = str(pagenum)
        user_params['RegionId']   = regionid
        obj = make_request(user_params, quiet=True)
        if quiet:
            return obj
        else:
            result_list = result_list + (obj['Items']['DBInstance'])
        if pagenum <= (obj['TotalRecordCount']/int(user_params['PageSize'])): pagenum += 1
        else: break
    for tmp in result_list:
        user_params = {}
        user_params['Action']       = 'DescribeDBInstanceAttribute'
        user_params['DBInstanceId'] = tmp['DBInstanceId']
        obj = make_request(user_params, quiet=True)['Items']['DBInstanceAttribute'][0]
        table.add_row([obj['ZoneId'], tmp['DBInstanceId'], tmp.get('DBInstanceDescription', ''), '%s%s' %(tmp['Engine'], tmp['EngineVersion']), tmp['DBInstanceType'], '%s %s %s' %(obj['DBInstanceMemory'], obj['DBInstanceStorage'], obj['MaxIOPS']), 
                       tmp['DBInstanceStatus'], obj['ConnectionString'],
                       obj['Port'], tmp.get('MasterInstanceId', ''), tmp['DBInstanceNetType'], tmp['CreateTime'].replace('Z', ''), tmp.get('ExpireTime', '').replace('Z', ''), tmp.get('PayType', '')])
        #table.add_row([tmp['RegionId'], obj['ZoneId'], tmp['DBInstanceId'], tmp.get('DBInstanceDescription', ''), tmp['Engine'], tmp['EngineVersion'], tmp['DBInstanceType'], obj['DBInstanceMemory'], obj['DBInstanceStorage'], tmp['DBInstanceStatus'], 
        #               obj['MaxIOPS'], obj['ConnectionString'],
        #               obj['Port'], tmp.get('MasterInstanceId', ''), tmp['DBInstanceNetType'], tmp['CreateTime'], tmp.get('ExpireTime', ''), tmp.get('PayType', '')])
    print(table)

def show_db_type():
    for tmp in [db_type, db_engine]:
        table = PrettyTable(['Key', 'Value'])
        table.align['Key'] = "l"
        table.align['Value'] = "l"
        for k, v in tmp:
            table.add_row([k,v])
        print(table)

def create_db(RegionId = None, ZoneId = None, Engine = None, EngineVersion = None, DBInstanceClass = None, DBInstanceStorage = None, DBInstanceNetType = None, DBInstanceDescription = None,
              SecurityIPList = None, PayType = None, Period = None, UsedTime = None, quiet = True):
    user_params = {}
    user_params['Action']                 = 'CreateDBInstance'
    user_params['RegionId']               = RegionId
    if ZoneId:      user_params['ZoneId'] = ZoneId
    user_params['Engine']                 = Engine
    user_params['EngineVersion']          = EngineVersion
    user_params['DBInstanceClass']        = DBInstanceClass
    user_params['DBInstanceStorage']      = DBInstanceStorage
    user_params['DBInstanceNetType']      = DBInstanceNetType
    user_params['DBInstanceDescription']  = DBInstanceDescription
    user_params['SecurityIPList']         = SecurityIPList
    user_params['PayType']                = PayType
    if user_params['PayType'] == 'Prepaid':
        user_params['Period']                 = Period
        user_params['UsedTime']               = UsedTime
    obj = make_request(user_params, quiet=True)
    if quiet:
        return obj
    else:
        print(obj)

def delete_db(dbinstanceid = [], quiet=True):
    for tmp in dbinstanceid:
        user_params = {}
        user_params['Action']     = 'DeleteDBInstance'
        user_params['DBInstanceId'] = tmp
        make_request(user_params, quiet=True)

def slave_db(dbinstanceid = [], RegionId = None, ZoneId = None, DBInstanceClass = None, DBInstanceStorage = None, DBInstanceDescription = None, quiet=True):
    for tmp in dbinstanceid:
        user_params = {}
        user_params['Action']             = 'CreateReadonlyDBInstance'
        if ZoneId: user_params['ZoneId']  = ZoneId
        user_params['RegionId']           = RegionId
        user_params['DBInstanceId']       = tmp
        user_params['EngineVersion']      = '5.6'
        user_params['DBInstanceClass']    = DBInstanceClass
        user_params['DBInstanceStorage']  = DBInstanceStorage
        user_params['PayType']            = 'Postpaid'
        if DBInstanceDescription: user_params['DBInstanceDescription'] = DBInstanceDescription
        print make_request(user_params, quiet=True)

    
if __name__ == '__main__':
    parser = OptionParser()

    parser.add_option('-i', '--id',              dest='accesskeyid',     help='specify access key id')
    parser.add_option('-s', '--secret',          dest='accesskeysecret', help='specify access key secret')
    parser.add_option('-c', '--config',          dest='config',          help='specify when creating an instance',  action='store_true')

    parser.add_option('-R', '--RegionId',        dest='regionid',        help='regionid str')
    parser.add_option('-N', '--InstanceId',      dest='instanceid',      help='instanceid str,str,str')

    parser.add_option('-Z', '--ShowZones',       dest='showzones',       help='show zones list',    action='store_true')
    parser.add_option('-T', '--ShowTypes',       dest='showtypes',       help='show types list',    action='store_true')
    parser.add_option('-I', '--ShowImages',      dest='showimages',      help='show images list',   action='store_true')
    parser.add_option('-D', '--ShowRegions',     dest='showregions',     help='show regions list',  action='store_true')
    parser.add_option('-E', '--ShowInstance',    dest='showinstance',    help='show instance list', action='store_true')

    parser.add_option('-S', '--StartInstance',    dest='startinstance',    help='start  instance',    action='store_true')
    parser.add_option('-P', '--StopInstance',     dest='stopinstance',     help='stop   instance',    action='store_true')
    parser.add_option('-B', '--RebootInstance',   dest='rebootinstance',   help='reboot instance',    action='store_true')
    parser.add_option('-L', '--DeleteInstance',   dest='deleteinstance',   help='delete instance',    action='store_true')
    parser.add_option('-A', '--OpenIpAddress',    dest='openipaddress',    help='open ip address',    action='store_true')

    parser.add_option('-O', '--ChangeNetworkOut', dest='changenetworkout', help='change network out', action='store_true')
    parser.add_option('-k', '--NetworkOutNum',    dest='networkoutnum',    help='change network out')

    parser.add_option('-C', '--CreateInstance',     dest='createinstance',      help='specify when creating an instance',  action='store_true')
    parser.add_option('-r', '--Regionid',           dest='regionid',            help='specify when creating an instance')
    parser.add_option('-z', '--Zoneid',             dest='zoneid',              help='specify when creating an instance')
    parser.add_option('-n', '--Instancename',       dest='instancename',        help='specify when creating an instance')
    parser.add_option('-d', '--Description',        dest='description',         help='specify when creating an instance')
    parser.add_option('-m', '--HostName',           dest='hostname',            help='specify when creating an instance')
    parser.add_option('-p', '--PassWord',           dest='password',            help='specify when creating an instance')
    parser.add_option('-g', '--SecurityGroupid',    dest='securitygroupid',     help='specify when creating an instance')
    parser.add_option('-t', '--InstanceType',       dest='instancetype',        help='specify when creating an instance')
    parser.add_option('-o', '--ImageId',            dest='imageid',             help='specify when creating an instance')
    parser.add_option('-X', '--DataDiskSize',    dest='datadisksize',        help='specify when creating an instance')
    parser.add_option('-Y', '--DataDiskCategory',            dest='datadiskcategory',             help='specify when creating an instance [cloud|cloud_efficiency|cloud_ssd|ephemeral_ssd] Default cloud', default = 'cloud')
    parser.add_option('-b', '--SystemDiskCategory', dest='systemdiskcategory',  help='specify when creating an instance [cloud|cloud_efficiency|cloud_ssd|ephemeral_ssd] Default cloud', default = 'cloud')
    parser.add_option('-f', '--InstanceChargeType', dest='instancechargetype', 
                                                    help='specify when creating an instance [PrePaid|PostPaid] Default PostPaid', default = 'PostPaid')
    parser.add_option('-e', '--Period',             dest='period',             help='specify when creating an instance [1,2,3,4,5,6,7,8,9,12,24,36]')
    parser.add_option('-q', '--IoOptimized',        dest='iooptimized',        
                                                    help='specify when creating an instance [none|optimized] Default none' , default = 'none')
    parser.add_option('-w', '--AllocatePublicIpAddress', dest='allocatepublicipAddress', help='specify when creating an instance', action = 'store_true')
    parser.add_option('-l', '--InternetMaxBandwidthOut', dest='internetmaxbandwidthout', help='specify when creating an instance')
    parser.add_option('-y', '--InternetChargeType',      dest='internetchargetype',      help='specify when creating an instance [PayByBandwidth|PayByTraffic] Default PayByBandwidth', default = 'PayByBandwidth')

    parser.add_option('--ShowDB',        dest='showdb',        help='show db list',      action='store_true')
    parser.add_option('--ShowDBType',    dest='showdbtype',    help='show db type list', action='store_true')

    parser.add_option('--CreateDB',               dest='createdb',               help='specify when creating a db',        action='store_true')
    parser.add_option('--CreateDBSlave',          dest='createdbslave',          help='specify when creating a slave db',  action='store_true')
    parser.add_option('--DeleteDB',               dest='deletedb',               help='delete db',                         action='store_true')

    parser.add_option('--DBInstanceId',           dest='dbinstanceid',           help='dbinstanceid str,str,str')
    parser.add_option('--DBEngine',               dest='dbengine',               help='specify when creating a db')
    parser.add_option('--DBEngineVersion',        dest='dbengineversion',        help='specify when creating a db')
    parser.add_option('--DBType',                 dest='dbinstanceclass',        help='specify when creating a db')
    parser.add_option('--DBInstanceStorage',      dest='dbinstancestorage',      help='specify when creating a db mysql[5,1000] sqlserver[10,1000] PostgreSQL and PPAS[5,2000]')
    parser.add_option('--DBInstanceNetType',      dest='dbinstancenettype',      help='specify when creating a db [Internet|Intranet] Default Intranet', default='Intranet')
    parser.add_option('--DBInstanceDescription',  dest='dbinstancedescription',  help='specify when creating a db')
    parser.add_option('--DBSecurityIPList',       dest='dbsecurityiplist',       help='specify when creating a db', default = '0.0.0.0/0')
    parser.add_option('--DBPayType',              dest='dbpaytype',              help='specify when creating a db [Postpaid|Prepaid] Default Postpaid', default = 'Postpaid')
    parser.add_option('--DBPeriod',               dest='dbperiod' ,              help='specify when creating a db [Year|Month]')
    parser.add_option('--DBUsedTime',             dest='dbusedtime',             help='specify when creating a db [Year 1,2,3 |Month 1-9]')

    (options, args) = parser.parse_args()
    if options.config and options.accesskeyid and options.accesskeysecret: 
        configure_accesskeypair(options.accesskeyid, options.accesskeysecret); sys.exit(0)
    else: setup_credentials()
    if options.showregions:
        describe_regions(quiet=0)
    if options.showzones and options.regionid:
        describe_zones(options.regionid, quiet=0)
    if options.showtypes and options.regionid:
        describe_types(options.regionid, quiet=0)
    if options.showimages and options.regionid:
        describe_images(options.regionid, quiet=0)
    if options.showinstance and options.regionid:
        describe_instances(options.regionid, quiet=0)
    if options.createinstance:
        describe_create(regionid = options.regionid, zoneid = options.zoneid, instancename = options.instancename, description = options.description, 
                        hostname = options.hostname, password = options.password, securitygroupid = options.securitygroupid, instancetype = options.instancetype, 
                        imageid = options.imageid, instancechargetype = options.instancechargetype, period = options.period, iooptimized = options.iooptimized, 
                        AllocatePublicIpAddress = options.allocatepublicipAddress, InternetMaxBandwidthOut = options.internetmaxbandwidthout, 
                        InternetChargeType = options.internetchargetype, systemdiskcategory = options.systemdiskcategory, 
                        DataDiskCategory = options.datadiskcategory, DataDiskSize = options.datadisksize, quiet=True)
    if options.startinstance and options.instanceid:
        describe_start(options.instanceid.split(','), quiet=0)
    if options.stopinstance and options.instanceid:
        describe_stop(options.instanceid.split(','), quiet=0)
    if options.rebootinstance and options.instanceid:
        describe_reboot(options.instanceid.split(','), quiet=0)
    if options.deleteinstance and options.instanceid:
        describe_delete(options.instanceid.split(','), quiet=0)
    if options.openipaddress:
        describe_allocatepublicipaddress(options.instanceid.split(','), quiet=0)
    if options.changenetworkout and options.instanceid:
       change_network(options.instanceid.split(','), out = options.networkoutnum, quiet=0)
    if options.showdb and options.regionid:
       show_db(options.regionid, quiet=0)
    if options.showdbtype:
       show_db_type()
    if options.createdb and options.regionid:
       if not (options.regionid and options.dbengine and options.dbengineversion and options.dbinstanceclass and options.dbinstancestorage and options.dbinstancenettype and options.dbsecurityiplist and options.dbpaytype):
           sys.exit('create db parameter loss')
       create_db(RegionId = options.regionid, ZoneId = options.zoneid, Engine = options.dbengine, EngineVersion = options.dbengineversion, DBInstanceClass = options.dbinstanceclass, DBInstanceStorage = options.dbinstancestorage,
                 DBInstanceNetType = options.dbinstancenettype, DBInstanceDescription = options.dbinstancedescription, SecurityIPList = options.dbsecurityiplist, PayType = options.dbpaytype,
                 Period = options.dbperiod, UsedTime = options.dbusedtime, quiet = 0)
    if options.deletedb and options.dbinstanceid:
        delete_db(options.dbinstanceid.split(','), quiet=0)
    if options.createdbslave and options.regionid:
       if not (options.regionid and options.dbinstanceid and options.dbinstanceclass and options.dbinstancestorage and options.dbinstancenettype):
           sys.exit('create slave db parameter loss')
       slave_db(dbinstanceid = options.dbinstanceid.split(','), RegionId = options.regionid, 
                ZoneId = options.zoneid, DBInstanceClass = options.dbinstanceclass, DBInstanceStorage = options.dbinstancestorage, DBInstanceDescription = options.dbinstancedescription, quiet=0)
