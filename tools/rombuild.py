import struct,zlib,lzma,sys
from romtool import c3, blocks
X=bytes.fromhex('75A467AFD195CF5A7B871B33C147EBD6BEA73A03CEBCF02A749066B36B3E09CC')
A=bytes.fromhex('82180D326A92124E80172CE9A2F2222577AB49DFD5C70693699BF6415F615935')
def enc(b): return bytes(((c^X[i%32])+A[i%32])&0xff for i,c in enumerate(b))
def dec(b): return c3(b)
def inner_dec(wire,cipher):
    x=dec(wire)                      # outer ROM stream layer
    if cipher==0: return x
    if cipher==1: return lzma.decompress(x)
    if cipher==3: return dec(x)      # own block cipher layer
    raise SystemExit('cipher %d'%cipher)
def inner_enc(plain,cipher):
    if cipher==0: return plain
    if cipher==1:
        f=[{'id':lzma.FILTER_LZMA1,'dict_size':0x40000,'lc':3,'lp':0,'pb':2}]
        out=lzma.compress(plain,format=lzma.FORMAT_ALONE,filters=f)
        return out[:5]+bytes([0xff])*8+out[13:]
    if cipher==3: return enc(plain)
    raise SystemExit('cipher %d'%cipher)
def build(src, replacements=None):
    replacements=replacements or {}
    d=open(src,'rb').read() if isinstance(src,str) else src
    out=bytearray(d[:0x80]); bl,end=blocks(d); total_sum=0
    for b in bl:
        if b['name'] not in replacements:
            out+=d[b['off']:b['off']+b['total']]; total_sum+=b['total']; continue
        h=bytearray(dec(d[b['off']:b['off']+0x80]))
        inner=inner_enc(replacements[b['name']],b['cipher'])
        total=((0x80+len(inner))+31)//32*32
        struct.pack_into('>I',h,0x18,total)
        struct.pack_into('>I',h,0x14,len(inner))
        struct.pack_into('>I',h,0x08,0)
        struct.pack_into('>I',h,0x08,zlib.crc32(bytes(h))&0xffffffff)
        blk=bytes(h)+inner+bytes(total-0x80-len(inner))
        out+=enc(blk); total_sum+=total
    struct.pack_into('>I',out,0x14,total_sum)
    struct.pack_into('>I',out,0x08,0)
    struct.pack_into('>I',out,0x08,zlib.crc32(bytes(out[:0x80]))&0xffffffff)
    return bytes(out)+d[end:]
if __name__=='__main__':
    r=build(sys.argv[1]); d=open(sys.argv[1],'rb').read()
    print('identity:',r==d,len(r))
