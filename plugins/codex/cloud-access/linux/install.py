#!/usr/bin/env python3
import sys,json,pathlib,subprocess,urllib.request,hashlib,tarfile,zipfile,shutil,os
base=pathlib.Path('/opt/rizonetech-mcp');stage=pathlib.Path(__file__).resolve().parent;conf=pathlib.Path('/etc/rizonetech-mcp')
if os.geteuid()!=0: raise SystemExit('Root required')
resume='--resume-downloads' in sys.argv
if base.exists() or conf.exists():
 if not resume or not base.is_dir() or not conf.is_dir() or set(p.name for p in base.iterdir())!={'node','downloads'} or any(conf.iterdir()) or base.stat().st_uid!=0 or conf.stat().st_uid!=0: raise SystemExit('Existing deployment requires review')
data=json.load(sys.stdin)
for k in ('atera','domains','tunnel'):
 if not isinstance(data.get(k),str) or not data[k]: raise SystemExit('Missing credential')
base.mkdir(mode=0o755,exist_ok=resume);conf.mkdir(mode=0o700,exist_ok=resume)
downloads=base/'downloads';downloads.mkdir(mode=0o700,exist_ok=resume)
def download(url,path):
 with urllib.request.urlopen(url,timeout=90) as r,open(path,'wb') as f: shutil.copyfileobj(r,f)
nv='v22.23.3';nn=f'node-{nv}-linux-x64.tar.xz';nf=downloads/nn
download(f'https://nodejs.org/dist/{nv}/{nn}',nf)
with urllib.request.urlopen(f'https://nodejs.org/dist/{nv}/SHASUMS256.txt',timeout=30) as r: sums=r.read().decode()
expected=next(line.split()[0] for line in sums.splitlines() if line.split()[-1]==nn)
if hashlib.sha256(nf.read_bytes()).hexdigest()!=expected: raise SystemExit('Node checksum mismatch')
with tarfile.open(nf) as archive: archive.extractall(downloads,filter='data')
if not resume: shutil.move(downloads/f'node-{nv}-linux-x64',base/'node')
archive_path=downloads/'tunnel.zip'
download('https://github.com/openai/tunnel-client/releases/download/v0.0.15/tunnel-client-v0.0.15-linux-amd64.zip',archive_path)
if hashlib.sha256(archive_path.read_bytes()).hexdigest()!='8c836dc5d68d68b663d9a5c5b28ff9fa780d9f7a3fffb1c306880b8f32fab5f1': raise SystemExit('Tunnel checksum mismatch')
(base/'bin').mkdir()
with zipfile.ZipFile(archive_path) as archive:
 matches=[n for n in archive.namelist() if pathlib.PurePosixPath(n).name=='tunnel-client']
 if len(matches)!=1: raise SystemExit('Unexpected archive')
 (base/'bin'/'tunnel-client').write_bytes(archive.read(matches[0]))
(base/'bin'/'tunnel-client').chmod(0o755)
for plugin in ('atera','domains-co-za'):
 (base/plugin).mkdir();shutil.copyfile(stage/(plugin+'.mjs'),base/plugin/'server.mjs');(base/plugin/'server.mjs').chmod(0o644)
for name in ('run-tunnel.sh','probe.mjs','update-credential.py'):
 shutil.copyfile(stage/name,base/name);(base/name).chmod(0o755)
for name,value in [('atera.provider',data['atera']),('domains-co-za.provider',data['domains']),('tunnel-key',data['tunnel'])]:
 credential='tunnel-key' if name=='tunnel-key' else 'provider'
 r=subprocess.run(['systemd-creds','encrypt','--with-key=host','--name='+credential,'-',str(conf/(name+'.cred'))],input=value.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode: raise SystemExit('Credential encryption failed')
 (conf/(name+'.cred')).chmod(0o600)
shutil.copyfile(stage/'rizonetech-mcp@.service','/etc/systemd/system/rizonetech-mcp@.service')
subprocess.run(['systemctl','daemon-reload'],check=True)
for plugin,count in [('atera',10),('domains-co-za',23)]:
 subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect','--unit=rizonetech-probe-'+plugin,'-p','DynamicUser=yes','-p','LoadCredentialEncrypted=provider:'+str(conf/(plugin+'.provider.cred')),str(base/'node/bin/node'),str(base/'probe.mjs'),str(base/plugin/'server.mjs'),str(count)],check=True)
print(json.dumps({'installed':True,'node':nv,'tunnel':'v0.0.15','servicesStarted':False,'credentialsEncrypted':True}))
