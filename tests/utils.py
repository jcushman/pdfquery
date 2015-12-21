from six import StringIO
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
        tree_string = StringIO()
        pdf.tree.write(tree_string, pretty_print=True, encoding="utf-8")
        tree_string = tree_string.getvalue()

        # get previous XML
        # this varies by Python version, because the float handling isn't quite
        # the same
        comparison_file = "tests/saved_output/%s.xml" % (output_name,)
        with open(comparison_file, 'rb') as f:
            saved_string = f.read()

        # compare current to previous
        if tree_string != saved_string:
            output_path = "tests/%s_failed_output.xml" % output_name
            with open(output_path, "wb") as out:
                out.write(tree_string)
            self.fail("XML conversion of sample pdf has changed! Compare %s to %s" % (comparison_file, output_path))