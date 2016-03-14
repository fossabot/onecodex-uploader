Introduction
------------

onecodex_uploader is a GUI frontend to allow users to easily upload large files
to One Codex without having to use the command-line client (currently, the web
client only allows uploads of <5 Gb).


Installation
------------

    # first install pyside and qt with one of the following commands
    brew install pyside pyside-tools qt
    sudo apt-get install pyside # FIXME
    
    # then set up the virtual environment
    virtualenv --system-site-packages venv -p python2
    pip install --ignore-installed -r requirements.txt

    # finally build the mac or pc application
    pyinstaller mac.spec
    pyinstaller pc.spec
