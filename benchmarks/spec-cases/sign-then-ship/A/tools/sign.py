import hashlib; open('.sig','w').write(hashlib.sha256(b'release-key').hexdigest()[:16]); print('signed')
