# -*- coding: utf-8 -*-
import re

from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LAParams, LTChar, LTImage, LTPage #LTTextBox, LTTextLine, LTFigure, 
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdftypes import resolve1

from pyquery import PyQuery
from lxml import cssselect, etree

# custom selectors monkey-patch

def _xpath_in_bbox(self, xpath, expr):
    x0,y0,x1,y1 = map(float, expr.split(","))
    # TODO: seems to be doing < rather than <= ???
    xpath.add_post_condition("@x0 >= %s" % x0)
    xpath.add_post_condition("@y0 >= %s" % y0)
    xpath.add_post_condition("@x1 <= %s" % x1)
    xpath.add_post_condition("@y1 <= %s" % y1)
    return xpath
cssselect.Function._xpath_in_bbox = _xpath_in_bbox

def _xpath_overlaps_bbox(self, xpath, expr):
    x0,y0,x1,y1 = map(float, expr.split(","))
    # TODO: seems to be doing < rather than <= ???
    xpath.add_post_condition("@x0 <= %s" % x1)
    xpath.add_post_condition("@y0 <= %s" % y1)
    xpath.add_post_condition("@x1 >= %s" % x0)
    xpath.add_post_condition("@y1 >= %s" % y0)
    return xpath
cssselect.Function._xpath_in_bbox = _xpath_in_bbox


# Re-sort the PDFMiner Layout tree so elements that fit inside other elements will be children of them

def _append_sorted(root, el, comparator):
    """ Add el as a child of root, or as a child of one of root's children. Comparator is a function(a, b) returning > 0 if a is a child of b, < 0 if b is a child of a, 0 if neither. """
    for child in root:
        rel = comparator(el, child)
        if rel > 0: # el fits inside child, add to child and return
            _append_sorted(child, el, comparator)
            return
        if rel < 0: # child fits inside el, move child into el (may move more than one)
            _append_sorted(el, child, comparator)
    # we weren't added to a child, so add to root
    root.append(el)

def _box_in_box(el, child):
    """ Return True if child is contained within el. """
    return float(el.get('x0')) <= float(child.get('x0')) and float(el.get('x1')) >= float(child.get('x1')) and float(el.get('y0')) <= float(child.get('y0')) and float(el.get('y1')) >= float(child.get('y1'))

def _comp_bbox(el, el2):
    """ Return 1 if el in el2, -1 if el2 in el, else 0"""
    if _box_in_box(el2, el): return 1
    if _box_in_box(el, el2): return -1
    return 0

# random helpers

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

# custom PDFDocument class
class QPDFDocument(PDFDocument):
    def get_page_number(self, index):
        """
        Given an index, return page label as specified by catalog['PageLabels']['Nums']
        Nums == [   0 << /S /r >>
                    4 << /S /D >>
                    7 << /S /D /P (A−) /St 8>>
                ]
                    /S = [
                            D Decimal arabic numerals
                            R Uppercase roman numerals
                            r Lowercase roman numerals
                            A Uppercase letters (A to Z for the first 26 pages, AA to ZZ for the next 26, and so on)
                            a Lowercase letters (a to z for the first 26 pages, aa to zz for the next 26, and so on)
                        ] (if no /S, just use prefix ...)
                    /P = text string label
                    /St = integer start value
        """
        try:
            nums = resolve1(self.catalog['PageLabels'])['Nums'] # e.g. [ 0 {settings} 2 {settings} 20
            # {settings} ...]
            assert len(nums) > 1 and len(nums) % 2 == 0
        except:
            return ""
        for i in range(len(nums)-2,-1,-2): # find highest page number lower than requested page
            if nums[i] <= index:
                break
        settings = nums[i+1].resolve()
        page_num = ""
        if 'S' in settings: # show a digit
            page_num = index - nums[i]
            if 'St' in settings: # alternate start value
                page_num += settings['St']
            else:
                page_num += 1
            num_type = settings['S'].name
            if num_type.lower() == 'r': # roman (upper or lower)
                import roman
                page_num = roman.toRoman(page_num)
                if num_type == 'r':
                    page_num = page_num.lower()
            elif num_type.lower() == 'a': # letters
                # a to z for the first 26 pages, aa to zz for the next 26, and so on
                letter = chr(page_num % 26 + 65)
                letter *= page_num / 26 + 1
                if num_type == 'a':
                    letter = letter.lower()
                page_num = letter
            else: #if num_type == 'D': # decimal arabic
                page_num = unicode(page_num)
        if 'P' in settings: # page prefix
            page_num = settings['P']+page_num
        return page_num


