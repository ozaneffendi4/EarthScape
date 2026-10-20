"""Start an isolated single-machine Hadoop lab without SSH or privileged Docker."""
import os,sys,subprocess,time,urllib.request,signal
from pathlib import Path
from xml.sax.saxutils import escape
signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
root=Path(__file__).resolve().parents[1]
hadoop=Path(os.environ['HADOOP_HOME']);state=Path(os.environ.get('EARTHSCAPE_CLUSTER',str(root/'cluster-runtime')));state.mkdir(parents=True,exist_ok=True)
base=state/'conf';base.mkdir(exist_ok=True)
import shutil
for p in (hadoop/'etc/hadoop').glob('*'):
 if p.is_file():shutil.copyfile(p,base/p.name)
def xml(path,values):path.write_text('<configuration>'+''.join('<property><name>'+k+'</name><value>'+escape(str(v))+'</value></property>' for k,v in values.items())+'</configuration>')
xml(base/'core-site.xml',{'fs.defaultFS':'hdfs://127.0.0.1:9000','hadoop.tmp.dir':str(state/'tmp')})
xml(base/'hdfs-site.xml',{'dfs.namenode.name.dir':str(state/'namenode'),'dfs.namenode.http-address':'0.0.0.0:9870','dfs.replication':'2','dfs.permissions.enabled':'true','dfs.namenode.datanode.registration.ip-hostname-check':'false'})
xml(base/'mapred-site.xml',{'mapreduce.framework.name':'yarn','mapreduce.map.memory.mb':256,'mapreduce.reduce.memory.mb':256,'mapreduce.map.java.opts':'-Xmx192m','mapreduce.reduce.java.opts':'-Xmx192m','mapreduce.job.ubertask.enable':'false','yarn.app.mapreduce.am.resource.mb':256,'yarn.app.mapreduce.am.command-opts':'-Xmx192m','mapreduce.application.classpath':','.join([str(hadoop/'share/hadoop/mapreduce/*'),str(hadoop/'share/hadoop/mapreduce/lib/*'),str(hadoop/'share/hadoop/common/*'),str(hadoop/'share/hadoop/common/lib/*'),str(hadoop/'share/hadoop/hdfs/*'),str(hadoop/'share/hadoop/hdfs/lib/*'),str(hadoop/'share/hadoop/yarn/*'),str(hadoop/'share/hadoop/yarn/lib/*')])})
xml(base/'yarn-site.xml',{'yarn.nodemanager.hostname':'127.0.0.1','yarn.nodemanager.bind-host':'127.0.0.1','yarn.nodemanager.webapp.address':'0.0.0.0:8042','yarn.resourcemanager.bind-host':'127.0.0.1','yarn.resourcemanager.scheduler.class':'org.apache.hadoop.yarn.server.resourcemanager.scheduler.fifo.FifoScheduler','yarn.resourcemanager.hostname':'127.0.0.1','yarn.resourcemanager.webapp.address':'0.0.0.0:8088','yarn.nodemanager.aux-services':'mapreduce_shuffle','yarn.nodemanager.resource.memory-mb':2048,'yarn.scheduler.minimum-allocation-mb':128,'yarn.scheduler.maximum-allocation-mb':2048,'yarn.nodemanager.vmem-check-enabled':'false','yarn.nodemanager.pmem-check-enabled':'false','yarn.nodemanager.env-whitelist':'JAVA_HOME,HADOOP_COMMON_HOME,HADOOP_HDFS_HOME,HADOOP_CONF_DIR,HADOOP_YARN_HOME,HADOOP_MAPRED_HOME,PATH,LANG,LC_ALL,JAVA_TOOL_OPTIONS'})
(base/'hadoop-env.sh').write_text('export HADOOP_HEAPSIZE_MAX=256\n');(base/'yarn-env.sh').write_text('export YARN_HEAPSIZE=256\n')
env=os.environ.copy();env.update({'HADOOP_CONF_DIR':str(base),'HADOOP_LOG_DIR':str(state/'logs'),'HADOOP_PID_DIR':str(state/'pids'),'HADOOP_MAPRED_HOME':str(hadoop),'HADOOP_COMMON_HOME':str(hadoop),'HADOOP_HDFS_HOME':str(hadoop),'HADOOP_YARN_HOME':str(hadoop),'HADOOP_ROOT_LOGGER':'WARN,console','JAVA_TOOL_OPTIONS':'--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED'})
for p in ['logs','pids']: (state/p).mkdir(exist_ok=True)
processes=[]
def start(binary,args,conf=base,label='service'):
 e=env.copy();e['HADOOP_CONF_DIR']=str(conf)
 f=(state/'logs'/f'{label}.log').open('a');p=subprocess.Popen([str(hadoop/'bin'/binary),*args],env=e,stdout=f,stderr=f);processes.append(p);return p
