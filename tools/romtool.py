import struct,sys,hashlib,os
X=bytes.fromhex('75A467AFD195CF5A7B871B33C147EBD6BEA73A03CEBCF02A749066B36B3E09CC')
A=bytes.fromhex('82180D326A92124E80172CE9A2F2222577AB49DFD5C70693699BF6415F615935')
def c3(b): return bytes(((c-A[i%32])^X[i%32])&0xff for i,c in enumerate(b))
def hdr(d,off=0):
    h=d[off:off+0x80]
    hs,crc,ct,uf,fmt,flags,length=struct.unpack('>IIBBHII',h[4:0x18])
    verify,blocks,dev=struct.unpack('>III',h[0x18:0x24])
    name=h[0x24:0x34].split(b'\0')[0].decode('latin1')
    ver=h[0x44:0x54].split(b'\0')[0].decode('latin1')
    return dict(hs=hs,crc=crc,ct=ct,fmt=fmt,flags=flags,length=length,verify=verify,blocks=blocks,dev=dev,name=name,ver=ver)
def blocks(d):
    off=0x80; out=[]
    for i in range(16):
        h=c3(d[off:off+0x80])
        if h[:4]!=bytes.fromhex('EB9F56C9'): break
        hs,crc,ct,uf,fmt,flags,length=struct.unpack('>IIBBHII',h[4:0x18])
        total,verify=struct.unpack('>II',h[0x18:0x20])
        btype,bid=struct.unpack('>II',h[0x20:0x28])
        name=h[0x28:0x38].split(b'\0')[0].decode('latin1')
        cipher=struct.unpack('>I',h[0x50:0x54])[0]
        out.append(dict(off=off,total=total,length=length,type=btype,name=name,cipher=cipher))
        off+=total
    return out,off
def extract_body(d,b):
    return c3(d[b['off']+0x80:b['off']+0x80+b['length']])
if __name__=='__main__':
    for p in sys.argv[1:]:
        d=open(p,'rb').read(); H=hdr(d); bl,end=blocks(d)
        print('==',os.path.basename(p),'size',len(d),'ver',H['ver'],'crypto',hex(H['ct']),'len',hex(H['length']),'tail',len(d)-0x80-H['length'])
        for b in bl: print('   ',b['name'],'off',hex(b['off']),'total',hex(b['total']),'len',hex(b['length']),'type',b['type'],'cipher',b['cipher'])
        v=extract_body(d,bl[0])
        out=p+'.version.elf'; open(out,'wb').write(v)
        print('    version elf',len(v),v[:4].hex(),hashlib.sha256(v).hexdigest()[:16])
