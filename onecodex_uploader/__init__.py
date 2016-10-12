from __future__ import print_function

from base64 import b64decode
import os
import platform
import sys
from pkg_resources import resource_filename

from PySide import QtCore, QtGui
from raven import Client

from onecodex_uploader.mainwindow_ui import Ui_MainWindow
from onecodex_uploader.upload import check_version, upload_file, get_apikey, UploadException
from onecodex_uploader.sniff import sniff_file
from onecodex_uploader.version import __version__

OC_SERVER = os.environ.get('ONE_CODEX_SERVER', 'https://app.onecodex.com/')

# set up a sentry client for error reporting; we obfuscate the key slightly, but it sounds like
# include the full DSN here (and not the public one) (github.com/getsentry/raven-python/issues/569)
key = b64decode("NmMxNDFkMzA4YjIwNDEzZDk3NmFhZTBiYTZjNGE4ZDM6"
                "MWM2ZmY5NDIxN2ZhNDYyMGExMjIwZmNjNmQyMWE0NGQ=")
client = Client(dsn='https://{}@sentry.io/105644'.format(key), release=__version__)
client.extra_context({'platform': platform.platform()})


def resource_path(relative_path):
    """
    Get path to resource when running in PyInstaller package or otherwise
    """
    try:
        return os.path.join(sys._MEIPASS, relative_path)
    except AttributeError:
        return resource_filename('onecodex_uploader', relative_path)


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
            client.capture_breadcrumb(message='Dropped something on the FileViewer')
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                self.file_dropped.emit(str(url.toLocalFile()))
        else:
            event.ignore()


class FileListModel(QtCore.QAbstractListModel):
    def __init__(self, parent=None):
        super(FileListModel, self).__init__(parent)
        self.parent = parent
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
            QtGui.QMessageBox.critical(self.parent, 'Error!', qc_results['msg'],
                                       QtGui.QMessageBox.Abort)
            return
        elif qc_results['seq_type'] == 'aa':
            QtGui.QMessageBox.critical(self.parent, 'Error!',
                                       'Amino acid FASTX files not supported',
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


class OCWorker(QtCore.QThread):
    upload_progress = QtCore.Signal(str, float)
    upload_finished = QtCore.Signal(str)

    def __init__(self, filename, apikey):
        QtCore.QThread.__init__(self)
        self.filename = filename
        self.apikey = apikey

    def run(self):
        try:
            upload_file(self.filename, self.apikey, OC_SERVER, self.upload_progress.emit)
            self.upload_finished.emit('')
        except UploadException as e:
            self.upload_finished.emit(str(e))
            client.captureMessage(str(e))
        except:
            client.captureException()


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
        icon = QtGui.QIcon()
        icon.addFile(resource_path('icons/mac_logo.iconset/icon_16x16.png'), QtCore.QSize(16, 16))
        icon.addFile(resource_path('icons/mac_logo.iconset/icon_32x32.png'), QtCore.QSize(32, 32))
        icon.addFile(resource_path('icons/mac_logo.iconset/icon_128x128.png'),
                     QtCore.QSize(128, 128))
        icon.addFile(resource_path('icons/mac_logo.iconset/icon_512x512.png'),
                     QtCore.QSize(512, 512))
        self.setWindowIcon(icon)
        icon = QtGui.QPixmap(resource_path('icons/plain_logo.png'))
        self.ui.logoLabel.setPixmap(icon.scaled(64, 64))

        # set up the file list
        self.files_model = FileListModel(self)
        view = FileViewer(self)
        view.setModel(self.files_model)
        view.file_dropped.connect(self.files_model.add_file)
        self.ui.fileListLayout.addWidget(view)

        # set up the ui
        self.ui.fileButton.clicked.connect(self.select_file_button)
        self.ui.uploadButton.clicked.connect(self.upload_button)
        self.reset()

        # set some globals
        self.lock = QtCore.QMutex()
        self.worker = None

        # version check
        should_quit, error_msg = check_version(__version__, OC_SERVER, 'gui')
        if error_msg is not None:
            QtGui.QMessageBox.warning(self, 'Error!', error_msg, QtGui.QMessageBox.Ok)
        if should_quit:
            QtGui.QApplication.instance().quit()

    def upload_button(self):
        client.capture_breadcrumb(message='Clicked Upload')
        self.ui.fileButton.hide()
        self.ui.uploadButton.setEnabled(False)
        self.ui.usernameField.setEnabled(False)
        self.ui.passwordField.setEnabled(False)

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
        self.ui.uploadProgress.setRange(0, 400)
        QtGui.QApplication.instance().processEvents()

        if apikey is None or apikey.strip() == '':
            # apikey is None is username/password failed, apikey == '' if user has no apikey
            QtGui.QMessageBox.critical(self, 'Error!', 'Could not authenticate successfully.',
                                       QtGui.QMessageBox.Abort)
        elif len(self.files_model.file_names) == 0:
            QtGui.QMessageBox.critical(self, 'Error!', 'No file selected.', QtGui.QMessageBox.Abort)
        else:
            client.user_context({'username': username})
            filename = self.files_model.file_names[0]
            self.worker = OCWorker(filename, apikey)
            self.worker.upload_progress.connect(self.upload_progress)
            self.worker.upload_finished.connect(self.upload_finished)
            self.worker.setTerminationEnabled(True)
            self.worker.start()

    def select_file_button(self):
        client.capture_breadcrumb(message='Clicked Select File')
        open_dialog = QtGui.QFileDialog()
        open_dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
        if platform.system() == 'Windows':
            options = QtGui.QFileDialog.DontUseNativeDialog
        else:
            options = 0

        name = open_dialog.getOpenFileName(self, 'Upload File', '', 'Sequencing File (*.*)',
                                           options=options)

        if name[0] != '':
            self.files_model.add_file(name[0])

    def upload_progress(self, filename, progress):
        # TODO: use filename to upload progress bar directly in QListView (for multiple files)
        if self.lock.tryLock():
            self.ui.uploadProgress.setValue(int(400 * progress))
            QtGui.QApplication.instance().processEvents()
            self.lock.unlock()

    def upload_finished(self, msg):
        if msg == '':
            QtGui.QMessageBox.information(self, 'Success!', 'File uploaded successfully')
            self.files_model.reset()
        else:
            QtGui.QMessageBox.critical(self, 'Error!', msg, QtGui.QMessageBox.Abort)
        self.reset()

    def reset(self):
        self.ui.fileButton.show()
        self.ui.uploadProgress.hide()
        self.ui.uploadProgress.setRange(0, 400)
        self.ui.uploadProgress.reset()
        self.ui.uploadButton.setEnabled(True)
        self.ui.usernameField.setEnabled(True)
        self.ui.passwordField.setEnabled(True)

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            q_msg = 'Upload in progress; are you sure you want to quit?'
            quit = QtGui.QMessageBox.question(self, 'Warning!', q_msg,
                                              QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if quit == QtGui.QMessageBox.Yes:
                # nuke everything to stop boto from hanging up
                self.worker.terminate()
                os.kill(os.getpid(), 9)
                # the above is insane, but otherwise boto is literally unstopable and the user
                # has to force-quit the application itself; would love to find a better way!
                # event.accept()
            else:
                event.ignore()
        else:
            event.accept()
