from __future__ import print_function
# -*- coding: utf-8 -*-

# builtins
import codecs
import json
import numbers
import re
import chardet
try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = dict  # sorry py2.6! Ordering isn't that important for our purposes anyway.

# pdfminer
from pdfminer.psparser import PSLiteral
from pdfminer.pdfparser import PDFParser
try:
    # pdfminer < 20131022
    from pdfminer.pdfparser import PDFDocument, PDFPage
except ImportError:
    # pdfminer >= 20131022
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LAParams, LTChar, LTImage, LTPage
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdftypes import resolve1

# other dependencies
from pyquery import PyQuery
from lxml import etree
import cssselect
import six
from six.moves import map
from six.moves import zip

# local imports
from .pdftranslator import PDFQueryTranslator
from .cache import DummyCache


# Re-sort the PDFMiner Layout tree so elements that fit inside other elements
# will be children of them
def _append_sorted(root, el, comparator):
    """ Add el as a child of root, or as a child of one of root's children.
    Comparator is a function(a, b) returning > 0 if a is a child of b, < 0 if
    b is a child of a, 0 if neither.
    """
    for child in root:
        rel = comparator(el, child)
        if rel > 0:
            # el fits inside child, add to child and return
            _append_sorted(child, el, comparator)
            return
        if rel < 0:
            # child fits inside el, move child into el (may move more than one)
            _append_sorted(el, child, comparator)
    # we weren't added to a child, so add to root
    root.append(el)


def _box_in_box(el, child):
    """ Return True if child is contained within el. """
    return all([
        float(el.get('x0')) <= float(child.get('x0')),
        float(el.get('x1')) >= float(child.get('x1')),
        float(el.get('y0')) <= float(child.get('y0')),
        float(el.get('y1')) >= float(child.get('y1')),
    ])


_comp_bbox_keys_required = set(['x0', 'x1', 'y0', 'y1'])
def _comp_bbox(el, el2):
    """ Return 1 if el in el2, -1 if el2 in el, else 0"""
    # only compare if both elements have x/y coordinates
    if _comp_bbox_keys_required <= set(el.keys()) and \
            _comp_bbox_keys_required <= set(el2.keys()):
        if _box_in_box(el2, el):
            return 1
        if _box_in_box(el, el2):
            return -1
    return 0


# assorted helpers
def _flatten(l, ltypes=(list, tuple)):
    # via http://rightfootin.blogspot.com/2006/09/more-on-python-flatten.html
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return ltype(l)

# these might have to be removed from the start of a decoded string after
# conversion
bom_headers = set([
    six.text_type(codecs.BOM_UTF8, 'utf8'),
    six.text_type(codecs.BOM_UTF16_LE, 'utf-16LE'),
    six.text_type(codecs.BOM_UTF16_BE, 'utf-16BE'),
    six.text_type(codecs.BOM_UTF32_LE, 'utf-32LE'),
    six.text_type(codecs.BOM_UTF32_BE, 'utf-32BE'),
])


def smart_unicode_decode(encoded_string):
    """
        Given an encoded string of unknown format, detect the format with
        chardet and return the unicode version.
        Example input from bug #11:
         ('\xfe\xff\x00I\x00n\x00s\x00p\x00e\x00c\x00t\x00i\x00o\x00n\x00'
          '\x00R\x00e\x00p\x00o\x00r\x00t\x00 \x00v\x002\x00.\x002')
    """
    if not encoded_string:
        return u''

    # optimization -- first try ascii
    try:
        return encoded_string.decode('ascii')
    except UnicodeDecodeError:
        pass

    # detect encoding
    detected_encoding = chardet.detect(encoded_string)
    decoded_string = six.text_type(
        encoded_string,
        encoding=detected_encoding['encoding'] or 'utf8',
        errors='replace'
    )

    # unicode string may still have useless BOM character at the beginning
    if decoded_string and decoded_string[0] in bom_headers:
        decoded_string = decoded_string[1:]

    return decoded_string

