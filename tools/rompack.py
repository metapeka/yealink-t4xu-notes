import struct,zlib,hashlib,sys
X=bytes.fromhex('75A467AFD195CF5A7B871B33C147EBD6BEA73A03CEBCF02A749066B36B3E09CC')
A=bytes.fromhex('82180D326A92124E80172CE9A2F2222577AB49DFD5C70693699BF6415F615935')
def c3(b): return bytes(((c-A[i%32])^X[i%32])&0xff for i,c in enumerate(b))
def parse(d):
    rom=d[:0x80]; blocks=[]; off=0x80
    hs,crc,ct,uf,fmt,flags,length=struct.unpack('>IIBBHII',rom[4:0x18])
    verify,n,dev=struct.unpack('>III',rom[0x18:0x24])
    for i in range(n):
        h=c3(d[off:off+0x80])
        total=struct.unpack('>I',h[0x18:0x1C])[0]
        blocks.append((off,total))
        off+=total
    return rom,n,blocks,off
def rebuild(d):
    rom,n,blocks,end=parse(d)
    out=bytearray(rom); out[0x08:0x0C]=b'\0\0\0\0'
    total_len=0
    body=bytearray()
    for off,total in blocks:
        enc=d[off:off+total]        # already cypher3-encrypted stream of this block
        body+=enc; total_len+=total
    struct.pack_into('>I',out,0x14,total_len)
    crc=zlib.crc32(bytes(out))&0xffffffff
    struct.pack_into('>I',out,0x08,crc)
    return bytes(out)+bytes(body)+d[end:]
if __name__=='__main__':
    src,dst=sys.argv[1],sys.argv[2]
    d=open(src,'rb').read()
    r=rebuild(d)
    open(dst,'wb').write(r)
    print('src',len(d),hashlib.sha256(d).hexdigest())
    print('dst',len(r),hashlib.sha256(r).hexdigest())
    print('identical:',r==d)
    if r!=d:
        for i,(a,b) in enumerate(zip(d,r)):
            if a!=b: print('first diff at',hex(i),hex(a),hex(b)); break