# create etree parser using custom Element class

class LayoutElement(etree.ElementBase):
    @property
    def layout(self):
        if not hasattr(self, '_layout'):
            print "setting to None"
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
    def __init__(self, filename, 
                    merge_tags=('LTChar', 'LTAnon'),
                    round_floats=True,
                    round_digits=3,
                    input_text_formatter=None,
                    normalize_spaces=True,
                    resort=True,
                    ):
        # store input
        self.filename = filename
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
            self.input_text_formatter = False

        # open doc
        fp = open(filename, 'rb')
        parser = PDFParser(fp)
        doc = QPDFDocument()
        parser.set_document(doc)
        doc.set_parser(parser)
        doc.initialize()
        self.doc = doc
        self.parser = parser
        self.tree = None
        self.pq = None

        # set up layout parsing
        rsrcmgr = PDFResourceManager()
        laparams = LAParams(all_texts=True, detect_vertical=True)
        self.device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        self.interpreter = PDFPageInterpreter(rsrcmgr, self.device)

        # caches
        self._pages = []
        self._pages_iter = None
        self._elements = []

    def load(self, *page_numbers):
        """
            Load etree and pyquery object for entire document, or given page numbers (ints or lists).
            After this is called, objects are available at pdf.tree and pdf.pq.

            >>> pdf.load()
            >>> pdf.tree
            <lxml.etree._ElementTree object at ...>
            >>> pdf.pq('LTPage')
            [<LTPage>, <LTPage>]
            >>> pdf.load(1)
            >>> pdf.pq('LTPage')
            [<LTPage>]
            >>> pdf.load(0,1)
            >>> pdf.pq('LTPage')
            [<LTPage>, <LTPage>]
        """
        self.tree = self.get_tree(*_flatten(page_numbers))
        self.pq = self.get_pyquery(self.tree)

    def extract(self, searches, tree=None, as_dict=True):
        """
            >>> foo = pdf.extract( [ ['pages', 'LTPage'] ])
            >>> foo
            {'pages': [<LTPage>, <LTPage>]}
            >>> pdf.extract( [ ['bar', ':in_bbox("100,100,400,400")'] ], foo['pages'][0])
            {'bar': [<LTTextLineHorizontal>, <LTTextBoxHorizontal>,...
        """
        if self.tree is None or self.pq is None:
            self.load()
        pq = PyQuery(tree) if tree is not None else self.pq
        if tree is None:
            pq = self.pq
        else:
            pq = PyQuery(tree)
        results = []
        formatter = None
        parent = pq
        for search in searches:
            if len(search) < 3:
                search = list(search) + [formatter]
            key, search, tmp_formatter = search
            if key == 'with_formatter':
                if type(search) == str: # is a pyquery method name, e.g. 'text'
                    formatter = lambda o, search=search: getattr(o, search)()
                elif hasattr(search, '__call__') or not search: # is a method, or None to end formatting
                    formatter = search
                else:
                    raise TypeError("Formatter should be either a pyquery method name or a callable function.")
            elif key == 'with_parent':
                parent = pq(search) if search else pq
            else:
                try:
                    result = parent("*").filter(search) if hasattr(search, '__call__') else parent(search)
                except cssselect.SelectorSyntaxError, e:
                    raise cssselect.SelectorSyntaxError( "Error applying selector '%s': %s" % (search, e) )
                if tmp_formatter:
                    result = tmp_formatter(result)
                results += result if type(result) == tuple else [[key, result]]
        if as_dict:
            results = dict(results)
        return results
    




    # tree building stuff

    def get_pyquery(self, tree=None, page_numbers=[]):
        """
            Wrap given tree in pyquery and return.
            If no tree supplied, will generate one from given page_numbers, or all page numbers.
        """
        if tree is None:
            if not page_numbers and self.tree is not None:
                tree = self.tree
            else:
                tree = self.get_tree(page_numbers)
        if hasattr(tree, 'getroot'):
            tree = tree.getroot()
        return PyQuery(tree)

    def get_tree(self, *page_numbers):
        """
            Return lxml.etree.ElementTree for entire document, or page numbers given if any.
        """
        # set up root
        root = parser.makeelement("pdfxml")
        for k, v in self.doc.info[0].items():
            root.set(k, unicode(v))
        # add pages
        if page_numbers:
            pages = [[n, self.get_layout(self.get_page(n))] for n in _flatten(page_numbers)]
        else:
            pages = enumerate(self.get_layouts())
        for n, page in pages:
            page = self._xmlize(page)
            page.set('page_index', unicode(n))
            page.set('page_label', self.doc.get_page_number(n))
            root.append(page)
        self._clean_text(root)
        # wrap root in ElementTree
        return etree.ElementTree(root)

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
        except TypeError: # not an iterable node
            pass


    def _xmlize(self, node, root=None):
        
        # collect attributes of current node
        tags = self._getattrs(node, 'y0', 'y1', 'x0', 'x1', 'width', 'height', 'bbox', 'linewidth', 'pts', 'index','name','matrix','word_margin' )
        if type(node) == LTImage:
            tags.update( self._getattrs(node, 'colorspace','bits','imagemask','srcsize','stream','name','pts','linewidth') )
        elif type(node) == LTChar:
            tags.update( self._getattrs(node, 'fontname','adv','upright','size') )
        elif type(node) == LTPage:
            tags.update( self._getattrs(node, 'pageid','rotate') )
          
        # create node
        branch = parser.makeelement(node.__class__.__name__, tags)
        branch.layout = node
        self._elements += [branch] # make sure layout keeps state
        if root is None:
            root = branch

        # add text
        if hasattr(node, 'get_text'):
            branch.text = node.get_text()
                
        # add children
        try:
            children = [self._xmlize(child, root) for child in node]
            last = None
            for child in children:
                if self.merge_tags and child.tag in self.merge_tags:
                    if branch.text and child.text in branch.text:
                        continue
                    elif last is not None and last.tag in self.merge_tags:
                        last.text += child.text
                        last.set('_obj_id', last.get('_obj_id')+","+child.get('_obj_id'))
                        continue
                # sort children by bounding boxes
                if self.resort:
                    _append_sorted(root, child, _comp_bbox)
                else:
                    branch.append(child)
                last = child
        except TypeError: # not an iterable node
            pass

        return branch

    def _getattrs(self, obj, *attrs):
        """ Return dictionary of given attrs on given object, if they exist, processing through filter_value(). """
        return dict( (attr, unicode(self._filter_value(getattr(obj, attr)))) for attr in attrs if hasattr(obj, attr))

    def _filter_value(self, val):
        if self.round_floats:
            if type(val) == float:
                val = round(val, self.round_digits)
            elif hasattr(val, '__iter__'):
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
        return self.device.get_result()

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
        self._pages_iter = self._pages_iter or self.doc.get_pages()
        if target_page >= 0:
            while len(self._pages) <= target_page:
                next = self._pages_iter.next()
                if not next:
                    return None
                next.page_number = 0
                self._pages += [next]
            try:
                return self._pages[target_page]
            except IndexError:
                return None
        self._pages += list(self._pages_iter)
        return self._pages


if __name__ == "__main__":
    import doctest
    pdf = PDFQuery("../examples/sample.pdf")
    doctest.testmod(extraglobs={'pdf': pdf}, optionflags=doctest.ELLIPSIS)