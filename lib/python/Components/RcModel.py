#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
from Tools.Directories import SCOPE_SKINS, resolveFilename


class RcModel:
	def __init__(self):
		pass

	def getRcFile(self, ext):
		remote = getRCName()
		f = resolveFilename(SCOPE_SKINS, 'rc_models/' + remote + '.' + ext)
		if not os.path.exists(f):
			f = resolveFilename(SCOPE_SKINS, 'rc_models/dmm1.' + ext)
		return f

	def getRcImg(self):
		return self.getRcFile('png')

	def getRcPositions(self):
		return self.getRcFile('xml')


rc_model = RcModel()
