# Synthetic fixtures only. No original project data is required.
from pathlib import Path
import sys,subprocess,tempfile,json,zipfile,os,hashlib,threading,ssl,shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
skill=ROOT/'skills'/'legacy-site-to-static';scripts=skill/'scripts';checks=[]

def invoke(script,*args):
    r=subprocess.run([sys.executable,'-B',str(scripts/script),*map(str,args)],capture_output=True,text=True,timeout=20)
    try:report=json.loads(r.stdout)
    except ValueError:raise AssertionError((r.returncode,r.stdout,r.stderr))
    return r,report

with tempfile.TemporaryDirectory(prefix='legacy-static-test-') as temporary:
    t=Path(temporary).resolve();raw=t/'raw';raw.mkdir()
    (raw/'old.php').write_text('<?php fixture only;')
    (raw/'data.sql.gz').write_bytes(b'\x1f\x8bnot-an-executable-gzip')
    outside=t/'outside.txt';outside.write_text('OUTSIDE')
    (raw/'link').symlink_to(outside)
    z=t/'backup.zip'
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as out:
        out.writestr('Uploads/image.png',b'image')
        out.writestr('Runtime/core.123',bytes(1024*1024))
        out.writestr('../unsafe.php','<?php')
    digest=hashlib.sha256(z.read_bytes()).hexdigest();before=set(t.rglob('*'))
    r,j=invoke('inventory_sources.py',raw,z,'--details','--strict')
    assert r.returncode==0 and j['ok'];assert j['sources'][0]['counts']['database']==1
    assert any(x['flags']==['link_not_traversed'] for x in j['sources'][0]['path_flags'])
    assert any('unsafe_archive_path' in x['flags'] for x in j['sources'][1]['path_flags'])
    assert set(t.rglob('*'))==before and hashlib.sha256(z.read_bytes()).hexdigest()==digest
    r,j=invoke('inventory_sources.py',z,'--max-entries','1','--strict');assert r.returncode==1 and j['sources'][0]['truncated']
    r=subprocess.run([sys.executable,'-B',str(scripts/'inventory_sources.py'),str(raw),'--out',str(raw/'report.json')],capture_output=True,text=True)
    assert r.returncode!=0 and not (raw/'report.json').exists();checks.append('Source inventory does not extract, execute or modify inputs; flags links/traversal and reports truncation; refuses source-path output')

    site=t/'public';(site/'assets').mkdir(parents=True);(site/'en').mkdir()
    (site/'assets/a.png').write_bytes(b'fixture-image')
    (site/'assets/site.css').write_text('body { background: url(a.png) }')
    home='<html><head><title>Catalogue</title><link rel="stylesheet" href="assets/site.css"></head><body><main id="top"><a href="en/index.html">English</a><img src="assets/a.png"><a href="#top">Top</a><div style="background:url(assets/a.png)"></div></main></body></html>'
    (site/'index.html').write_text(home)
    (site/'en/index.html').write_text('<title>English</title><img src="../assets/a.png"><a href="../index.html#top">Home</a>')
    (site/'robots.txt').write_text('User-agent: *\nAllow: /\n')
    (site/'site.json').write_text(json.dumps({'products':[{'id':1}]}))
    (site/'version.json').write_text(json.dumps({'version':'r2','products':1,'confirmedTranslations':1}))
    policy={'validation':{'data_file':'site.json','version_file':'version.json','expected_version':'r2','expected_counts':{'products':1},'previous_confirmed_translations':1}}
    config=t/'project.json';config.write_text(json.dumps(policy))
    r,j=invoke('check_release.py',site,'--mode','formal','--policy',config)
    assert r.returncode==0 and j['ok'] and j['summary']['errors']==0 and j['summary']['local_references']>=6
    assert len(j['manifest'])==7;checks.append('Clean formal release passes with nested-language links, anchors, CSS and inline-image references; SHA256 manifest covers public files')

    (site/'index.html').write_text(home.replace('assets/a.png','assets/A.png'))
    r,j=invoke('check_release.py',site,'--mode','formal');assert r.returncode==1 and any(x['kind']=='local_reference_case_mismatch' for x in j['issues'])
    checks.append('Reference spelling is checked against the manifest even on case-insensitive local filesystems')

    (site/'index.html').write_text(home.replace('assets/a.png','assets/missing.png'))
    r,j=invoke('check_release.py',site,'--mode','formal');assert r.returncode==1 and any(x['kind']=='missing_local_reference' for x in j['issues'])
    (site/'index.html').write_text(home.replace('<title>','<meta name="robots" content="noindex"><title>'))
    r,j=invoke('check_release.py',site,'--mode','formal');assert r.returncode==1 and any(x['kind']=='formal_entry_not_indexable' for x in j['issues'])
    (site/'index.html').write_text(home)
    (site/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    r,j=invoke('check_release.py',site,'--mode','formal');assert r.returncode==1 and any(x['kind']=='robots_blocks_formal_homepage' for x in j['issues'])
    policy['validation']['require_indexing']=False;config.write_text(json.dumps(policy));r,j=invoke('check_release.py',site,'--mode','formal','--policy',config);assert r.returncode==0
    policy['validation']['require_indexing']=True;(site/'robots.txt').write_text('User-agent: *\nAllow: /\n')
    (site/'version.json').write_text(json.dumps({'version':'r2','products':1,'confirmedTranslations':0}));config.write_text(json.dumps(policy))
    r,j=invoke('check_release.py',site,'--mode','formal','--policy',config);assert r.returncode==1 and any(x['kind']=='confirmed_translation_count_decreased' for x in j['issues'])
    policy['validation']['translation_decrease_accepted']=True;config.write_text(json.dumps(policy));r,j=invoke('check_release.py',site,'--mode','formal','--policy',config);assert r.returncode==0 and j['summary']['warnings']==1
    checks.append('Missing assets, formal noindex, blocking robots and unaccepted translation loss fail; explicit user indexing/translation policies remain possible')

    (site/'leak.json').write_text('{"DB_PASSWORD":"fixture-secret-that-must-not-be-printed"}')
    (site/'editor.json').write_text('{"editorAssets":{},"enHistory":[]}')
    (site/'bad.php.jpg').write_text('<?php fixture')
    (site/'escape.txt').symlink_to(outside)
    r,j=invoke('check_release.py',site,'--mode','formal')
    kinds={x['kind'] for x in j['issues']};assert {'credential_assignment_candidate','private_editing_metadata','server_code_or_sensitive_file','link_or_special_file_not_allowed'}<=kinds
    assert 'fixture-secret-that-must-not-be-printed' not in r.stdout
    for name in ['leak.json','editor.json','bad.php.jpg','escape.txt']:(site/name).unlink()
    (site/'index.html').write_text(home+'<form action="/api/contact" method="post"></form>')
    r,j=invoke('check_release.py',site,'--mode','formal');assert r.returncode==1
    policy['validation']['allowed_post_form_actions']=['/api/contact'];config.write_text(json.dumps(policy))
    r,j=invoke('check_release.py',site,'--mode','formal','--policy',config);assert r.returncode==0
    checks.append('Server-code disguises, symlinks, credential values and private drafts are blocked/redacted; declared contact-form backends work without fake local files')

    policy['validation']['record_pages']=[{'collection':'products','id_field':'id','pattern':'product-{id}.html'}]
    config.write_text(json.dumps(policy));r,j=invoke('check_release.py',site,'--mode','formal','--policy',config)
    assert r.returncode==1 and any(x['kind']=='record_page_missing' for x in j['issues'])
    (site/'product-1.html').write_text('<title>Product 1</title><a href="index.html">Home</a>')
    policy['validation']['public_download_archives']=['manual.zip']
    with zipfile.ZipFile(site/'manual.zip','w') as z:z.writestr('manual.txt','Public documentation')
    config.write_text(json.dumps(policy));r,j=invoke('check_release.py',site,'--mode','formal','--policy',config)
    assert r.returncode==0
    checks.append('Declared record-to-page mappings catch unlinked missing detail pages, and explicitly reviewed public ZIP downloads are accepted')

    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            if self.path.startswith('/redirect'):
                self.send_response(301);self.send_header('Location','/should-not-be-fetched?token=private');self.end_headers();return
            if self.path.startswith('/large'):
                self.send_response(200);self.end_headers();self.wfile.write(b'x'*1024);return
            self.send_response(200);self.send_header('Set-Cookie','fixture-sensitive-cookie');self.end_headers();self.wfile.write(b'fixture-private-body')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(server.server_port)
    try:
        r,j=invoke('probe_routes.py',origin+'/ok?token=private');assert r.returncode==0 and j['ok']
        assert 'token=private' not in r.stdout and 'fixture-private-body' not in r.stdout and 'fixture-sensitive-cookie' not in r.stdout
        r,j=invoke('probe_routes.py',origin+'/redirect','--expect-status','301');assert r.returncode==0 and j['checks'][0]['status']==301 and all(not x.startswith('/should-not') for x in calls)
        assert 'token=private' not in r.stdout
        r,j=invoke('probe_routes.py',origin+'/large','--max-bytes','10');assert r.returncode==1 and j['checks'][0]['body_truncated'] and j['checks'][0]['body_sha256'] is None
        r=subprocess.run([sys.executable,'-B',str(scripts/'probe_routes.py'),'https://user:password@example.invalid/'],capture_output=True,text=True);assert r.returncode!=0
    finally:server.shutdown();server.server_close();thread.join()
    checks.append('HTTP probes do not follow redirects or log bodies/Cookies/query secrets; oversized bodies and credential-bearing URLs fail')
    openssl=shutil.which('openssl')
    if openssl:
        key=t/'test-tls.key';cert=t/'test-tls.crt'
        r=subprocess.run([openssl,'req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost'],capture_output=True,timeout=20)
        assert r.returncode==0
        tls_server=ThreadingHTTPServer(('127.0.0.1',0),Handler);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(str(cert),str(key));tls_server.socket=ctx.wrap_socket(tls_server.socket,server_side=True)
        thread=threading.Thread(target=tls_server.serve_forever,daemon=True);thread.start()
        try:
            r,j=invoke('probe_routes.py','https://127.0.0.1:'+str(tls_server.server_port)+'/')
            assert r.returncode==1 and j['checks'][0]['status'] is None and j['checks'][0]['error'] and j['checks'][0]['tls_verification_enabled']
        finally:tls_server.shutdown();tls_server.server_close();thread.join()
        checks.append('HTTPS probe rejects an untrusted self-signed certificate and does not claim a verified response')

print(json.dumps({'passed':True,'checks':checks},indent=2))
