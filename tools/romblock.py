import struct,zlib,lzma,sys
from romtool import c3, hdr, blocks
X=bytes.fromhex('75A467AFD195CF5A7B871B33C147EBD6BEA73A03CEBCF02A749066B36B3E09CC')
A=bytes.fromhex('82180D326A92124E80172CE9A2F2222577AB49DFD5C70693699BF6415F615935')
def c3_enc(b): return bytes(((c^X[i%32])+A[i%32])&0xff for i,c in enumerate(b))
TYPES={0:'none',1:'lzma',3:'cypher3'}
def decode_body(d,b):
    w=d[b['off']+0x80:b['off']+0x80+b['length']]
    outer=c3(w)                      # outer ROM stream layer
    c=b['cipher']
    if c==0: return outer
    if c==1: return lzma.decompress(outer)
    if c==3: return c3(outer)
    raise SystemExit('unsupported cipher %d'%c)
def encode_body(plain,b,lc=3,lp=0,pb=2,dict_size=0x40000):
    c=b['cipher']
    if c==0: inner=plain
    elif c==1:
        f=[{'id':lzma.FILTER_LZMA1,'dict_size':dict_size,'lc':lc,'lp':lp,'pb':pb}]
        inner=lzma.compress(plain,format=lzma.FORMAT_ALONE,filters=f)
    elif c==3: inner=c3_enc(plain)
    else: raise SystemExit('unsupported cipher %d'%c)
    return c3_enc(inner)             # outer layer
if __name__=='__main__':
    d=open(sys.argv[1],'rb').read()
    for b in blocks(d)[0]:
        plain=decode_body(d,b)
        wire=d[b['off']+0x80:b['off']+0x80+b['length']]
        enc=encode_body(plain,b)
        print('%-10s cipher=%d plain=%-9d wire=%-9d re-encode identical=%s'%(
            b['name'],b['cipher'],len(plain),len(wire),enc==wire))
        if enc!=wire:
            print('   first diff at',next(i for i,(x,y) in enumerate(zip(enc,wire)) if x!=y), 'len diff',len(enc)-len(wire))
