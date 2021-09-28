# media_bundler/versioning.py

"""
Module for versioning bundles.

Ideas and code credited to the Andreas Pelme and other authors of the
django-compress project:
http://code.google.com/p/django-compress/

This is a rewrite of their original code to not rely on reading the version
information from a directory listing and work with the rest of
django-media-bundler.
"""

from __future__ import with_statement

from hashlib import md5, sha1
import os
import shutil

from media_bundler.conf import bundler_settings


_bundle_versions = None

def get_bundle_versions():
    global _bundle_versions
    if not bundler_settings.BUNDLE_VERSION_FILE:
        _bundle_versions = {}  # Should this be None?
    if _bundle_versions is None:
        update_versions()
    return _bundle_versions


def update_versions():
    """Executes the bundle versions file and updates the cache."""
    global _bundle_versions
    vars = {}
    try:
        execfile(bundler_settings.BUNDLE_VERSION_FILE, vars)
    except IOError:
        _bundle_versions = {}
    else:
        _bundle_versions = vars['BUNDLE_VERSIONS']


def write_versions(versions):
    global _bundle_versions
    _bundle_versions = _bundle_versions.copy()
    _bundle_versions.update(versions)
    with open(bundler_settings.BUNDLE_VERSION_FILE, 'w') as output:
        versions_str = '\n'.join('    %r: %r,' % (name, vers)
                                 for (name, vers) in versions.items())
        output.write('''\
#!/usr/bin/env python

"""
Media bundle versions.

DO NOT EDIT!  Module generated by 'manage.py bundle_media'.
"""

BUNDLE_VERSIONS = {
%s
}
''' % versions_str)


class VersioningError(Exception):

    """This exception is raised when version creation fails."""


class VersioningBase(object):

    def __init__(self):
        self.versions = get_bundle_versions().copy()

    def get_version(self, source_files):
        raise NotImplementedError

    def update_bundle_version(self, bundle):
        version = self.get_version(bundle)
        orig_path = bundle.get_bundle_path()
        dir, basename = os.path.split(orig_path)
        if '.' in basename:
            name, _, extension = basename.rpartition('.')
            versioned_basename = '.'.join((name, version, extension))
        else:
            versioned_basename += '.' + version
        self.versions[bundle.name] = versioned_basename
        versioned_path = os.path.join(dir, versioned_basename)
        shutil.copy(orig_path, versioned_path)


class MtimeVersioning(VersioningBase):

    def get_version(self, bundle):
        """Return the modification time for the newest source file."""
        return str(max(int(os.stat(f).st_mtime) for f in bundle.get_paths()))


class HashVersioningBase(VersioningBase):

    def __init__(self, hash_method):
        super(HashVersioningBase, self).__init__()
        self.hash_method = hash_method

    def get_version(self, bundle):
        buf = open(bundle.get_bundle_path())
        return self.get_hash(buf)

    def get_hash(self, f, chunk_size=2**14):
        """Compute the hash of a file."""
        m = self.hash_method()
        while 1:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            m.update(chunk)
        return m.hexdigest()


class Md5Versioning(HashVersioningBase):

    def __init__(self):
        super(Md5Versioning, self).__init__(md5)


class Sha1Versioning(HashVersioningBase):

    def __init__(self):
        super(Sha1Versioning, self).__init__(sha1)


VERSIONERS = {
    'sha1': Sha1Versioning,
    'md5': Md5Versioning,
    'mtime': MtimeVersioning,
}
