import sys
for l in open(sys.argv[1]):
    l=l.rstrip('\n')
    if not l.strip(): continue
    a,rest=l.split(None,1)
    print('%05x %s'%(int(a,16)-0x22a10,rest))
