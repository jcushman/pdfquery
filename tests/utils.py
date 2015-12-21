from lxml import etree

from six import BytesIO
import sys

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

class BaseTestCase(unittest.TestCase):

    def assertValidOutput(self, pdf, output_name):
        """
            Test that converted XML hasn't changed from saved version.
        """
        # Just skip this test if we're on python 2.6 -- float handling makes element sort ordering unpredictable,
        # causing intermittent test failures.
        if sys.version_info[:2] < (2, 7):
            return

        # get current XML for sample file
        tree_string = BytesIO()
        pdf.tree.write(tree_string, pretty_print=True, encoding="utf-8")
        tree_string = tree_string.getvalue()

        # get previous XML
        # this varies by Python version, because the float handling isn't quite
        # the same
        comparison_file = "tests/saved_output/%s.xml" % (output_name,)
        with open(comparison_file, 'rb') as f:
            saved_string = f.read()

        # compare current to previous
        if not self.xml_strings_equal(saved_string, tree_string):
            output_path = "tests/%s_failed_output.xml" % output_name
            with open(output_path, "wb") as out:
                out.write(tree_string)
            self.fail("XML conversion of sample pdf has changed! Compare %s to %s" % (comparison_file, output_path))

    def xml_strings_equal(self, s1, s2):
        """
            Return true if two xml strings are semantically equivalent (ignoring attribute ordering and whitespace).
        """
        # via http://stackoverflow.com/a/24349916/307769
        def elements_equal(e1, e2):
            if e1.tag != e2.tag: return False
            if e1.text != e2.text: return False
            if e1.tail != e2.tail: return False
            if e1.attrib != e2.attrib: return False
            if len(e1) != len(e2): return False
            return all(elements_equal(c1, c2) for c1, c2 in zip(e1, e2))

        e1 = etree.XML(s1, parser=etree.XMLParser(remove_blank_text=True))
        e2 = etree.XML(s2, parser=etree.XMLParser(remove_blank_text=True))

        return elements_equal(e1, e2)
