import os
import re
import sys
import json
import base64
import pymongo
import requests
import ConfigParser
from optparse    import OptionParser
from aliyunsdkcore import client
from aliyunsdkecs.request.v20140526 import DescribeDisksRequest, \
                                           DescribeInstancesRequest                                          
from aliyunsdkrds.request.v20140815 import DescribeDBInstancesRequest, \
                                           DescribeDBInstanceAttributeRequest

class Aly(object):
    def __init__(self, auths = [], RegionId = None):
        a = requests.adapters.HTTPAdapter(max_retries = 3)
        self.requests = requests.Session()
        self.requests.mount('http://',  a)
        self.requests.mount('https://', a)
        self.clt_conn_list = []
        for auth in auths:
            accessKeyId     = auth.get('AccessKeyId',     None)
            accessKeySecret = auth.get('AccessKeySecret', None)
            if accessKeyId and accessKeySecret and RegionId:
                clt = client.AcsClient(accessKeyId, accessKeySecret, RegionId)
                self.clt_conn_list.append(clt)
            else:
                print '>>> Aly Class Params Error'

    def get_esc_price(self, vm_region_no    = None, instance_type   = None, systemdisk_category = None, 
                            systemdisk_size = None, iooptimized     = None, vm_os_kind   = None, 
                            datadisk_item   = None, vm_is_flow_type = None, vm_bandwidth = None, discount = 1):
        params_componentCode = {"componentCode":"vm_region_no","properties":[{"code":"vm_region_no","value":vm_region_no}]}
        params_instance_type = {"componentCode":"instance_type","properties":[{"code":"instance_type","value":instance_type},{"code":"instance_generation","value":"ecs-1"}]}
        params_iooptimized   = {"componentCode":"iooptimized","properties":[{"code":"iooptimized","value":iooptimized}]}
        params_systemdisk    = {"componentCode":"systemdisk","properties":[{"code":"systemdisk_category","value":systemdisk_category},{"code":"systemdisk_size","value":systemdisk_size}]}
        params_datadisk      = {"componentCode":"datadisk","properties":[{"code":"datadisk_category","value":""},{"code":"datadisk_size","value":""}]}
        params_vm_os         = {"componentCode":"vm_os","properties":[{"code":"vm_os_kind","value":vm_os_kind}]}
        params_vm_bandwidth  = {"componentCode":"vm_bandwidth","properties":[{"code":"vm_is_flow_type","value":vm_is_flow_type},{"code":"vm_bandwidth","value":vm_bandwidth}]}
        params               = {"commodities":[{"commodityCode":"vm","specCode":"vm","chargeType":"PREPAY","duration":1,"free":False,"orderType":"BUY","prePayPostCharge":False,
                                                "pricingCycle":"Month","quantity":1,"renewChange":False,"syncToSubscription":False,"instanceId":"","components":[]}]}

        if datadisk_item: 
            for i in datadisk_item:
                params_datadisk['properties'][0]['value'] = i[0]
                params_datadisk['properties'][1]['value'] = i[1]
                params['commodities'][0]['components'].append(params_datadisk)
        params['commodities'][0]['components'].append(params_vm_os)
        params['commodities'][0]['components'].append(params_systemdisk)
        params['commodities'][0]['components'].append(params_iooptimized)
        params['commodities'][0]['components'].append(params_vm_bandwidth)
        params['commodities'][0]['components'].append(params_instance_type)
        params['commodities'][0]['components'].append(params_componentCode)

        url = 'https://buy.aliyun.com/ajax/CalculatorAjax/getPrice.jsonp?callback=jQuery&data=%s' %base64.b64encode(json.dumps(params))
        headers = {'Referer' : 'https://www.aliyun.com/price/product'}
        result = json.loads(self.requests.get(url, headers = headers).text.replace('jQuery(', '').replace(');', ''))
        return result

    def get_host_list(self, pageNumber = 1, pageSize = 100, image = False, price = False):
        result = []
        request = DescribeInstancesRequest.DescribeInstancesRequest()
        request.set_accept_format('json')
        request.set_query_params(dict(PageNumber = pageNumber, PageSize = pageSize))
        for clt in self.clt_conn_list:
            clt_result = json.loads(clt.do_action(request))
            result += clt_result['Instances']['Instance']
            totalCount = clt_result['TotalCount']
            while totalCount > pageNumber * pageSize:
                pageNumber += 1 
                request.set_query_params(dict(PageNumber = pageNumber, PageSize = pageSize))
                clt_result = json.loads(clt.do_action(request))
                result += clt_result['Instances']['Instance']
        if image:
            result_dict = {}
            for r in result:
                result_dict[r['InstanceId']] = r
            result_dict_keys = result_dict.keys()
            images = self.get_image_list()
            for disk in images:
                if disk['InstanceId'] and disk['InstanceId'] in result_dict_keys:
                    result_dict[disk['InstanceId']].setdefault('images', [])
                    result_dict[disk['InstanceId']]['images'].append(disk)
            result = result_dict.values()
        if price:
            tmp = []
            vm_region_no_list = set(re.findall(r'\| (cn-.*?)"', requests.get('https://www.aliyun.com/price/detail/ecs').text))
            for r in result:
                vm_region_no = [x for x in vm_region_no_list if r['RegionId'] in x][0]
                instance_type = r['InstanceType']
                datadisk    = [(x['Category'], x['Size']) for x in r['images'] if x['Type'] != 'system']
                systemdisk  = [(x['Category'], x['Size']) for x in r['images'] if x['Type'] == 'system'][0]
                iooptimized = r['IoOptimized'] and 'optimized' or 'none'
                if r['InstanceChargeType'] == 'PrePaid' and r['InternetChargeType'] == 'PayByBandwidth':
                    vm_is_flow_type = 5
                elif r['InstanceChargeType'] == 'PrePaid' and r['InternetChargeType'] == 'PayByTraffic':
                    vm_is_flow_type = 1
                else:
                    tmp.append(r)
                    continue
                vm_bandwidth = r['InternetMaxBandwidthOut']*1024
                r['price'] = self.get_esc_price(vm_region_no = vm_region_no, instance_type = instance_type, systemdisk_category = systemdisk[0],
                                                systemdisk_size = systemdisk[1], iooptimized = iooptimized, vm_os_kind = 'linux',
                                                datadisk_item = datadisk, vm_is_flow_type = vm_is_flow_type, vm_bandwidth = vm_bandwidth, discount = 1)
                tmp.append(r)
            result = tmp
        return result

    def get_image_list(self, pageNumber = 1, pageSize = 100):
        result = []
        request = DescribeDisksRequest.DescribeDisksRequest()
        request.set_accept_format('json')
        request.set_query_params(dict(PageNumber = pageNumber, PageSize = pageSize))
        for clt in self.clt_conn_list:
            clt_result = json.loads(clt.do_action(request))
            result += clt_result['Disks']['Disk']
            totalCount = clt_result['TotalCount']
            while totalCount > pageNumber * pageSize:
                pageNumber += 1 
                request.set_query_params(dict(PageNumber = pageNumber, PageSize = pageSize))
                clt_result = json.loads(clt.do_action(request))
                result += clt_result['Disks']['Disk']
        return result

    def get_rds_list(self, pageNumber = 1, pageSize = 100, price = False):
        tmp    = []
        result = []
        request = DescribeDBInstancesRequest.DescribeDBInstancesRequest()
        request.set_accept_format('json')
        request.set_query_params(dict(PageNumber = pageNumber, PageSize = pageSize))
        request1 = DescribeDBInstanceAttributeRequest.DescribeDBInstanceAttributeRequest()
        request1.set_accept_format('json')
        for clt in self.clt_conn_list:
            clt_result = json.loads(clt.do_action(request))
            result += clt_result['Items']['DBInstance']
            totalCount = clt_result['TotalRecordCount']
            while totalCount > pageNumber * pageSize:
                pageNumber += 1 
                request.set_query_params(dict(PageNumber = pageNumber, PageSize = pageSize))
                clt_result = json.loads(clt.do_action(request))
                result += clt_result['Items']['DBInstance']
        for r in result:
            request1.set_query_params({'DBInstanceId' : r['DBInstanceId']})
            tmp.append(json.loads(clt.do_action(request1))['Items']['DBInstanceAttribute'][0])
        if price:
            print len(tmp)
            url = 'https://buy.aliyun.com/ajax/CalculatorAjax/Product.jsonp?callback=jQuery&commodity_code=rds&spec_code=rds' 
            headers = {'Referer' : 'https://www.aliyun.com/price/product'}
            rds_region_Product = json.loads(self.requests.get(url, headers = headers).text.replace('jQuery(', '').replace(');', ''))
            rds_region_list    = set([x['value'] for x in rds_region_Product['data']['components']['rds_region']['rds_region']])
            for num, ri in enumerate(tmp): 
                if ri['PayType'] == 'Prepaid' and ri['DBInstanceType'] == 'Primary':
                    rds_class  = ri['DBInstanceClass']
                    rds_region = [x for x in rds_region_list if ri['RegionId'] in x][0]
                    rds_dbtype = ri['Engine'].lower()
                    rds_storage = ri['DBInstanceStorage']
                    rds_price = self.get_rds_price(rds_class = rds_class, rds_region = rds_region, rds_dbtype = rds_dbtype, rds_storage = rds_storage, discount = 1)
                    if rds_price['code'] == 200:
                        ri['price'] = rds_price
                        tmp[num] = ri
        return tmp

    def get_rds_price(self, rds_class = None, rds_region = None, rds_dbtype = None, rds_storage = None, discount = 1):
        params_rds_class   = {"componentCode":"rds_class","properties":[{"code":"rds_class","value":rds_class}]}
        params_rds_region  = {"componentCode":"rds_region","properties":[{"code":"rds_region","value":rds_region}]}
        params_rds_dbtype  = {"componentCode":"rds_dbtype","properties":[{"code":"rds_dbtype","value":rds_dbtype}]}
        params_rds_storage = {"componentCode":"rds_storage","properties":[{"code":"rds_storage","value":rds_storage}]}
        params             = {"commodities":[{"commodityCode":"rds","specCode":"rds","chargeType":"PREPAY","duration":1,"free":False,"orderParams":{},
                                              "orderType":"BUY","prePayPostCharge":False,"pricingCycle":"Month","quantity":1,"renewChange":False,
                                              "syncToSubscription":False,"instanceId":"","components":[]}]}

        params['commodities'][0]['components'].append(params_rds_class)
        params['commodities'][0]['components'].append(params_rds_region)
        params['commodities'][0]['components'].append(params_rds_dbtype)
        params['commodities'][0]['components'].append(params_rds_storage)

        url = 'https://buy.aliyun.com/ajax/CalculatorAjax/getPrice.jsonp?callback=jQuery&data=%s' %base64.b64encode(json.dumps(params))
        headers = {'Referer' : 'https://www.aliyun.com/price/product'}
        result = json.loads(self.requests.get(url, headers = headers).text.replace('jQuery(', '').replace(');', ''))
        return result

