"""This script is passed to LibreOffice python interpreter to be executed."""
""" System Requirements
    sudo aptitude install -y libreoffice libreoffice-script-provider-python uno-libs3 python3-uno 
"""
import sys
import os
import platform
import subprocess
import time
import atexit
import socket
import uno
import argparse
from urllib.parse import urlparse
import pathlib

# print("Executing LibreOffice python script using LibreOffice python")
OPENOFFICE_PORT = 8100 # 2002

if 'Linux' in platform.system():
    OPENOFFICE_BIN     = "soffice"
else:
    OPENOFFICE_PATH    = os.environ["LIBREOFFICE_PROGRAM"]
    OPENOFFICE_BIN     = os.path.join(OPENOFFICE_PATH, 'soffice')

NoConnectException = uno.getClass("com.sun.star.connection.NoConnectException")
PropertyValue = uno.getClass("com.sun.star.beans.PropertyValue")


# Adapted from: https://www.linuxjournal.com/content/starting-stopping-and-connecting-openoffice-python
class OORunner:
    """
    Start, stop, and connect to OpenOffice.
    """
    def __init__(self, port=OPENOFFICE_PORT):
        """ Create OORunner that connects on the specified port. """
        self.port = port


    def connect(self, no_startup=False):
        """
        Connect to OpenOffice.
        If a connection cannot be established try to start OpenOffice.
        """
        print("Connecting to LibreOffice at port {}".format(self.port))
        localContext = uno.getComponentContext()
        resolver     = localContext.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", localContext)
        context      = None
        did_start    = False

        n = 0
        while n < 6:
            try:
                context = resolver.resolve("uno:socket,host=localhost,port=%d;urp;StarOffice.ComponentContext" % self.port)
                break
            except NoConnectException as e:
                print("Exception occured : ",e)

            # If first connect failed then try starting OpenOffice.
            if n == 0:
                print("Failed to connect. Trying to start LibreOffice instance.")
                # Exit loop if startup not desired.
                if no_startup:
                     break
                self.startup()
                did_start = True

            # Pause and try again to connect
            time.sleep(1)
            n += 1

        if not context:
            raise Exception("Failed to connect to LibreOffice on port %d" % self.port)

        desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        dispatcher = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", context)

        if not desktop:
            raise Exception("Failed to create LibreOffice desktop on port %d" % self.port)

        if did_start:
            _started_desktops[self.port] = desktop

        return desktop, dispatcher


    def startup(self):
        """
        Start a headless instance of OpenOffice.
        """
        print("Starting headless LibreOffice")

        try:
            pid = subprocess.Popen([OPENOFFICE_BIN, '--norestore', '--nofirststartwizard', '--nologo', '--headless', '--invisible', '--accept=socket,host=localhost,port=%d;urp;' % self.port]).pid
        except Exception as e:
            raise Exception("Failed to start LibreOffice on port %d: %s" % (self.port, e.message))

        if pid <= 0:
            raise Exception("Failed to start LibreOffice on port %d" % self.port)

        print("LibreOffice started")


    def shutdown(self):
        """
        Shutdown OpenOffice.
        """
        print("Shutting down LibreOffice")
        try:
            if _started_desktops.get(self.port):
                print("Terminating instance at port {}".format(self.port))
                _started_desktops[self.port].terminate()
                del _started_desktops[self.port]
        except Exception as e:
            print("Exception occured : ", e)

# Keep track of started desktops and shut them down on exit.
_started_desktops = {}

def _shutdown_desktops():
    """ Shutdown all OpenOffice desktops that were started by the program. """
    for port, desktop in _started_desktops.items():
        print("Exit: Found instance found at port {}. Terminating...".format(port))
        try:
            if desktop:
                desktop.terminate()
        except Exception as e:
            print("Exception occured : ", e)


atexit.register(_shutdown_desktops)


def oo_shutdown_if_running(port=OPENOFFICE_PORT):
    """ Shutdown OpenOffice if it's running on the specified port. """
    oorunner = OORunner(port)
    try:
        desktop = oorunner.connect(no_startup=True)
        desktop.terminate()
    except Exception as e:
            print("Exception occured : ", e)


def run(source, update=False, pdf=False):
    fileurl = uno.systemPathToFileUrl(os.path.realpath(source))
    filepath, ext = os.path.splitext(source)
    fileurlpdf = uno.systemPathToFileUrl(os.path.realpath(filepath + ".pdf"))
    runner = OORunner(2002)
    desktop, dispatcher = runner.connect()

    print("Loading document")
    struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
    struct.Name = 'Hidden'
    struct.Value = True
    document = desktop.loadComponentFromURL(fileurl, "_default", 0, ([struct]))
    doc = document.getCurrentController()
 

    if update:
        print("Updating Indexes and Saving")
        dispatcher.executeDispatch(doc, ".uno:UpdateAllIndexes", "", 0, ())

        # Saving
        opts = []

        if ext == ".docx":
            struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
            struct.Name = "FilterName"
            struct.Value = "MS Word 2007 XML"
            opts.append(struct)

        struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        struct.Name = 'URL'
        struct.Value = fileurl
        opts.append(struct)

        dispatcher.executeDispatch(doc, ".uno:SaveAs", "", 0, tuple(opts))
    if pdf:
        try:
            print("Generating PDF")
            struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
            struct.Name = 'URL'
            struct.Value = fileurlpdf
            struct2 = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
            struct2.Name = "FilterName"
            struct2.Value = "writer_pdf_Export"
            dispatcher.executeDispatch(doc, ".uno:ExportDirectToPDF", "", 0, tuple([struct, struct2]))
        except Exception as e:
            print("error", e)

        runner.shutdown()
        return True
    runner.shutdown()


def run_S3(doc, update=False, pdf=False, base_path=''):
    fileurl = uno.systemPathToFileUrl(doc.read())
    source = urlparse(doc.url).path
    filepath, ext = os.path.splitext(source)
    
    runner = OORunner(2002)
    desktop, dispatcher = runner.connect()

    print("Loading document")
    struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
    struct.Name = 'Hidden'
    struct.Value = True
    print("________++++++++++++++++__________________")


    document = desktop.loadComponentFromURL(doc.read(), "_default", 0, ([struct]))
    doc = document.getCurrentController()
    
    print("________>>>>>>>>>>")
    if update:
        print("Updating Indexes and Saving")
        dispatcher.executeDispatch(doc, ".uno:UpdateAllIndexes", "", 0, ())

        # Saving
        opts = []

        if ext == ".docx":
            struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
            struct.Name = "FilterName"
            struct.Value = "MS Word 2007 XML"
            opts.append(struct)

        struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        struct.Name = 'URL'
        struct.Value = fileurl
        opts.append(struct)

        dispatcher.executeDispatch(doc, ".uno:SaveAs", "", 0, tuple(opts))
    if pdf:
        try:
            full_path = os.path.join(base_path, filepath)
            pathlib.Path(os.path.split(full_path)).mkdir(parents=True, exist_ok=True)
            print("Generating PDF")
            struct = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
            struct.Name = 'URL'
            struct.Value = uno.systemPathToFileUrl(os.path.realpath(full_path + ".pdf"))
            struct2 = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
            struct2.Name = "FilterName"
            struct2.Value = "writer_pdf_Export"
            dispatcher.executeDispatch(doc, ".uno:ExportDirectToPDF", "", 0, tuple([struct, struct2]))
        except Exception as e:
            print("error", e)

        runner.shutdown()
        return True
    runner.shutdown()

