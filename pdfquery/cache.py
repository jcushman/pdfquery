import hashlib
import zipfile
from lxml import etree

class BaseCache(object):

    def __init__(self):
        self.hash_key = None

    def set_hash_key(self, file):
        """Calculate and store hash key for file."""
        filehasher = hashlib.md5()
        while True:
            data = file.read(8192)
            if not data:
                break
            filehasher.update(data)
        file.seek(0)
        self.hash_key = filehasher.hexdigest()

    def set(self, page_range_key, tree):
        """write tree to key"""
        pass

    def get(self, page_range_key):
        """load tree from key, or None if cache miss"""
        return None


class DummyCache(BaseCache):
    pass


class FileCache(BaseCache):

    def __init__(self, directory='/tmp/'):
        self.directory = directory
        super(FileCache, self).__init__()

    def get_cache_filename(self, page_range_key):
        return "pdfquery_{hash_key}{page_range_key}.xml".format(
            hash_key=self.hash_key,
            page_range_key=page_range_key
        )

    def get_cache_file(self, page_range_key, mode):
        try:
            return zipfile.ZipFile(self.directory+self.get_cache_filename(page_range_key)+".zip", mode)
        except IOError:
            return None

    def set(self, page_range_key, tree):
        xml = etree.tostring(tree, encoding='utf-8', pretty_print=False, xml_declaration=True)
        cache_file = self.get_cache_file(page_range_key, 'w')
        cache_file.writestr(self.get_cache_filename(page_range_key), xml)
        cache_file.close()

    def get(self, page_range_key):
        cache_file = self.get_cache_file(page_range_key, 'r')
        if cache_file:
            return etree.fromstring(cache_file.read(self.get_cache_filename(page_range_key)))