if __name__ == '__main__':
    access_key_id       = '';
    access_key_secret   = '';
    CONFIGFILE    = os.path.dirname(os.path.abspath(__file__)) + '/.aliyuncredentials'
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

    (options, args) = parser.parse_args()
    if options.config and options.accesskeyid and options.accesskeysecret:
        configure_accesskeypair(options.accesskeyid, options.accesskeysecret); sys.exit(0)
    else: setup_credentials()

    auth = [{'AccessKeyId': access_key_id, 'AccessKeySecret': access_key_secret}]
    mongo_server = options.mongoserver
    RegionId = 'cn-hangzhou'
    conn        = pymongo.MongoClient(options.mongoserver)
    instance_esc = conn.aly.instance
    instance_rds = conn.aly.instance_rds
    aly = Aly(auth, RegionId)
    for instance in aly.get_host_list(image = True, price = True):
        instance_dict = instance_esc.find({'InstanceId' : instance['InstanceId']}).sort('_id', pymongo.DESCENDING)
        if instance_dict.count() == 0:
            instance_esc.insert(instance)
        else:
            old = instance_dict[0]
            if old['Cpu'] != instance['Cpu'] or old['Memory'] != instance['Memory'] or old['images'] != instance['images'] or \
            old['ExpiredTime'] != instance['ExpiredTime'] or old['InternetMaxBandwidthOut'] != instance['InternetMaxBandwidthOut']:
                instance_esc.insert(instance)
    for instance in aly.get_rds_list(price = True):
        instance_dict = instance_rds.find({'DBInstanceId' : instance['DBInstanceId']}).sort('_id', pymongo.DESCENDING)
        if instance_dict.count() == 0:
            instance_rds.insert(instance)
        else:
            old = instance_dict[0]
            if old['MaxIOPS'] != instance['MaxIOPS'] or old['DBInstanceStorage'] != instance['DBInstanceStorage'] or \
               old['DBInstanceClass'] != instance['DBInstanceClass'] or old['ExpireTime'] != instance['ExpireTime']:
                instance_rds.insert(instance)
