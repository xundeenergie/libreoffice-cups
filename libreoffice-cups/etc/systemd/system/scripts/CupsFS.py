#!/usr/bin/python -u
#!/usr/bin/env python

#
# CupsFS.py: a FUSE filesystem for mounting an LDAP directory in Python
# Need python-fuse bindings, and an LDAP server.
# usage: ./CupsFS.py lt;mountpoint&gt;
# unmount with fusermount -u lt;mountpoint&gt;
#
# Source: https://github.com/libfuse/python-fuse/wiki

import stat
import errno
import fuse
import re
import os
from time import time
from subprocess import *

fuse.fuse_python_api = (0, 2)

class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = stat.S_IFDIR | 0755
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 2
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 4096
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

class CupsFS(fuse.Fuse):
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)

        # Get our list of printers available.
#        lpstat = Popen(['LANG=C lpstat -p'], shell=True, stdout=PIPE)
#        output = lpstat.communicate()[0]
#        lines = output.split('\n');
#        lpstat.wait()

        self.printers = {}
        self.files = {}
        self.lastfiles = {}
        self.lf = dict()

#        ex = re.compile('^printer')
#        for line in lines:
#            if not ex.search(line): continue
#            self.printers[line.split(' ')[1]] = []
        self.readprinters()

    def readprinters(self):
        plisttmp = set()
        lpstat = Popen(['LANG=C lpstat -p'], shell=True, stdout=PIPE)
        output = lpstat.communicate()[0]
        lines = output.split('\n');
        lpstat.wait()
        ex = re.compile('^printer')
        for line in lines:
            if ex.search(line): 
                word=line.split(' ')[1]
                plisttmp.add(word)
                if word in self.printers: 
                    #print('continue',word)
                    continue
                else:
                    #print('add',word)
                    self.printers[word] = []
            else:
                continue

        # delete not existing printer from list
        pdel = set()
        for pt in self.printers:
            if pt not in plisttmp: pdel.add(pt)
        for p in pdel: 
            #print('delete',p)
            del self.printers[p]
        

    def getattr(self, path):
        st = MyStat()
        pe = path.split('/')[1:]

        st.st_atime = int(time())
        st.st_mtime = st.st_atime
        st.st_ctime = st.st_atime
        #print('getattrP',self.lf,pe[0],pe[-1])
        if path == '/':
            #print('is root')
            pass
        elif self.printers.has_key(pe[-1]):
            #print('is printer')
            pass
        elif self.lastfiles.has_key(pe[-1]):
            st.st_mode = stat.S_IFREG | 0666
            st.st_nlink = 1
            st.st_size = len(self.lastfiles[pe[-1]])
        elif self.lf.has_key(pe[0]):
            if self.lf[pe[0]].has_key(pe[-1]):
                #print('is file',pe[-1])
                st.st_mode = stat.S_IFREG | 0666
                st.st_nlink = 1
                st.st_size = len(self.lf[pe[0]][pe[-1]])
            else:
                #print('is empty')
                #st.st_mode = stat.S_IFREG | 0666
                #st.st_nlink = 1
                #st.st_size = len(self.lf[pe[0]][pe[-1]])
                return -errno.ENOENT
                pass
        else:
            #print('error no entry')
            return -errno.ENOENT
        return st

    def readdir(self, path, offset):
        dirents = [ '.', '..' ]
        #print('PATH',path,path[1:])
        if path == '/':
            self.readprinters()
            dirents.extend(self.printers.keys())
        else:
            pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
            if len(pe) < 2: 
                dirents.extend(self.printers[pe[-1]])
            else:
                dirents.extend(self.printers[pe[-1]])
                #print('DEADBEEF',path)
        for r in dirents:
            yield fuse.Direntry(r)

    def mknod(self, path, mode, dev):
        #print('mknodP',path,os.path.isdir(path))
        pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
        self.printers[pe[0]].append(pe[1])
        self.files[pe[1]] = ""
        #self.lastfiles[pe[1]] = ""
        self.lf[pe[0]] = dict()
        self.lf[pe[0]][pe[1]] = ""
        return 0

    def unlink(self, path):
        #print('UNLINK',path)
        pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
        self.printers[pe[0]].remove(pe[-1])
        del(self.files[pe[1]])
        #del(self.lastfiles[pe[1]])
        del(self.lf[pe[0]][pe[-1]])
        return 0

    def read(self, path, size, offset):
        #print('readP',path,os.path.isdir(path))
        pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
        #return self.lastfiles[pe[1]][offset:offset+size]
        #print('Y',self.lf[pe[0]][pe[1]][offset:offset+size])
        return self.lf[pe[0]][pe[1]][offset:offset+size]

    def write(self, path, buf, offset):
        #print('writeP',path,os.path.isdir(path))
        pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
        self.files[pe[-1]] += buf
        return len(buf)

    def release(self, path, flags):
        pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
        if len(self.files[pe[-1]]) > 0:
            cmd = ['lpr -P %s -T "%s"' % (pe[0],pe[1])]
            lpr = Popen(cmd, shell=True, stdin=PIPE)
            lpr.communicate(input=self.files[pe[1]])
            lpr.wait()
            #self.lastfiles[pe[1]] = self.files[pe[1]]
            self.lf[pe[0]][pe[1]] = self.files[pe[1]]
            self.files[pe[1]] = ""      # Clear out string
        return 0

    def open(self, path, flags):
        return 0

    def truncate(self, path, size):
        return 0

    def utime(self, path, times):
        return 0

    def mkdir(self, path, mode):
        return 0

    def rmdir(self, path):
        return 0

    def rename(self, pathfrom, pathto):
        return 0

    def fsync(self, path, isfsyncfile):
        return 0

def main():
    usage="""
        CupsFS: A filesystem to allow printing for applications that can
                only print to file.
    """ + fuse.Fuse.fusage

    server = CupsFS(version="%prog " + fuse.__version__,
                    usage=usage, dash_s_do='setsingle')
    server.parse(errex=1)
    server.main()

if __name__ == '__main__':
       main()