def prepare_for_json_encoding(obj):
    """
    Convert an arbitrary object into just JSON data types (list, dict, unicode str, int, bool, null).
    """
    obj_type = type(obj)
    if obj_type == list or obj_type == tuple:
        return [prepare_for_json_encoding(item) for item in obj]
    if obj_type == dict:
        # alphabetizing keys lets us compare attributes for equality across runs
        return OrderedDict(
            (prepare_for_json_encoding(k),
             prepare_for_json_encoding(obj[k])) for k in sorted(obj.keys())
        )
    if obj_type == six.binary_type:
        return smart_unicode_decode(obj)
    if obj_type == bool or obj is None or obj_type == six.text_type or isinstance(obj, numbers.Number):
        return obj
    if obj_type == PSLiteral:
        # special case because pdfminer.six currently adds extra quotes to PSLiteral.__repr__
        return u"/%s" % obj.name
    return six.text_type(obj)

def obj_to_string(obj, top=True):
    """
    Turn an arbitrary object into a unicode string. If complex (dict/list/tuple), will be json-encoded.
    """
    obj = prepare_for_json_encoding(obj)
    if type(obj) == six.text_type:
        return obj
    return json.dumps(obj)


# via http://stackoverflow.com/a/25920392/307769
invalid_xml_chars_re = re.compile(u'[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\u10000-\u10FFFF]+')
def strip_invalid_xml_chars(s):
    return invalid_xml_chars_re.sub('', s)


# custom PDFDocument class
class QPDFDocument(PDFDocument):
    def get_page_number(self, index):
        """
        Given an index, return page label as specified by
        catalog['PageLabels']['Nums']

        In a PDF, page labels are stored as a list of pairs, like
        [starting_index, label_format, starting_index, label_format ...]

        For example:
        [0, {'S': 'D', 'St': 151}, 4, {'S':'R', 'P':'Foo'}]

        So we have to first find the correct label_format based on the closest
        starting_index lower than the requested index, then use the
        label_format to convert the index to a page label.

        Label format meaning:
            /S = [
                    D Decimal arabic numerals
                    R Uppercase roman numerals
                    r Lowercase roman numerals
                    A Uppercase letters (A to Z for the first 26 pages, AA to ZZ
                      for the next 26, and so on)
                    a Lowercase letters (a to z for the first 26 pages, aa to zz
                      for the next 26, and so on)
                ] (if no /S, just use prefix ...)
            /P = text string label
            /St = integer start value
        """

        # get and cache page ranges
        if not hasattr(self, 'page_range_pairs'):
            try:
                page_ranges = resolve1(self.catalog['PageLabels'])['Nums']
                assert len(page_ranges) > 1 and len(page_ranges) % 2 == 0
                self.page_range_pairs = list(
                    reversed(list(zip(page_ranges[::2], page_ranges[1::2]))))
            except:
                self.page_range_pairs = []

        if not self.page_range_pairs:
            return ""

        # find page range containing index
        for starting_index, label_format in self.page_range_pairs:
            if starting_index <= index:
                break  # we found correct label_format
        label_format = resolve1(label_format)

        page_label = ""

        # handle numeric part of label
        if 'S' in label_format:

            # first find number for this page ...
            page_label = index - starting_index
            if 'St' in label_format:  # alternate start value
                page_label += label_format['St']
            else:
                page_label += 1

            # ... then convert to correct format
            num_type = label_format['S'].name

            # roman (upper or lower)
            if num_type.lower() == 'r':
                import roman
                page_label = roman.toRoman(page_label)
                if num_type == 'r':
                    page_label = page_label.lower()

            # letters
            elif num_type.lower() == 'a':
                # a to z for the first 26 pages, aa to zz for the next 26, and
                # so on
                letter = chr(page_label % 26 + 65)
                letter *= page_label / 26 + 1
                if num_type == 'a':
                    letter = letter.lower()
                page_label = letter

            # decimal arabic
            else:  # if num_type == 'D':
                page_label = obj_to_string(page_label)

        # handle string prefix
        if 'P' in label_format:
            page_label = label_format['P']+page_label

        return page_label


# create etree parser using custom Element class

class LayoutElement(etree.ElementBase):
    @property
    def layout(self):
        if not hasattr(self, '_layout'):
            self._layout = None
        return self._layout

    @layout.setter
    def layout(self, value):
        self._layout = value
