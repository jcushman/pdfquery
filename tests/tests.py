# to run:
# pip install unittest2
# unit2 discovery

import StringIO
import sys
import pdfquery
import unittest2

from pdfquery.cache import FileCache, DummyCache


class TestPDFQuery(unittest2.TestCase):

    def setUp(self):
        self.pdf = pdfquery.PDFQuery("tests/sample.pdf",
                                     parse_tree_cacher=FileCache("/tmp/") if sys.argv[1]=='cache' else None,
                                     )
        self.pdf.load()

    def test_xml_conversion(self):
        """
            Test that converted XML hasn't changed from saved version.
        """
        # get current XML for sample file
        tree_string = StringIO.StringIO()
        self.pdf.tree.write(tree_string, pretty_print=True, encoding="utf-8")
        tree_string = tree_string.getvalue()

        # get previous XML
        # this varies by Python version, because the float handling isn't quite the same
        comparison_file = "tests/sample_output_python_2.6.xml" if sys.version_info[0] == 2 and sys.version_info[1] < 7 else "tests/sample_output.xml"
        with open(comparison_file, 'rb') as f:
            saved_string = f.read()

        # compare current to previous
        if tree_string != saved_string:
            with open("tests/failed_output.xml", "wb") as out:
                out.write(tree_string)
            self.fail("XML conversion of sample.pdf has changed! Compare tests/sample_output.xml to tests/failed_output.xml.")

    def test_selectors(self):
        """
            Test the :contains and :in_bbox selectors.
        """
        label = self.pdf.pq('LTTextLineHorizontal:contains("Your first name and initial")')
        self.assertEqual(len(label), 1)

        left_corner = float(label.attr('x0'))
        self.assertEqual(left_corner, 143.651)

        bottom_corner = float(label.attr('y0'))
        self.assertEqual(bottom_corner, 714.694)

        name = self.pdf.pq('LTTextLineHorizontal:in_bbox("%s, %s, %s, %s")' % (left_corner, bottom_corner - 30, left_corner + 150, bottom_corner)).text()
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

            ('oath', 'LTTextLineHorizontal:contains("perjury")', lambda match: match.text()[:30] + "..."),
            ('year', 'LTTextLineHorizontal:contains("Form 1040A (")', lambda match: int(match.text()[-5:-1]))
        ])

        self.assertDictEqual(values, {
            'last_name': 'Michaels',
            'spouse': 'Susan R.',
            'oath': u'Under penalties of perjury, I ...',
            'year': 2007
        })

    def test_page_numbers(self):
        self.assertEqual(self.pdf.tree.getroot()[0].get('page_label'), '1')

class TestUnicode(unittest2.TestCase):

    def setUp(self):
        self.pdf = pdfquery.PDFQuery("tests/unicode_docinfo.pdf")
        self.pdf.load()

    def test_docinfo(self):
        docinfo = self.pdf.tree.getroot()
        self.assertEqual(docinfo.attrib['Title'], u'\u262d\U0001f61c\U0001f4a9Unicode is fun!')

if __name__ == '__main__':
    unittest2.main()
