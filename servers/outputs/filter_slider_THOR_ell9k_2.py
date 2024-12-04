# -*- coding: utf-8 -*-
"""
Output server for a second Thorlabs ELL9K filter slider. 
Inherits from FilterSliderThorEll9k

Created on Thu Apr  4 15:58:30 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = filter_slider_THOR_ell9k_2
version = 1.0
description =

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""


from servers.outputs.filter_slider_THOR_ell9k import FilterSliderThorEll9k


class FilterSliderThorEll9k2(FilterSliderThorEll9k):
    name = "filter_slider_THOR_ell9k_2"


__server__ = FilterSliderThorEll9k2()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
