import os
import sys
import json
import time
import pymongo

from aliyunsdkcore import client
from aliyunsdkecs.request.v20140526 import StartInstanceRequest, \
                                           CreateInstanceRequest, \
                                           DescribeInstancesRequest, \
                                           AllocatePublicIpAddressRequest

def copyInstanceConfigCreateInstance(host = None, oldname = None, newname = None):
    conn   = pymongo.MongoClient(host).aly.instance
    result = conn.find({'InstanceName' : oldname}).sort('_id', pymongo.DESCENDING)
    if result.count() == 0: print '>> Not Find %s' %oldname; sys.exit(1)
    params = {}
    params['RegionId']                = result[0]['RegionId']
    params['ZoneId']                  = result[0]['ZoneId']
    params['ImageId']                 = [x['ImageId'] for x in result[0]['images'] if x['Type'] == 'system'][0]
    params['InstanceType']            = result[0]['InstanceType']
    params['SecurityGroupId']         = result[0]['SecurityGroupIds']['SecurityGroupId'][0]
    params['InstanceName']            = newname
    params['Description']             = newname
    params['InternetChargeType']      = result[0]['InternetChargeType']
    params['InternetMaxBandwidthOut'] = result[0]['InternetMaxBandwidthOut']
    params['HostName']                = newname
    params['IoOptimized']             = result[0]['IoOptimized'] and 'optimized' or 'none'
    params['SystemDisk.Category']     = [x['Category'] for x in result[0]['images'] if x['Type'] == 'system'][0]
    params['SystemDisk.Size']         = [x['Size'] for x in result[0]['images'] if x['Type'] == 'system'][0]
    params['DataDisk.1.Category']     = 'cloud'
    params['DataDisk.1.Size']         = 100
    params['InstanceChargeType']      = result[0]['InstanceChargeType']
    params['Period']                  = 1

    clt = client.AcsClient(access_key_id, access_key_secret, params['RegionId'])
    request = CreateInstanceRequest.CreateInstanceRequest()
    request.set_accept_format('json')
    request.set_query_params(params)
    #c_r = json.loads(clt.do_action(request))
    c_r = json.loads('{"InstanceId":"i-234hs2qwx","RequestId":"D3209274-D317-4041-8304-80D19F2ABB78"}')
    if c_r.get('InstanceId', None) == None: print '>> Create Instance %s' %c_r['Message']; sys.exit(1)
    if result[0]['PublicIpAddress']['IpAddress']:
        request = AllocatePublicIpAddressRequest.AllocatePublicIpAddressRequest()
        request.set_accept_format('json')
        request.set_query_params({'InstanceId': c_r['InstanceId']})
        #p_r = json.loads(clt.do_action(request))
        p_r = json.loads('{"RequestId": "080A06E3-75C5-4256-910B-23278063C38F", "IpAddress": "114.55.149.208"}')
        if p_r.get('IpAddress', None) == None: print '>> Create Network %s' %c_r['Message']; sys.exit(1)
    request = DescribeInstancesRequest.DescribeInstancesRequest()
    request.set_accept_format('json')
    request.set_query_params({'InstanceIds' : '["%s"]' %c_r['InstanceId']})
    d_r = json.loads(clt.do_action(request))
    innerIpAddress = d_r['Instances']['Instance'][0]['InnerIpAddress']['IpAddress'][0]
    request = StartInstanceRequest.StartInstanceRequest()
    request.set_accept_format('json')
    request.set_query_params({'InstanceId' : c_r['InstanceId']})
    s_r = json.loads(clt.do_action(request))
    while 1:
        request = DescribeInstancesRequest.DescribeInstancesRequest()
        request.set_accept_format('json')
        request.set_query_params({'InstanceIds' : '["%s"]' %c_r['InstanceId']})
        d_r = json.loads(clt.do_action(request))
        if d_r['Instances']['Instance'][0]['Status'] == 'Running': break
        time.sleep(10)
    print os.popen('echo /home/easemob/zhaoyufeng/autoinitserver.sh %s %s' %(innerIpAddress, newname)).read()


if __name__ == '__main__':
    import os
    import ConfigParser
    from   optparse import OptionParser

    access_key_id       = '';
    access_key_secret   = '';
    CONFIGFILE    = os.path.dirname(os.path.abspath(__file__)) + '/.aliyuncredentials_rw'
    CONFIGSECTION = 'Credentials'

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

    parser = OptionParser()

    parser.add_option('-i', '--id',              dest='accesskeyid',     help='specify access key id')
    parser.add_option('-s', '--secret',          dest='accesskeysecret', help='specify access key secret')
    parser.add_option('-c', '--config',          dest='config',          help='specify when creating an instance',  action='store_true')
    parser.add_option('-m', '--mongoserver',     dest='mongoserver',     help='Ex: 192.168.70.132:27017', default = '127.0.0.1:27017')
    parser.add_option('-o', '--oldname',         dest='oldname',         help='copy src  InstanceName',   default = None)
    parser.add_option('-n', '--newname',         dest='newname',         help='copy dest InstanceName',   default = None)

    (options, args) = parser.parse_args()
    if options.config and options.accesskeyid and options.accesskeysecret:
        configure_accesskeypair(options.accesskeyid, options.accesskeysecret); sys.exit(0)
    else: setup_credentials()
 
    if options.oldname and options.newname:
        copyInstanceConfigCreateInstance(options.mongoserver, options.oldname, options.newname)
    else:
        print '>> oldname or newname error'; sys.exit(1)








