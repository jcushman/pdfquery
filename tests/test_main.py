# to run:
# python setup.py test
#
# to debug:
# pip install nose
# nosetests --pdb

import sys
import tempfile

import pdfquery
from pdfquery.cache import FileCache

from .utils import BaseTestCase

### helpers ###




class TestPDFQuery(BaseTestCase):
    """
        Various tests based on the IRS_1040A sample doc.
    """

    @classmethod
    def setUpClass(cls):
        cls.pdf = pdfquery.PDFQuery("tests/samples/IRS_1040A.pdf")
        cls.pdf.load()

    def test_xml_conversion(self):
        """
            Test that converted XML hasn't changed from saved version.
        """
        if (sys.version_info[:2] <= (3, 5)):
            # PDFMiner parses slightly different with Python 3.5
            self.assertValidOutput(self.pdf, "IRS_1040A_output_py35")
        else:
            self.assertValidOutput(self.pdf, "IRS_1040A_output")

    def test_selectors(self):
        """
            Test the :contains and :in_bbox selectors.
        """
        label = self.pdf.pq('LTTextLineHorizontal:contains("Your first name '
                            'and initial")')
        self.assertEqual(len(label), 1)

        left_corner = float(label.attr('x0'))
        self.assertEqual(left_corner, 143.651)

        bottom_corner = float(label.attr('y0'))
        self.assertEqual(bottom_corner, 714.694)

        name = self.pdf.pq('LTTextLineHorizontal:in_bbox("%s, %s, %s, %s")' %
                           (left_corner,
                            bottom_corner - 30,
                            left_corner + 150,
                            bottom_corner)
                           ).text()
        self.assertEqual(name, "John E.")

    def test_extract(self):
        """
            Test the extract() function.
        """
        values = self.pdf.extract([
            ('with_parent', 'LTPage[pageid="1"]'),
            ('with_formatter', 'text'),

            ('last_name', 'LTTextLineHorizontal:in_bbox("315,680,395,700")'),
            ('spouse', 'LTTextLineHorizontal:in_bbox("170,650,220,680")'),

            ('with_parent', 'LTPage[pageid="2"]'),

            ('oath', 'LTTextLineHorizontal:contains("perjury")',
             lambda match: match.text()[:30] + "..."),
            ('year', 'LTTextLineHorizontal:contains("Form 1040A (")',
             lambda match: int(match.text()[-5:-1]))
        ])

        self.assertDictEqual(values, {
            'last_name': 'Michaels',
            'spouse': 'Susan R.',
            'oath': u'Under penalties of perjury, I ...',
            'year': 2007
        })

    def test_page_numbers(self):
        self.assertEqual(self.pdf.tree.getroot()[0].get('page_label'), '1')


class TestDocInfo(BaseTestCase):

    def test_docinfo(self):

        doc_info_results = [
            ["tests/samples/bug11.pdf",
             {'Producer': 'Mac OS X 10.9.3 Quartz PDFContext',
              'Title': u'\u262d\U0001f61c\U0001f4a9Unicode is fun!',
              'Author': 'Russkel', 'Creator': 'Firefox',
              'ModDate': "D:20140528141914+08'00'",
              'CreationDate': 'D:20140528061106Z', 'Subject': ''}],
            ["tests/samples/bug15.pdf",
             {'Producer': 'Mac OS X 10.9.3 Quartz PDFContext',
              'Author': 'Brepols Publishers',
              'Creator': 'PDFsharp 1.2.1269-g (www.pdfsharp.com)',
              'AAPL_Keywords': '["Brepols", "Publishers", "CTLO"]',
              'Title': 'Exporter',
              'ModDate': "D:20140614192741Z00'00'",
              'Keywords': 'Brepols, Publishers, CTLO',
              'CreationDate': "D:20140614192741Z00'00'",
              'Subject': 'Extrait de la Library of Latin Texts - Series A'}],
            ["tests/samples/bug17.pdf",
             {'CreationDate': 'D:20140328164512Z',
              'Creator': 'Adobe InDesign CC (Macintosh)',
              'ModDate': 'D:20140328164513Z',
              'Producer': 'Adobe PDF Library 10.0.1', 'Trapped': '/False'}]
        ]

        for file_path, expected_results in doc_info_results:
            pdf = pdfquery.PDFQuery(file_path)
            pdf.load(None)
            docinfo = dict(pdf.tree.getroot().attrib)
            self.assertDictEqual(docinfo,expected_results)


class TestUnicode(BaseTestCase):

    def test_unicode_text(self):
        pdf = pdfquery.PDFQuery("tests/samples/bug18.pdf")
        pdf.load()
        self.assertEqual(
            pdf.pq('LTTextLineHorizontal:contains("Hop Hing Oils")').text(),
            (u'5 Hop Hing Oils and Fats (Hong Kong) Ltd \uf06c '
             u'\u7279\u5bf6\u7cbe\u88fd\u8c6c\u6cb9')
        )

    def test_invalid_xml_characters(self):
        pdf = pdfquery.PDFQuery("tests/samples/bug39.pdf")
        pdf.load(2)  # throws error if we fail to strip ascii control characters -- see issue #39


class TestAnnotations(BaseTestCase):
    """
        Ensure that annotations such as links are getting added to the PDFs
        properly, as discussed in issue #28.
    """

    def test_xml_conversion(self):
        """
            Test that converted XML hasn't changed from saved version.
        """
        pdf = pdfquery.PDFQuery("tests/samples/bug28.pdf")
        pdf.load()
        self.assertValidOutput(pdf, "bug28_output")

    def test_annot_dereferencing(self):
        """
            See issues #37, #42.
        """
        pdf = pdfquery.PDFQuery("tests/samples/bug37.pdf")
        pdf.load()
        pdf = pdfquery.PDFQuery("tests/samples/bug42.pdf")
        pdf.load()


class TestPageRange(BaseTestCase):
    """
        Test various page number parameters
    """

    @classmethod
    def setUpClass(cls):
        cache_dir = "{}/".format(tempfile.gettempdir())
        cls.pdf = pdfquery.PDFQuery("tests/samples/bug67.pdf", parse_tree_cacher=FileCache(cache_dir))

    def test_page_int(self):
        self.pdf.load(3)
        self.assertEqual(len(self.pdf.pq('LTPage')), 1)
        self.pdf.load(0, 10, 25, 49)
        self.assertEqual(len(self.pdf.pq('LTPage')), 4)

    def test_page_array(self):
        self.pdf.load([0, 7, 11])
        self.assertEqual(len(self.pdf.pq('LTPage')), 3)
        self.pdf.load([10], [0, 12], [30, 40])
        self.assertEqual(len(self.pdf.pq('LTPage')), 5)

    def test_page_mixed(self):
        self.pdf.load([0, 7, 11], [0, 44], 1)
        self.assertEqual(len(self.pdf.pq('LTPage')), 6)

    def test_page_range(self):
        self.pdf.load(range(0, 150))
        self.assertEqual(len(self.pdf.pq('LTPage')), 150)