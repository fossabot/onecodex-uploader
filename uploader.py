#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from PySide.QtGui import QApplication
from onecodex_uploader import OCUploader

QApplication.setGraphicsSystem('native')
app = QApplication(sys.argv)
oc_uploader = OCUploader()
oc_uploader.show()
sys.exit(app.exec_())
