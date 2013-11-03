from lxml import etree

class BaseCache(object):

    def __init__(self, baseKey=""):
        self.baseKey = baseKey

    def set(self, key, tree):
        """write tree to key"""
        pass

    def get(self, key):
        """load tree from key, or None if cache miss"""
        return None


class DummyCache(BaseCache):
    pass

class TempCache(BaseCache):
    
    def get_tmp(self, key, mode):
        name = self.baseKey+key
        path = "/tmp/{}.xml".format(name)
        try:
            return open(path, mode)
        except IOError:
            return None

    def set(self, key, tree):
        with self.get_tmp(key, 'w+') as tmp:
            tree.write(tmp, encoding='utf-8', pretty_print=False, xml_declaration=True)

    def get(self, key):
        tmp = self.get_tmp(key, 'r')
        if tmp is None:
            return None
        return etree.parse(tmp)