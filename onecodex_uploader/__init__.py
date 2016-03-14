from __future__ import print_function
import os
import platform
import sys
from pkg_resources import resource_filename

from PySide import QtCore, QtGui

from onecodex_uploader.mainwindow_ui import Ui_MainWindow
from onecodex_uploader.upload import upload_file, get_apikey, UploadException
from onecodex_uploader.sniff import sniff_file

OC_SERVER = 'https://app.onecodex.com/'


class FileViewer(QtGui.QListView):
    file_dropped = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(FileViewer, self).__init__(parent)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.setIconSize(QtCore.QSize(16, 16))
        if platform.system() != 'Darwin':
            # drag and drop URLs are malformed on Mac OS X, i.e.:
            # https://bugreports.qt.io/browse/QTBUG-24379
            # workaround is using NSURL (from pyobjc?) if we ever want this
            self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                self.file_dropped.emit(str(url.toLocalFile()))
        else:
            event.ignore()


class FileListModel(QtCore.QAbstractListModel):
    def __init__(self, parent=None):
        super(FileListModel, self).__init__(parent)
        self.file_names = []
        self.file_info = []

    def rowCount(self, index):
        return len(self.file_names)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        if index.row() >= len(self.file_names) or index.row() < 0:
            return None

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:
                return os.path.basename(self.file_names[index.row()])
            # TODO: allow for more columns to e.g. display extra file info
        elif role == QtCore.Qt.ToolTipRole:
            return self.file_names[index.row()]
        elif role == QtCore.Qt.DecorationRole and index.column() == 0:
            if self.file_info[index.row()]['compression'] == 'none':
                pixmap = QtGui.QPixmap(resource_path('icons/fa-file.png'))
            else:
                pixmap = QtGui.QPixmap(resource_path('icons/fa-file-archive.png'))
            return QtGui.QIcon(pixmap.scaled(16, 16))

    def add_file(self, filename):
        self.reset()  # TODO: remove this to enable multiple files

        qc_results = sniff_file(filename)
        if qc_results['file_type'] == 'bad':
            QtGui.QMessageBox.critical(self, 'Error!', qc_results['msg'], QtGui.QMessageBox.Abort)
            return
        elif qc_results['seq_type'] == 'aa':
            QtGui.QMessageBox.critical(self, 'Error!', 'Amino acid FASTX files not supported',
                                       QtGui.QMessageBox.Abort)
            return

        self.beginInsertRows(QtCore.QModelIndex(), len(self.file_names), len(self.file_names))
        self.file_names.append(filename)
        self.file_info.append(qc_results)
        self.endInsertRows()

    def reset(self):
        self.beginRemoveRows(QtCore.QModelIndex(), 0, len(self.file_names) - 1)
        self.file_names = []
        self.file_info = []
        self.endRemoveRows()


def resource_path(relative_path):
    """
    Get path to resource when running in PyInstaller package or otherwise
    """
    try:
        return os.path.join(sys._MEIPASS, relative_path)
    except AttributeError:
        return resource_filename('onecodex_uploader', relative_path)


class OCUploader(QtGui.QMainWindow):
    """
    Logic for the file uploader
    """
    def __init__(self, *args):
        super(OCUploader, self).__init__(*args)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # add some pretty icons
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(resource_path('icons/fa-folder-open.png')))
        self.ui.fileButton.setIcon(icon)
        self.ui.fileButton.setIconSize(QtCore.QSize(16, 16))
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(resource_path('icons/fa-upload.png')))
        self.ui.uploadButton.setIcon(icon)
        self.ui.uploadButton.setIconSize(QtCore.QSize(16, 16))

        # set up the file list
        self.files_model = FileListModel(self)
        view = FileViewer()
        view.setModel(self.files_model)
        view.file_dropped.connect(self.files_model.add_file)
        self.ui.fileListLayout.addWidget(view)
        self.view = view

        # set up the ui
        self.ui.fileButton.clicked.connect(self.select_file_button)
        self.ui.uploadButton.clicked.connect(self.upload_button)
        self.reset()

        # set some globals
        self.lock = QtCore.QMutex()

    def upload_button(self):
        self.ui.fileButton.hide()
        self.ui.uploadButton.setEnabled(False)

        # make the upload progress bar just show "loading" not an actual progress
        self.ui.uploadProgress.show()
        self.ui.uploadProgress.setRange(0, 0)

        # force the GUI to update
        QtGui.QApplication.instance().processEvents()

        username, password = self.ui.usernameField.text(), self.ui.passwordField.text()
        if username == '':
            QtGui.QMessageBox.critical(self, 'Error!', 'Please enter a username',
                                       QtGui.QMessageBox.Abort)
            self.reset()
            return
        elif password == '':
            QtGui.QMessageBox.critical(self, 'Error!', 'Please enter a password',
                                       QtGui.QMessageBox.Abort)
            self.reset()
            return

        apikey = get_apikey(username, password, OC_SERVER)
        self.ui.uploadProgress.setRange(0, 100)
        QtGui.QApplication.instance().processEvents()

        if apikey is None or apikey.strip() == '':
            # apikey is None is username/password failed, apikey == '' if user has no apikey
            QtGui.QMessageBox.critical(self, 'Error!', 'Could not authenticate successfully.',
                                       QtGui.QMessageBox.Abort)
        elif self.file_name == '':
            QtGui.QMessageBox.critical(self, 'Error!', 'No file selected.',
                                       QtGui.QMessageBox.Abort)
        else:
            filename = self.files_model.file_names[0]
            try:
                upload_file(filename, apikey, OC_SERVER, self.update_progress)
                QtGui.QMessageBox.information(self, 'Success!', 'File uploaded successfully')
                # TODO: when handling multiple files should just update the icon or something
                self.files_model.reset()
            except UploadException as e:
                QtGui.QMessageBox.critical(self, 'Error!', str(e), QtGui.QMessageBox.Abort)

        self.reset()

    def select_file_button(self):
        open_dialog = QtGui.QFileDialog()
        open_dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
        name = open_dialog.getOpenFileName(self, 'Upload File', '', 'Sequencing File (*.*)')

        self.files_model.add_file(name[0])

    def update_progress(self, progress):
        self.lock.lock()
        self.ui.uploadProgress.setValue(int(100 * progress))
        QtGui.QApplication.instance().processEvents()
        self.lock.unlock()

    def reset(self):
        self.ui.fileButton.show()
        self.ui.uploadProgress.hide()
        self.ui.uploadProgress.setRange(0, 100)
        self.ui.uploadProgress.reset()
        self.ui.uploadButton.setEnabled(True)