if not (state/'namenode/current/VERSION').exists():subprocess.run([str(hadoop/'bin/hdfs'),'namenode','-format','-nonInteractive'],env=env,check=True,stdout=subprocess.DEVNULL)
start('hdfs',['namenode'],label='namenode')
# Two independent DataNode processes with distinct storage and ports.
for i in range(2):
 conf=state/f'datanode{i}';conf.mkdir(exist_ok=True)
 for p in base.glob('*'): (conf/p.name).write_bytes(p.read_bytes())
 xml(conf/'hdfs-site.xml',{'dfs.datanode.data.dir':str(state/f'blocks{i}'),'dfs.datanode.address':f'127.0.0.1:{9866+i*10}','dfs.datanode.http.address':f'127.0.0.1:{9864+i*10}','dfs.datanode.ipc.address':f'127.0.0.1:{9867+i*10}','dfs.datanode.hostname':'localhost','dfs.replication':2,'dfs.permissions.enabled':'true'})
 start('hdfs',['datanode'],conf,f'datanode{i}')
start('yarn',['resourcemanager'],label='resourcemanager');start('yarn',['nodemanager'],label='nodemanager')
try:
 for i in range(120):
  if any(p.poll() is not None for p in processes):raise RuntimeError('Hadoop daemon exited; inspect cluster-runtime/logs')
  try:
   urllib.request.urlopen('http://127.0.0.1:9870',timeout=2);urllib.request.urlopen('http://127.0.0.1:8088',timeout=2)
   report=subprocess.run([str(hadoop/'bin/hdfs'),'dfsadmin','-report'],env=env,capture_output=True,text=True,timeout=15)
   if 'Live datanodes (2)' in report.stdout:break
  except Exception:pass
  time.sleep(1)
 else:raise RuntimeError('Hadoop initialization timeout')
 subprocess.run([str(hadoop/'bin/hdfs'),'dfsadmin','-safemode','wait'],env=env,check=True,timeout=120,stdout=subprocess.DEVNULL)
 env.update({'EARTHSCAPE_STORAGE':'hdfs','EARTHSCAPE_HOST':os.environ.get('EARTHSCAPE_HOST','127.0.0.1'),'EARTHSCAPE_ADMIN_PASSWORD':'EarthDemo!2026','EARTHSCAPE_ANALYST_PASSWORD':'AnalystDemo!2026','EARTHSCAPE_VIEWER_PASSWORD':'ViewerDemo!2026'})
 # Initial sync preserves the seed archive in HDFS even when runtime was pre-populated.
 sys.path.insert(0,str(root));import storage_pipeline
 home=Path(os.environ.get('EARTHSCAPE_DATA',str(root/'runtime')))
 os.environ.update(env)
 for p in (home/'raw').rglob('*.enc'):storage_pipeline.queue_file(p,'/earthscape/raw/'+p.parent.name+'/'+p.name,home)
 service=subprocess.Popen([sys.executable,str(root/'app.py')],env=env)
 processes.append(service);print('Hadoop cluster ready: 2 DataNodes, YARN, web dashboard',flush=True);service.wait()
finally:
 for p in reversed(processes):
  if p.poll() is None:p.terminate()
 for p in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
