from Crypto.Cipher import AES
from Crypto.Util import _counter as counter

ARC_KEY = bytes.fromhex('C53DB23870A1A2F71CAE64061FDD0E1157309DC85204D4C5BFDF25090DF2572C')
ARC_IV = bytes.fromhex('E915AA018FEF71FC508132E4BB4CEB42')

MAC_KEY = bytes.fromhex('9821330E34B91F70D0A48CBD625993126970CEA09192C0E6CDA676CC9838289D')
WIN_KEY = bytes.fromhex('CB648DF3D12A16BF71701414E69619EC171CCA5D2A142E3E59DE7ADDA18A3A30')

PRF_KEY = bytes.fromhex('728B369E24ED0134768511021812AFC0A3C25D02065F166B4BCC58CD2644F29E')
CONFIG_KEY = bytes.fromhex('378B9026EE7DE70B8AF124C1E30978670F9EC8FD5E7285A86442DD73068C0473')

def pad(data, blocksize=16):
    return data + bytes(blocksize - len(data) % blocksize)

def aes_bom():
    return AES.new(ARC_KEY, IV=ARC_IV, mode=AES.MODE_CFB, segment_size=128)

def aes_sng(key, ivector):
    ctr = counter._newBE(b'', b'', ivector, allow_wraparound=False)
    return AES.new(key, mode=AES.MODE_CTR, counter=ctr)
