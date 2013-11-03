#-*- coding:utf-8 -*-
#
# Copyright (C) 2008 - Olivier Lauzanne <olauzanne@gmail.com>
#
# Distributed under the BSD license, see LICENSE.txt
from cssselect import xpath as cssselect_xpath


class PDFQueryTranslator(cssselect_xpath.GenericTranslator):

    def xpath_in_bbox_function(self, xpath, fn):
        if len(fn.arguments) > 1:
            x0,y0,x1,y1 = [float(t.value) for t in fn.arguments]
        else:
            x0,y0,x1,y1 = map(float, fn.arguments[0].value.split(","))
        # TODO: seems to be doing < rather than <= ???
        xpath.add_condition("@x0 >= %s" % x0)
        xpath.add_condition("@y0 >= %s" % y0)
        xpath.add_condition("@x1 <= %s" % x1)
        xpath.add_condition("@y1 <= %s" % y1)
        return xpath

    def xpath_overlaps_bbox_function(self, xpath, fn):
        if len(fn.arguments) > 1:
            x0,y0,x1,y1 = [float(t.value) for t in fn.arguments]
        else:
            x0,y0,x1,y1 = map(float, fn.arguments[0].value.split(","))
        # TODO: seems to be doing < rather than <= ???
        xpath.add_condition("@x0 <= %s" % x1)
        xpath.add_condition("@y0 <= %s" % y1)
        xpath.add_condition("@x1 >= %s" % x0)
        xpath.add_condition("@y1 >= %s" % y0)
        return xpath