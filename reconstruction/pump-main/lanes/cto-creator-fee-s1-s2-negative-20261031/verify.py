#!/usr/bin/env python3
"""Verify archived S1/S2 negative provenance and bounded raw joins; stdlib only."""
import argparse,difflib,hashlib,io,json,re,struct,tarfile,zipfile
from pathlib import Path,PurePosixPath
SYMBOL='_ZN14pump_recovered9admin_cto7execute17h3bd6d7f34f2e30d7E'
ORIGINAL='7a19affaa2c6187e04a5fe0ea298cee81fa5eb8c24cfcc30d85f615e89f7b02d'
COMMITS={'ECEA':'ecea7021fcb6a09959901522c6a4edca150a1a1b','S1':'66caa3e2de152190bab3d998e7f6df18243b8e1e','S2':'5cfe37b14b5486b802782651fde4a39985141494'}
ZIP_SHA={'ECEA':'e37113f971eb103ffa929a4c931f00d876bcdaef112f50ff0b6be451d788c48a','S1':'13b50791b061c72bae69ff94251bb8b26648be3bde0aac2cb423b6c352d50618','S2':'2cbef91934f7714bef0073698157f0b55210a05691178e7b32e17030992bc8c7'}
ELF_SHA={'ECEA':'8efdc872cdf169ae992c5efc193480c3cc4d9cc7b8808d956733e4f3ce713435','S1':'74ac33d132787888aa8257908750930a3537feb06acc6413d5365426dd23ff8a','S2':'eeb484325eb342fa9a59c19e661b8f8bd0af14b88b61c459946e712db253de88'}
LEAF='programs/pump/src/creator/admin_cto.rs'

def need(value,message):
    if not value: raise ValueError(message)
