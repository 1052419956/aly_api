from __future__ import division

import os
import json
import pymongo
import threading
import ConfigParser
from   optparse      import OptionParser
from   influxdb      import InfluxDBClient
from   aliyunsdkcore import client
from   aliyunsdkcms.request.v20160318 import QueryMetricLastRequest

class mythread(object):
    def __init__(self, worker = None, producer = [], worker_num = 40):
        self.worker     = worker
        self.worker_num = worker_num
        self.queue_producer = producer
        self.result = []

    def __work(self):
        while 1:
            try:
                params = self.queue_producer.pop()
                tp = type(params)
                if   tp is tuple or tp is list: self.result.append(self.worker(*params))
                elif tp is dict:                self.result.append(self.worker(**params))
                else:                           self.result.append(self.worker(params))
            except IndexError:
                break

    def run(self):
        thread_list = []
        worker_num = self.worker_num < len(self.queue_producer) and self.worker_num or len(self.queue_producer)
        for _ in xrange(worker_num): thread_list.append(threading.Thread(target=self.__work))
        for tmp in thread_list: tmp.start()
        for tmp in thread_list: tmp.join()
        return self.result

def get_rds_instance_list(mongo_host):
    conn = pymongo.MongoClient(mongo_host)
    db   = conn.aly.instance_rds
    return db.find({}, {'DBInstanceId' : 1, 'MaxIOPS' : '1', 'DBInstanceMemory' : 1, 'DBInstanceStorage' : 1, 
                        'DBInstanceDescription' : 1, 'RegionId' : 1, 'MaxConnections': 1})


def save_rds_instance_monitoring(rds_instance, metric):
    clt = client.AcsClient(access_key_id, access_key_secret, 'cn-hangzhou')
    request = QueryMetricLastRequest.QueryMetricLastRequest()
    request.set_accept_format('json')
    request.set_Project('acs_rds')
    request.set_Metric(metric)
    request.set_Dimensions("{instanceId:'%s'}" %rds_instance['DBInstanceId'])
    request.set_Period('300')
    result = json.loads(clt.do_action(request))['Datapoints'][0]
    if result.get('type', None):        del result['type']
    if result.get('timestamp', None):   del result['timestamp']
    if result.get('instanceId', None):  del result['instanceId']
    if result.get('SampleCount', None): del result['SampleCount']
    result = dict([(x[0],float(x[1])) for x in result.items()])
    influxdb = InfluxDBClient('192.168.70.132', 8086, 'easemob', 'thepushbox', 'monitor')
    metric_list = ['CpuUsage', 'DiskUsage', 'IOPSUsage', 'ConnectionUsage', 'MemoryUsage', 'MySQL_NetworkInNew', 'MySQL_NetworkOutNew']
    if   metric == 'DiskUsage':
        result['max_value'] = rds_instance['DBInstanceStorage']
        result['absolute_value'] = result['value']/100*rds_instance['DBInstanceStorage']
    elif metric == 'IOPSUsage':
        result['max_value'] = rds_instance['MaxIOPS']
        result['absolute_value'] = result['value']/100*rds_instance['MaxIOPS']
    elif metric == 'ConnectionUsage':
        result['max_value'] = rds_instance['MaxConnections']
        result['absolute_value'] = result['value']/100*rds_instance['MaxConnections']
    elif metric == 'MemoryUsage':
        result['max_value'] = rds_instance['DBInstanceMemory']
        result['absolute_value'] = result['value']/100*rds_instance['DBInstanceMemory']
    influxdb.write_points([{"measurement":metric,"tags":{"hostname":rds_instance['DBInstanceDescription'],"region":rds_instance['RegionId']}, "fields":result}])


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

    metric_list = ['CpuUsage', 'DiskUsage', 'IOPSUsage', 'ConnectionUsage', 'MemoryUsage', 'MySQL_NetworkInNew', 'MySQL_NetworkOutNew']
    work_list = [(rds_instance, metric) for rds_instance in get_rds_instance_list(options.mongoserver) for metric in metric_list]
    mt = mythread(save_rds_instance_monitoring, work_list)
    mt.run()
