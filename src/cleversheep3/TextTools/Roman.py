#!/usr/bin/env python
"""Small module providing conversion of decimal to Roman number format.

Credits
    From Raymond Hettinger, in a response to the
    `Python Cookbook recipe 415384`_.

.. _`Python Cookbook recipe 415384`: http://code.activestate.com/recipes/415384/

"""
__docformat__ = "restructuredtext"


coding = zip(
    [1000,900,500,400,100,90,50,40,10,9,5,4,1],
    ["M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"]
)

def decToRoman(num):
    """Convert a decimal number to Roman numeral form.

    This is useful, for example, when producing numbered lists where
    the numbers are Roman numerals.

    It is range limited to only support values in the range 1 to 3999. This is
    easily good enough for things like document generation, which is why this
    module exists as part of cleversheep3.

    :Return:
        A string of roman numerals in upper case.

    """
    if num <= 0 or num >= 4000 or int(num) != num: #pragma: unreachable
        raise ValueError('Input should be an integer between 1 and 3999')
    result = []
    for d, r in coding:
        while num >= d:
            result.append(r)
            num -= d
    return ''.join(result)