def sha(b): return hashlib.sha256(b).hexdigest()
def gitblob(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def js(b): return json.loads(b)
def safe(name):
    p=PurePosixPath(name);return not p.is_absolute() and '..'not in p.parts and str(p)==name

def tarbytes(raw,mode='r:*'):
    with tarfile.open(fileobj=io.BytesIO(raw),mode=mode)as t:
        mm=t.getmembers();need(len({m.name for m in mm})==len(mm),'duplicate tar path')
        need(all(m.isfile()and safe(m.name)for m in mm),'nonregular/unsafe tar member')
        return{m.name:(t.extractfile(m).read(),bool(m.mode&0o111))for m in mm}

def logical(raw):
    pos=0
    while pos<len(raw):
        n=16 if raw[pos]==0x18 else 8;need(pos+n<=len(raw),'truncated logical instruction')
        yield pos;pos+=n

def elf(b):
    need(b[:7]==b'\x7fELF\x02\x01\x01' and len(b)>=64,'ELF header')
    off=struct.unpack_from('<Q',b,40)[0];sz,count,ni=struct.unpack_from('<HHH',b,58)
    need(sz==64 and ni<count and off+sz*count<=len(b),'ELF section table')
    hh=[struct.unpack_from('<IIQQQQIIQQ',b,off+i*sz)for i in range(count)]
    def payload(h):
        need(h[4]+h[5]<=len(b),'ELF section extent');return b[h[4]:h[4]+h[5]]
    strings=payload(hh[ni]);ss={}
    for h in hh:
        need(h[0]<len(strings),'ELF name offset');end=strings.find(b'\0',h[0]);need(end>=0,'ELF name end')
        n=strings[h[0]:end].decode();need(n not in ss,'duplicate ELF section');ss[n]=(h,payload(h))
    sy=[]
    if '.symtab'in ss:
        h,d=ss['.symtab'];need(h[9]==24 and len(d)%24==0,'ELF symbol stride');st=payload(hh[h[6]])
        for i in range(0,len(d),24):
            n,info,other,sec,addr,size=struct.unpack_from('<IBBHQQ',d,i);end=st.find(b'\0',n);need(0<=n<len(st)and end>=0,'symbol name')
            sy.append((st[n:end].decode(),info,sec,addr,size))
    return ss,sy

def target(b):
    ss,sy=elf(b);f=[s for s in sy if s[0]==SYMBOL and s[1]&15==2];need(len(f)==1,'unique CTO symbol')
    x=f[0];h,t=ss['.text'];a=x[3]-h[3];z=a+x[4];bounds=set(logical(t));need(a in bounds and(z in bounds or z==len(t)),'CTO logical extent')
    return ss,sy,x,t[a:z]

def provenance(z,commit,corepayload,repo):
    members=z.namelist();need(len(members)==len(set(members))and all(safe(n)for n in members),'ZIP member domain')
    need(z.testzip()is None,'ZIP CRC');g=js(z.read('program-source-inputs.json'));core=js(z.read('toolchain-source-inputs.json'))
    need(g['base']==core['base']==commit and len(g['files'])==141 and len(core['files'])==236,'frozen provenance cohort')
    p=tarbytes(z.read('program-source.tar.gz'));need(set(p)=={x['path']for x in g['files']}and len(p)==141,'source141 domain')
    for x in g['files']:
        b,e=p[x['path']];need(len(b)==x['bytes']and sha(b)==x['sha256']and gitblob(b)==x['gitBlob']and e==(x['mode']=='100755'),'source bytes/mode '+x['path'])
    selected=js(z.read('source-inputs.json'));vector=[{'path':x['path'].removeprefix('programs/pump/'),'bytes':x['bytes'],'executable':x['mode']=='100755','sha256':x['sha256']}for x in g['files']]
    vector.sort(key=lambda x:x['path']);digest=sha(json.dumps(vector,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
    need(selected['files']==vector and selected['sha256']==digest and selected==js(z.read('preflight-builder-source-inputs.json')),'selected source vector')
    stage=js(z.read('compiled-workspace-inputs.json'));s=tarbytes(z.read('compiled-workspace.tar.gz'));need(len(s)==142 and set(s)==set(stage),'stage142 domain')
    for n,(b,e)in s.items():need(stage[n]=={'bytes':len(b),'executable':e,'sha256':sha(b)},'compiled stage bytes '+n)
    for x in core['files']:
        n=x['path'];need(safe(n),'unsafe CORE path');b=corepayload.get('core-source/'+n)
        if b is None:b=(repo/n).read_bytes()
        need(len(b)==x['bytes']and sha(b)==x['sha256']and gitblob(b)==x['gitBlob'],'CORE bytes '+n)
    pre=js(z.read('PREFLIGHT.json'));need(pre['base']==commit and(pre['programGitFiles'],pre['selectedSourceFiles'],pre['workspaceFiles'],pre['coreFiles'])==(141,141,142,236),'preflight counts')
    build=js(z.read('build.json'));need(build['ok']and build['stack_warnings']==[]and build['recipe']=='identity'and build['source_sha256']==digest,'recorded native build')
    for n,k in [('unstripped.so','unstripped_sha256'),('candidate.so','candidate_sha256')]:need(sha(z.read(n))==build[k],'build image binding')
    need(js(z.read('tool-inputs-before.json'))==js(z.read('tool-inputs-after.json')),'tool before/after')
    need(js(z.read('registry-source-inputs.json'))==js(z.read('registry-source-inputs-after.json')),'registry before/after')
    need(js(z.read('native-lld-input-before.json'))==js(z.read('native-lld-input-after.json')),'linker before/after')
    cold=js(z.read('cold-target-inputs.json'));need(cold['base']==commit and cold['sourceSha256']==digest and cold['targetAbsentBeforeBuild']and cold['dependencyTemplatesAbsent'],'cold build receipt')
    return g,core,stage,p,s,build

def graph(raw):
    """Logical instructions and direct intraprocedural CFG; calls return."""
    rows={p:struct.unpack_from('<BBhi',raw,p)for p in logical(raw)};succ={};leaders={0}
    for p,(op,reg,off,imm)in rows.items():
        nxt=p+(16 if op==0x18 else 8);s=[]
        if op==0x95:pass
        elif op&7 in(5,6)and op not in(0x85,0x8d):
            dest=p+8+off*8;need(dest in rows,'branch into noninstruction');s=[dest]
            if op not in(0x05,0x06)and nxt<len(raw):s.append(nxt)
            leaders.add(dest)
        elif nxt<len(raw):s=[nxt]
        if (op==0x95 or(op&7 in(5,6)and op not in(0x85,0x8d)))and nxt<len(raw):leaders.add(nxt)
        succ[p]=set(s)
    pred={p:set()for p in rows}
    for p,ss in succ.items():
        for q in ss:pred[q].add(p)
    starts=sorted(leaders);blocks={};owner={}
    for i,start in enumerate(starts):
        end=starts[i+1]if i+1<len(starts)else len(raw);pcs=[p for p in rows if start<=p<end]
        need(bool(pcs),'empty block');blocks[start]={'start':start,'end':end,'successors':sorted(succ[pcs[-1]]),'predecessors':[]}
        for p in pcs:owner[p]=start
    for start,block in blocks.items():
        block['successors']=sorted({owner[x]for x in block['successors']})
        block['predecessors']=sorted({owner[x]for x in pred[start]})
    return rows,succ,pred,blocks

def defines(row,reg):
    op,rr,off,imm=row
    if op in(0x85,0x8d):return reg<=5
    return (op==0x18 or op&7 in(1,4,7))and rr&15==reg

def reachdefs(rows,pred,reg,at):
    todo=list(pred[at]);seen=set();found=set()
    if at==0:found.add(None)
    while todo:
        p=todo.pop()
        if p in seen:continue
        seen.add(p)
        if defines(rows[p],reg):found.add(p)
        elif p==0:found.add(None)
        else:todo.extend(pred[p])
    return found

def reachable(edges,start):
    seen=set();todo=[start]
    while todo:
        p=todo.pop()
        if p not in seen:seen.add(p);todo.extend(edges[p])
    return seen

def fpwrite(row):
    op,reg,off,imm=row
    return(off,off+{0:4,8:2,16:1,24:8}[op&24])if op&7 in(2,3)and reg&15==10 else None

def exact(raw,expected):
    starts=set(logical(raw))
    for x in expected:
        p=x['offset'];p=int(p,0)if isinstance(p,str)else p;b=bytes.fromhex(x['raw'])
        need(p in starts and len(b)==(16 if raw[p]==0x18 else 8)and raw[p:p+len(b)]==b,'actual ELF raw witness '+hex(p))

def machine(images,w,original):
    outputs={};gg={}
    for key in('S1','S2'):
        spec=w['variants'][key];ss,sy,sym,raw=target(images[key]);need(sym[3]==141840 and sym[4]==spec['body']['bytes']and sha(raw)==spec['bodySha256'],'CTO body '+key)
        exact(raw,spec['instructions']);rows,succ,pred,blocks=graph(raw);gg[key]=(raw,rows,succ,pred)
        for expected in spec['expectedBlocks']:
            actual=blocks[expected['start']];need(actual['end']==expected['end']and set(actual['successors'])==set(expected['successors'])and set(actual['predecessors'])==set(expected['predecessors']),'actual common/selection block '+key)
        sweep=[s for s in sy if s[0]==spec['sweep']['name']and s[1]&15==2];need(len(sweep)==1 and sweep[0][3:]==(spec['sweep']['address'],9096),'outlined sweep symbol '+key)
        call=spec['sweepCall'];p=call['offset'];op,rr,off,imm=rows[p];need(op==0x85 and rr==0x10 and sym[3]+p+8+imm*8==sweep[0][3]and sym[3]+sym[4]==sweep[0][3],'actual sweep call '+key)
        outputs[key]={'CTOBytes':len(raw),'logicalInstructions':len(rows),'sweepBytes':9096,'commonSharedHeadInstructions':3}
    raw,r,succ,pred=gg['S1'];need(all(not defines(row,8)for p,row in r.items()if 0x198<p<0x3c0),'S1 shared R8 retained through delayed spill')
    need([p for p,v in r.items()if p<0xae0 and v[0]==0x79 and v[1]>>4==10 and v[2]==-1976]==[0xad0],'S1 first direct fee read after projection')
    need(len([p for p in r if 0x1270<=p<0x1288])==3,'S1 common head has three instructions')
    raw,r,succ,pred=gg['S2'];need([p for p,v in r.items()if p<0x1598 and v[0]==0x79 and v[1]>>4==10 and v[2]==-1984]==[0xb28],'S2 one bounded validation fee-tag read')
    need(reachdefs(r,pred,7,0xe50)=={0x268},'S2 creator prefix curve pointer')
    nodes=reachable(succ,0xb10)&reachable(pred,0x1568)
    ranges=[(-1432,-1425),(-1136,-1127),(-1912,-1904)]
    need(all(not any(a<hi and lo<b for lo,hi in ranges)for p in nodes if (ab:=fpwrite(r[p]))is not None for a,b in[ab]),'S2 selected direct frame ranges preserved')
    need(reachdefs(r,pred,3,0x1560)=={0x1378,0x1420,0x1468}and reachdefs(r,pred,0,0x1558)=={0xa78,0xea0,0x1410,0x1bb8}and reachdefs(r,pred,6,0x1410)=={0x1390},'S2 middle-word bounded register bridges')
    c=w['S2consumers'];exact(raw,c['final_pack']['instructions']);curve=c['curve_consumer'];exact(raw,[curve['curve_pointer_load']]+[x for pair in curve['pairs']for x in pair.values()])
    stores=[p for p,v in r.items()if (ab:=fpwrite(v))is not None and ab[0]<-1184 and -1216<ab[1]];need(stores==[0x1520,0x1530,0x1540,0x1550,0x1558,0x1560],'S2 whole-CTO direct target-store census')
    need(0x1fd8 not in reachable({p:{q for q in ss if q!=0x1520}for p,ss in succ.items()},0),'S2 pack store dominates curve read in direct CFG')
    need(all(reachdefs(r,pred,1,int(pair['curve_store']['offset'],0))=={0x1f90}for pair in curve['pairs']),'S2 curve-pointer register bridge')
    need(all(pred[int(pair['curve_store']['offset'],0)]=={int(pair['target_load']['offset'],0)}for pair in curve['pairs']),'S2 immediate curve load/store edges')
    pool=c['pool_consumer'];exact(raw,pool['target_argument']+[pool['call']]);need(pred[0x2dc0]=={0x2db8}and reachdefs(r,pred,3,0x2dd8)=={0x2dc0},'S2 pool target argument retained')
    ss,sy,_,_=target(images['S2']);found=[s for s in sy if 'cpi14admin_cto_pool17h'in s[0]and s[1]&15==2];need(len(found)==1 and found[0][3:]==(0x10a008,4056),'S2 pool helper symbol')
    p=0x2dd8;need(141840+p+8+r[p][3]*8==found[0][3],'S2 actual pool call target');h,t=ss['.text'];a=found[0][3]-h[3];helper=t[a:a+4056];exact(helper,[x for pair in pool['serialized_target_words']for x in pair.values()]);hr,hs,hp,hb=graph(helper)
    need(all(reachdefs(hr,hp,3,int(pair['target_read']['offset'],0))=={None}for pair in pool['serialized_target_words']),'S2 helper entry creator pointer reaches four reads')
    need(all(hp[int(pair['payload_store']['offset'],0)]=={int(pair['target_read']['offset'],0)}for pair in pool['serialized_target_words']),'S2 immediate pool read/store edges')
    os,_=elf(original);h,t=os['.text'];o=t[141840-h[3]:169240-h[3]]
    for x in w['originalOrder']['witnesses']:
        p=int(x['relative'],16);need(o[p:p+len(bytes.fromhex(x['raw']))].hex()==x['raw'],'original order witness')
    outputs['S1']['projectionBeforeFee']=True;outputs['S2'].update(preselectionBeforeFee=True,validationFeeTagReads=1,targetDirectStores=6,curveAndPoolConsumerJoins=True)
    return outputs

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--repo',type=Path);args=ap.parse_args();here=Path(__file__).resolve().parent
    repo=args.repo.resolve()if args.repo else next((q for q in here.parents if(q/'evidence/original/pump/deployed.so').is_file()),None);need(repo is not None,'provide --repo with checked-in original and pinned binary CORE inputs')
    m=js((here/'inputs.json').read_bytes());need(m['commits']==COMMITS,'source cohort');archive=(here/m['archive']['path']).read_bytes();need(sha(archive)==m['archive']['sha256']and len(archive)==m['archive']['bytes'],'sealed archive')
    packed=tarbytes(archive);need(set(packed)==set(m['archive']['members']),'outer archive domain');data={n:b for n,(b,e)in packed.items()}
    for n,b in data.items():need(m['archive']['members'][n]=={'bytes':len(b),'sha256':sha(b)},'outer member '+n)
    original=(repo/'evidence/original/pump/deployed.so').read_bytes();need(sha(original)==ORIGINAL,'checked-in original image')
    wraw=(here/'witnesses.json').read_bytes();need(m['witnesses']=={'bytes':len(wraw),'sha256':sha(wraw)},'witness identity');w=js(wraw)
    z={};prov={};images={};score={}
    for key,commit in COMMITS.items():
        raw=data['raw/'+key+'.zip'];count=43 if key=='ECEA'else 45;need(sha(raw)==ZIP_SHA[key]and m['rawArchives'][key]=={'member':'raw/'+key+'.zip','sha256':sha(raw),'members':count},'raw ZIP identity '+key)
        z[key]=zipfile.ZipFile(io.BytesIO(raw));need(len(z[key].namelist())==count,'raw ZIP census');prov[key]=provenance(z[key],commit,data,repo)
        images[key]=z[key].read('unstripped.so');need(sha(images[key])==ELF_SHA[key],'unstripped identity '+key);score[key]=js(z[key].read('score.json'))
        c=data['git/'+key+'.commit'];need(hashlib.sha1(b'commit '+str(len(c)).encode()+b'\0'+c).hexdigest()==commit,'source commit object '+key)
        if key!='ECEA':need([x[7:]for x in c.decode().splitlines()if x.startswith('parent ')]==[COMMITS['ECEA']],'candidate sole ECEA parent')
        root=js(data['receipts/'+key+'-root-admission.json']);need(root['base']==commit and root['images']['unstripped.so']==ELF_SHA[key]and root['images']['candidate.so']==prov[key][5]['candidate_sha256']and root['sourceAndArchiveAdmission']=='PASS'and root['independentOfficialScorer']=='PASS','retained root admission binding')
    need(all(prov[k][1]['files']==prov['ECEA'][1]['files']for k in COMMITS),'same CORE236')
    cp={n.removeprefix('core-source/')for n in data if n.startswith('core-source/')};allcore={x['path']for x in prov['ECEA'][1]['files']};need(cp==set(m['coreArchivedPaths'])and allcore-cp==set(m['coreExternalBinaryPaths']),'CORE storage domain')
    source={k:prov[k][3][LEAF][0]for k in COMMITS};need([sha(source[k])for k in COMMITS]==['6acfd4b38634ab18c877d7868e9a54bb167c17f465334dfa24996b78910c93b3','7bd0a55d1f9205ccbe45e5bfea4f02556d020674b0e1d8faae41bae04a9cc778','655abec1538697c255f3c1841c3827159b3d92094afe13aa961bcd3f40910689'],'exact CTO source leaves')
    lines={k:b.decode().splitlines(True)for k,b in source.items()};need(all(len(x)==772 for x in lines.values()),'772 source coordinates')
    errors=lambda ls:[(i+1,m.group(1))for i,x in enumerate(ls)for m in re.finditer(r'error!\(PumpError::([A-Za-z0-9_]+)\)',x)]
    need(errors(lines['ECEA'])==errors(lines['S1'])==errors(lines['S2']),'error macro coordinates')
    for old,new,name in [('ECEA','S1','ECEA-to-S1.patch'),('S1','S2','S1-to-S2.patch')]:
        a,b=prov[old][2],prov[new][2];need(set(a)==set(b)and[n for n in a if a[n]!=b[n]]==[LEAF],'sole staged source delta')
        patch=''.join(difflib.unified_diff(lines[old],lines[new],fromfile='a/'+LEAF,tofile='b/'+LEAF)).encode();need(patch==(here/name).read_bytes()and m['patches'][name]=={'bytes':len(patch),'sha256':sha(patch)},'exact source content patch')
    a,b,c=lines['ECEA'],lines['S1'],lines['S2'];need([i+1 for i,(x,y)in enumerate(zip(a,b))if x!=y]==[314,315,334,338,339]and[i+1 for i,(x,y)in enumerate(zip(b,c))if x!=y]==[315,339],'bounded source deltas')
    need(a[:313]==b[:313]==c[:313]and b[313]==' Ok(target)}\n','creator helper signature/checks retained')
    marker='let (collect_old,sharing_update,skip)=';head,tail=a[338].split(marker,1);need(b[314]==head.removeprefix(' Ok(target)}')+'\n'and b[338]==marker+tail,'S1 Result split and late override')
    need(c[314]==b[314].removesuffix('\n')+'if shared&&!holder{target=st.creator;}\n'and c[338]==b[338].replace('target=a.bonding_curve.creator;',''),'S2 early selection only')
    oldcast='holder_key as *const Pubkey as *const u8';newcast='&holder_key as *const Pubkey as *const u8'
    need(all(b[n-1].replace(newcast,oldcast)==a[n-1]and c[n-1]==b[n-1]for n in range(326,339)),'fee guards and both volatile reads preserved')
    need([i+1 for i,x in enumerate(c)if 'read_volatile'in x]==[334,338]and a[339:]==b[339:]==c[339:],'volatile coordinates and downstream tail')
    base=score['ECEA']['windows'];need(len(base)==1035 and(sum(x['normalized']for x in base.values()),sum(x['raw']for x in base.values()))==(1034,1034),'saved control totals')
    need('RESULT.json'in z['ECEA'].namelist()and'FAILURE.json'not in z['ECEA'].namelist(),'control receipt')
    negatives={}
    for key in('S1','S2'):
        ref=js(z[key].read('reference-admission.json'));need(ref['base']==COMMITS['ECEA']and ref['run']==41166161483 and ref['artifactId']==13029328269 and ref['originalZipSha256']==ZIP_SHA['ECEA']and ref['coreEqual'],'exact native reference')
        need(set(ref['files'])==set(z['ECEA'].namelist()),'reference43 domain')
        for n,e in ref['files'].items():
            b=z['ECEA'].read(n);need(e=={'bytes':len(b),'sha256':sha(b)},'reference member '+n)
        ww=score[key]['windows'];need(set(ww)==set(base)and all(base[n]['normalized']==ww[n]['normalized']for n in base),'saved normalized equality')
        losses=[n for n in base if base[n]['raw']and not ww[n]['raw']];need(len(losses)==687 and(sum(x['normalized']for x in ww.values()),sum(x['raw']for x in ww.values()))==(1034,347),'saved rejection arithmetic')
        summary=score[key]['summary'];need(sorted(summary['raw_losses'],key=lambda n:int(n,0))==[hex(n)for n in sorted(map(int,losses))],'saved loss declaration')
        changed={n:{'reference':base[n],'candidate':ww[n]}for n in base if base[n]!=ww[n]};cmp=js(z[key].read('CANDIDATE-COMPARISON.json'));need(cmp['changedRows']==changed and cmp['noNormalizedLosses']and not cmp['noRawLosses'],'saved rejecting comparison')
        fail=js(z[key].read('FAILURE.json'));need(fail['base']==COMMITS[key]and fail['type']=='ValueError'and'raw or normalized losses'in fail['message']and'RESULT.json'not in z[key].namelist(),'original native failure retained')
        negatives[key]={'nativeConclusion':'FAIL/no-loss guard','normalized':1034,'raw':347,'rawLosses':687,'buildSeconds':prov[key][5]['seconds']}
    for key in COMMITS:
        ww=score[key]['windows'];summary=score[key]['summary'];need(summary['candidate_sha256']==ELF_SHA[key]and summary['total']==len(ww)and summary['normalized']==sum(x['normalized']for x in ww.values())and summary['raw']==sum(x['raw']for x in ww.values()),'saved summary recomputation')
    findings=data['prior/FINDINGS.json'];need(sha(findings)=='261968890255a52b0cb1887fe039c0afd8940abeb0290a75268e86be22bfcf74','corrected exact prior receipt')
    for x in js(findings)['authenticated_retained_files']:
        b=data['prior/'+x['retained_text']];need(len(b)==x['bytes']and sha(b)==x['sha256']and gitblob(b)==x['git_blob'],'retained prior script/text')
    need(data['analysis/unqualified/S1-ABI.json']==b''and all(n in data for n in m['unqualified']),'empty/failed ABI evidence retained and unqualified')
    result={'status':'PASS_HISTORICAL_S1_S2_NEGATIVES_PRESERVED','commits':COMMITS,'sourceFiles':141,'stageFiles':142,'COREFiles':236,'negativeMeasurements':negatives,'machine':machine(images,w,original),'prior3384':'Exact execute-side fee-helper negative credited; reported old-base result, not replayed.','limits':'Recorded score arithmetic and selected actual raw/CFG/direct-frame/register/consumer joins only. Normally returning calls and private-buffer nonalias assumption. No compile, IR, VM, official scorer, Rust lifetime/type/whole-ABI equivalence, exterior-address-only theorem, latest-main executable qualification, source gain or followup source authorization.'}
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