parser_lookup = etree.ElementDefaultClassLookup(element=LayoutElement)
parser = etree.XMLParser()
parser.set_element_class_lookup(parser_lookup)


# main class
class PDFQuery(object):
    def __init__(
            self,
            file,
            merge_tags=('LTChar', 'LTAnno'),
            round_floats=True,
            round_digits=3,
            input_text_formatter=None,
            normalize_spaces=True,
            resort=True,
            parse_tree_cacher=None,
            laparams={'all_texts':True, 'detect_vertical':True},
    ):
        # store input
        self.merge_tags = merge_tags
        self.round_floats = round_floats
        self.round_digits = round_digits
        self.resort = resort

        # set up input text formatting function, if any
        if input_text_formatter:
            self.input_text_formatter = input_text_formatter
        elif normalize_spaces:
            r = re.compile(r'\s+')
            self.input_text_formatter = lambda s: re.sub(r, ' ', s)
        else:
            self.input_text_formatter = None

        # open doc
        if not hasattr(file, 'read'):
            try:
                file = open(file, 'rb')
            except TypeError:
                raise TypeError("File must be file object or filepath string.")

        parser = PDFParser(file)
        if hasattr(QPDFDocument, 'set_parser'):
            # pdfminer < 20131022
            doc = QPDFDocument()
            parser.set_document(doc)
            doc.set_parser(parser)
        else:
            # pdfminer >= 20131022
            doc = QPDFDocument(parser)
            parser.set_document(doc)
        if hasattr(doc, 'initialize'):
            # as of pdfminer==20140328, "PDFDocument.initialize() method is
            # removed and no longer needed."
            doc.initialize()
        self.doc = doc
        self.parser = parser
        self.tree = None
        self.pq = None
        self.file = file

        if parse_tree_cacher:
            self._parse_tree_cacher = parse_tree_cacher
            self._parse_tree_cacher.set_hash_key(self.file)
        else:
            self._parse_tree_cacher = DummyCache()

        # set up layout parsing
        rsrcmgr = PDFResourceManager()
        if type(laparams) == dict:
            laparams = LAParams(**laparams)
        self.device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        self.interpreter = PDFPageInterpreter(rsrcmgr, self.device)

        # caches
        self._pages = []
        self._pages_iter = None
        self._elements = []

    def load(self, *page_numbers):
        """
        Load etree and pyquery object for entire document, or given page
        numbers (ints or lists). After this is called, objects are
        available at pdf.tree and pdf.pq.

        >>> pdf.load()
        >>> pdf.tree
        <lxml.etree._ElementTree object at ...>
        >>> pdf.pq('LTPage')
        [<LTPage>, <LTPage>]
        >>> pdf.load(1)
        >>> pdf.pq('LTPage')
        [<LTPage>]
        >>> pdf.load(0, 1)
        >>> pdf.pq('LTPage')
        [<LTPage>, <LTPage>]
        """
        self.tree = self.get_tree(*_flatten(page_numbers))
        self.pq = self.get_pyquery(self.tree)

    def extract(self, searches, tree=None, as_dict=True):
        """
            >>> foo = pdf.extract([['pages', 'LTPage']])
            >>> foo
            {'pages': [<LTPage>, <LTPage>]}
            >>> pdf.extract([['bar', ':in_bbox("100,100,400,400")']], foo['pages'][0])
            {'bar': [<LTTextLineHorizontal>, <LTTextBoxHorizontal>,...
        """
        if self.tree is None or self.pq is None:
            self.load()
        if tree is None:
            pq = self.pq
        else:
            pq = PyQuery(tree, css_translator=PDFQueryTranslator())
        results = []
        formatter = None
        parent = pq
        for search in searches:
            if len(search) < 3:
                search = list(search) + [formatter]
            key, search, tmp_formatter = search
            if key == 'with_formatter':
                if isinstance(search, six.string_types):
                    # is a pyquery method name, e.g. 'text'
                    formatter = lambda o, search=search: getattr(o, search)()
                elif hasattr(search, '__call__') or not search:
                    # is a method, or None to end formatting
                    formatter = search
                else:
                    raise TypeError("Formatter should be either a pyquery "
                                    "method name or a callable function.")
            elif key == 'with_parent':
                parent = pq(search) if search else pq
            else:
                try:
                    result = parent("*").filter(search) if \
                        hasattr(search, '__call__') else parent(search)
                except cssselect.SelectorSyntaxError as e:
                    raise cssselect.SelectorSyntaxError(
                        "Error applying selector '%s': %s" % (search, e))
                if tmp_formatter:
                    result = tmp_formatter(result)
                results += result if type(result) == tuple else [[key, result]]
        if as_dict:
            results = dict(results)
        return results

    # tree building stuff
    def get_pyquery(self, tree=None, page_numbers=None):
        """
            Wrap given tree in pyquery and return.
            If no tree supplied, will generate one from given page_numbers, or
            all page numbers.
        """
        if not page_numbers:
            page_numbers = []
        if tree is None:
            if not page_numbers and self.tree is not None:
                tree = self.tree
            else:
                tree = self.get_tree(page_numbers)
        if hasattr(tree, 'getroot'):
            tree = tree.getroot()
        return PyQuery(tree, css_translator=PDFQueryTranslator())

    def get_tree(self, *page_numbers):
        """
            Return lxml.etree.ElementTree for entire document, or page numbers
            given if any.
        """
        cache_key = "_".join(map(str, _flatten(page_numbers)))
        tree = self._parse_tree_cacher.get(cache_key)
        if tree is None:
            # set up root
            root = parser.makeelement("pdfxml")
            if self.doc.info:
                for k, v in list(self.doc.info[0].items()):
                    k = obj_to_string(k)
                    v = obj_to_string(resolve1(v))
                    try:
                        root.set(k, v)
                    except ValueError as e:
                        # Sometimes keys have a character in them, like ':',
                        # that isn't allowed in XML attribute names.
                        # If that happens we just replace non-word characters
                        # with '_'.
                        if "Invalid attribute name" in e.args[0]:
                            k = re.sub('\W', '_', k)
                            root.set(k, v)

            # Parse pages and append to root.
            # If nothing was passed in for page_numbers, we do this for all
            # pages, but if None was explicitly passed in, we skip it.
            if not(len(page_numbers) == 1 and page_numbers[0] is None):
                if page_numbers:
                    pages = [[n, self.get_layout(self.get_page(n))] for n in
                             _flatten(page_numbers)]
                else:
                    pages = enumerate(self.get_layouts())
                for n, page in pages:
                    page = self._xmlize(page)
                    page.set('page_index', obj_to_string(n))
                    page.set('page_label', self.doc.get_page_number(n))
                    root.append(page)
                self._clean_text(root)

            # wrap root in ElementTree
            tree = etree.ElementTree(root)
            self._parse_tree_cacher.set(cache_key, tree)

        return tree

    def _clean_text(self, branch):
        """
            Remove text from node if same text exists in its children.
            Apply string formatter if set.
        """
        if branch.text and self.input_text_formatter:
            branch.text = self.input_text_formatter(branch.text)
        try:
            for child in branch:
                self._clean_text(child)
                if branch.text and branch.text.find(child.text) >= 0:
                    branch.text = branch.text.replace(child.text, '', 1)
        except TypeError:  # not an iterable node
            pass

    def _xmlize(self, node, root=None):
        if isinstance(node, LayoutElement):
            # Already an XML element we can use
            branch = node
        else:
            # collect attributes of current node
            tags = self._getattrs(
                node, 'y0', 'y1', 'x0', 'x1', 'width', 'height', 'bbox',
                'linewidth', 'pts', 'index', 'name', 'matrix', 'word_margin'
            )
            if type(node) == LTImage:
                tags.update(self._getattrs(
                    node, 'colorspace', 'bits', 'imagemask', 'srcsize',
                    'stream', 'name', 'pts', 'linewidth')
                )
            elif type(node) == LTChar:
                tags.update(self._getattrs(
                    node, 'fontname', 'adv', 'upright', 'size')
                )
            elif type(node) == LTPage:
                tags.update(self._getattrs(node, 'pageid', 'rotate'))

            # create node
            branch = parser.makeelement(node.__class__.__name__, tags)

        branch.layout = node
        self._elements += [branch]  # make sure layout keeps state
        if root is None:
            root = branch

        # add text
        if hasattr(node, 'get_text'):
            branch.text = strip_invalid_xml_chars(node.get_text())

        # add children if node is an iterable
        if hasattr(node, '__iter__'):
            last = None
            for child in node:
                child = self._xmlize(child, root)
                if self.merge_tags and child.tag in self.merge_tags:
                    if branch.text and child.text in branch.text:
                        continue
                    elif last is not None and last.tag in self.merge_tags:
                        last.text += child.text
                        last.set(
                            '_obj_id',
                            last.get('_obj_id','') + "," + child.get('_obj_id','')
                        )
                        continue
                # sort children by bounding boxes
                if self.resort:
                    _append_sorted(root, child, _comp_bbox)
                else:
                    branch.append(child)
                last = child
        return branch

    def _getattrs(self, obj, *attrs):
        """ Return dictionary of given attrs on given object, if they exist,
        processing through _filter_value().
        """
        filtered_attrs = {}
        for attr in attrs:
            if hasattr(obj, attr):
                filtered_attrs[attr] = obj_to_string(
                    self._filter_value(getattr(obj, attr))
                )
        return filtered_attrs

    def _filter_value(self, val):
        if self.round_floats:
            if type(val) == float:
                val = round(val, self.round_digits)
            elif hasattr(val, '__iter__') and not isinstance(val, six.string_types):
                val = [self._filter_value(item) for item in val]
        return val

    # page access stuff
    def get_page(self, page_number):
        """ Get PDFPage object -- 0-indexed."""
        return self._cached_pages(target_page=page_number)

    def get_layout(self, page):
        """ Get PDFMiner Layout object for given page object or page number. """
        if type(page) == int:
            page = self.get_page(page)
        self.interpreter.process_page(page)
        layout = self.device.get_result()
        layout = self._add_annots(layout, page.annots)
        return layout

    def get_layouts(self):
        """ Get list of PDFMiner Layout objects for each page. """
        return (self.get_layout(page) for page in self._cached_pages())

    def _cached_pages(self, target_page=-1):
        """
        Get a page or all pages from page generator, caching results.
        This is necessary because PDFMiner searches recursively for pages,
        so we won't know how many there are until we parse the whole document,
        which we don't want to do until we need to.
        """
        try:
            # pdfminer < 20131022
            self._pages_iter = self._pages_iter or self.doc.get_pages()
        except AttributeError:
            # pdfminer >= 20131022
            self._pages_iter = self._pages_iter or \
                PDFPage.create_pages(self.doc)

        if target_page >= 0:
            while len(self._pages) <= target_page:
                next_page = next(self._pages_iter)
                if not next_page:
                    return None
                next_page.page_number = 0
                self._pages += [next_page]
            try:
                return self._pages[target_page]
            except IndexError:
                return None
        self._pages += list(self._pages_iter)
        return self._pages

    def _add_annots(self, layout, annots):
        """Adds annotations to the layout object
        """
        if annots:
            for annot in resolve1(annots):
                annot = resolve1(annot)
                if annot.get('Rect') is not None:
                    annot['bbox'] = annot.pop('Rect')  # Rename key
                    annot = self._set_hwxy_attrs(annot)
                try:
                    annot['URI'] = resolve1(annot['A'])['URI']
                except KeyError:
                    pass
                for k, v in six.iteritems(annot):
                    if not isinstance(v, six.string_types):
                        annot[k] = obj_to_string(v)
                elem = parser.makeelement('Annot', annot)
                layout.add(elem)
        return layout

    @staticmethod
    def _set_hwxy_attrs(attr):
        """Using the bbox attribute, set the h, w, x0, x1, y0, and y1
        attributes.
        """
        bbox = attr['bbox']
        attr['x0'] = bbox[0]
        attr['x1'] = bbox[2]
        attr['y0'] = bbox[1]
        attr['y1'] = bbox[3]
        attr['height'] = attr['y1'] - attr['y0']
        attr['width'] = attr['x1'] - attr['x0']
        return attr


if __name__ == "__main__":
    import doctest
    pdf = PDFQuery("../examples/sample.pdf")
    doctest.testmod(extraglobs={'pdf': pdf}, optionflags=doctest.ELLIPSIS)
