import os
import sys
import time
from tarfile import TarInfo, DIRTYPE
from StringIO import StringIO

# These patches are only required for versions of Plone that use older Pythons
PYTHON_VERSION = sys.version_info[:2]

# TarballExportContext don't write dirs in tarball and we need to fix this

#security.declareProtected( ManagePortal, 'writeDataFile' )
def writeDataFile( self, filename, text, content_type, subdir=None ):

    """ See IExportContext.
    """
    mod_time = time.time()
    if subdir is not None:
        elements = subdir.split('/')
        parents = filter(None, elements)
        while parents:
            dirname = os.path.join(*parents)
            try:
                self._archive.getmember(dirname+'/')
            except KeyError:
                info = TarInfo(dirname)
                info.size = 0
                info.mode = 509
                info.mtime = mod_time
                info.type = DIRTYPE
                self._archive.addfile(info, StringIO())
            parents = parents[:-1]

        filename = '/'.join((subdir, filename))

    stream = StringIO(text)
    info = TarInfo(filename)
    info.size = len(text)
    info.mode = 436
    info.mtime = mod_time
    self._archive.addfile(info, stream)

if PYTHON_VERSION < (2, 6):
    from Products.GenericSetup.context import TarballExportContext
    TarballExportContext.writeDataFile = writeDataFile

from Products.GenericSetup.context import SKIPPED_FILES, SKIPPED_SUFFIXES


def listDirectory(self, path, skip=SKIPPED_FILES,
                  skip_suffixes=SKIPPED_SUFFIXES):

    """ See IImportContext.
    """
    if path is None:  # root is special case:  no leading '/'
        path = ''
    elif path:
        if not self.isDirectory(path):
            return None

        if not path.endswith('/'):
            path = path + '/'

    pfx_len = len(path)

    names = []
    for name in self._archive.getnames():
        if name == path or not name.startswith(path):
            continue
        name = name[pfx_len:]
        if name.count('/') > 1:
            continue
        if '/' in name and not name.endswith('/'):
            continue
        if name in skip:
            continue
        if [s for s in skip_suffixes if name.endswith(s)]:
            continue
        # directories have trailing '/' character and we need to remove it
        name = name.rstrip('/')
        names.append(name)

    return names

if PYTHON_VERSION < (2, 6):
    from Products.GenericSetup.context import TarballImportContext
    TarballImportContext.listDirectory = listDirectory

# patch for this bug in tarfile module - http://bugs.python.org/issue1719898
if PYTHON_VERSION == (2, 4):
    from tarfile import nts, GNUTYPE_SPARSE
    from os.path import normpath

    def frombuf(cls, buf):
        """Construct a TarInfo object from a 512 byte string buffer.
        """
        tarinfo = cls()
        tarinfo.name = nts(buf[0:100])
        tarinfo.mode = int(buf[100:108], 8)
        tarinfo.uid = int(buf[108:116], 8)
        tarinfo.gid = int(buf[116:124], 8)

        # There are two possible codings for the size field we
        # have to discriminate, see comment in tobuf() below.
        if buf[124] != chr(0200):
            tarinfo.size = long(buf[124:136], 8)
        else:
            tarinfo.size = 0L
            for i in range(11):
                tarinfo.size <<= 8
                tarinfo.size += ord(buf[125 + i])

        tarinfo.mtime = long(buf[136:148], 8)
        tarinfo.chksum = int(buf[148:156], 8)
        tarinfo.type = buf[156:157]
        tarinfo.linkname = nts(buf[157:257])
        tarinfo.uname = nts(buf[265:297])
        tarinfo.gname = nts(buf[297:329])
        try:
            tarinfo.devmajor = int(buf[329:337], 8)
            tarinfo.devminor = int(buf[337:345], 8)
        except ValueError:
            tarinfo.devmajor = tarinfo.devmajor = 0
        tarinfo.prefix = buf[345:500]

        # The prefix field is used for filenames > 100 in
        # the POSIX standard.
        # name = prefix + '/' + name
        if tarinfo.type != GNUTYPE_SPARSE:
            tarinfo.name = normpath(os.path.join(nts(tarinfo.prefix), tarinfo.name))

        # Some old tar programs represent a directory as a regular
        # file with a trailing slash.
        if tarinfo.isreg() and tarinfo.name.endswith("/"):
            tarinfo.type = DIRTYPE

        # Directory names should have a '/' at the end.
        if tarinfo.isdir():
            tarinfo.name += "/"
        return tarinfo

    frombuf = classmethod(frombuf)
    TarInfo.frombuf = frombuf
