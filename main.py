import cv2
import numpy as np

from MZODQtSnippets import MZODImageWidget, MZODLabelComboBox
from MZODCam import MZODCam
from MZODTabTemplate import MZODTabTemplate
import json
import os
import sys
import time
import traceback
from PyQt5 import QtGui, QtCore, QtWidgets

from lab01 import Lab01
from lab00 import Lab00
from lab02 import Lab02
from lab01ours import Lab01Ours


class MZODWindow(QtWidgets.QMainWindow):
    # upper limit of the trigger rate
    MAX_FPS = 60

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

        # load default settings
        self.default_settings = {
            'camera': None
        }
        settings = self.load_settings()
        self.settings = settings if settings else self.default_settings

        self.central_widget = None
        self.grid_layout = None
        self.combo_box_cameras = None

        self.button_connect = None

        self.ref_pixmap = None
        self.gb_image = None
        self.image = None

        # list of camera names
        self.cameras = None
        # camera wrapper
        self.camera = MZODCam()

        # tabs
        self.tabs = None

        # trigger loop: next trigger follows the end of the previous task, but not faster than MAX_FPS
        self.grabbing = False
        self.loop_id = 0

    # create all controls here
    def setup_ui(self):
        self.resize(1200, 800)
        self.central_widget = QtWidgets.QWidget(self)
        self.grid_layout = QtWidgets.QGridLayout(self.central_widget)

        # camera select box
        self.cameras = self.camera.get_available_cameras()
        self.combo_box_cameras = MZODLabelComboBox(text='Available Cameras', items=self.cameras)
        # preselects already known camera
        if self.settings['camera'] in self.cameras:
            self.combo_box_cameras.setCurrentText(self.settings['camera'])
        self.grid_layout.addWidget(self.combo_box_cameras, 0, 0, 1, 1)

        # camera connect button
        self.button_connect = QtWidgets.QPushButton(self)
        self.button_connect.setText('Connect')
        self.grid_layout.addWidget(self.button_connect, 0, 1, 1, 1)
        self.button_connect.clicked.connect(self.cam_connect)

        # tabs - add your tabs here (see MZODTabTemplate.py)
        self.tabs = QtWidgets.QTabWidget(self)
        self.add_tab(Lab00(self.camera, self.tabs))
        self.add_tab(Lab01(self.camera, self.tabs))
        self.add_tab(Lab02(self.camera, self.tabs))
        self.add_tab(Lab01Ours(self.camera, self.tabs))
        self.grid_layout.addWidget(self.tabs, 1, 0, 1, 2)
        self.setCentralWidget(self.central_widget)

    # adds tab to the tab widget
    def add_tab(self, tab):
        self.tabs.addTab(tab, tab.title)

    # load app "settings"
    @staticmethod
    def load_settings():
        if os.path.exists('settings.json'):
            try:
                with open('settings.json', 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(e)
        return None

    # save settings
    def save_settings(self):
        try:
            with open('settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(e)

    # connects to the camera / disconnects when already connected
    def cam_connect(self):
        if self.camera.is_connected:
            self.cam_stop()
            self.camera.disconnect()
            self.button_connect.setText('Connect')
            if self.image is not None:
                self.image.load_pixmap(self.ref_pixmap)
            return
        if self.combo_box_cameras.currentIndex() >= 0:
            self.camera.connect(self.combo_box_cameras.currentText())

            # let the selected tab react to the connection
            tab = self.tabs.currentWidget()
            if tab is not None:
                try:
                    tab.after_connection()
                except Exception:
                    traceback.print_exc()

            # start the trigger loop
            self.grabbing = True
            self.loop_id += 1
            loop_id = self.loop_id
            QtCore.QTimer.singleShot(0, lambda: self.cam_grab(loop_id))
            self.button_connect.setText('Disconnect')

    # stops the trigger loop and camera grabbing
    def cam_stop(self):
        # pending scheduled cam_grab call returns immediately when grabbing is False
        self.grabbing = False
        self.camera.stop()

    # schedules next cam_grab: right after the previous task is finished,
    # but not sooner than 1/MAX_FPS since the last trigger
    def schedule_next_grab(self, loop_id):
        if not self.grabbing or loop_id != self.loop_id:
            return
        remaining = 1.0 / self.MAX_FPS - (time.perf_counter() - self.camera.last_trigger_time)
        QtCore.QTimer.singleShot(max(0, int(remaining * 1000 + 0.999)), lambda: self.cam_grab(loop_id))

    # grab frame from camera, let the selected tab process it and display the result.
    # the next call is scheduled once everything above is finished
    def cam_grab(self, loop_id):
        # stale calls scheduled before a disconnect/reconnect are dropped
        if not self.grabbing or not self.camera.is_connected or loop_id != self.loop_id:
            return
        try:
            # trigger/grab
            grab_result = self.camera.trigger()
            if grab_result is not None:
                try:
                    tab = self.tabs.currentWidget()
                    tab.process_image(grab_result) if tab is not None else None
                finally:
                    grab_result.Release()
        except Exception:
            traceback.print_exc()
        finally:
            self.schedule_next_grab(loop_id)

    # on close
    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.cam_stop()
        self.camera.disconnect()
        if self.combo_box_cameras.currentIndex() >= 0:
            self.settings['camera'] = self.combo_box_cameras.currentText()
        self.save_settings()
        a0.accept()


class MZCAMApp:
    def __init__(self, argv):
        self.app = QtWidgets.QApplication(argv)
        self.app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        self.ui = MZODWindow()
        self.ui.setup_ui()

    def run(self):
        self.ui.show()
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    MZCAMgui = MZCAMApp(sys.argv)
    MZCAMgui.run()
