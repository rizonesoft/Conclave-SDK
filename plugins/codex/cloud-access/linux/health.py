import urllib.request,json
for plugin,port in [('atera',18781),('domains-co-za',18782),('bunny-net',18783)]:
 d=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/health?details=true'))
 c=d['components'];m=c['mcp']['details']
 print(json.dumps({'plugin':plugin,'ready':d['ready'],'pollFailures':c['control-plane']['details']['consecutive_failures'],'initialized':m.get('initialize',{}).get('ok'),'tools':m.get('tools_list',{}).get('retained_count'),'discoveryComplete':m.get('tools_list',{}).get('complete')}))