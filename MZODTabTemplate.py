from PyQt5 import QtCore, QtWidgets, QtGui
import numpy as np


# scroll area content that never gets squeezed vertically below the height its layout asks for,
# so the scroll area shows the vertical scrollbar instead
class _MZODTabContent(QtWidgets.QWidget):
    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        if self.layout() is not None:
            hint.setHeight(max(hint.height(), self.layout().sizeHint().height()))
        return hint


class MZODTabTemplate(QtWidgets.QWidget):
    """Template for a tutorial tab.
    The main window calls `process_image` for the currently selected tab only,
    once per acquired frame.
    """

    # text shown on the tab header
    title = 'Template'

    def __init__(self, camera, parent=None):
        super().__init__(parent)
        # MZODCam shared with the main window, use it to set the camera up (e.g. self.camera.set_param(...))
        self.camera = camera

        # the tab is vertically scrollable: controls live in `self.content` placed in a scroll area
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.content = _MZODTabContent(self.scroll_area)
        self.scroll_area.setWidget(self.content)
        outer_layout.addWidget(self.scroll_area)

        self.grid_layout = QtWidgets.QGridLayout(self.content)
        # widgets stay on top when the tab is taller than they need
        self.grid_layout.setAlignment(QtCore.Qt.AlignTop)
        self.setup_ui()

    # create your controls here, e.g.:
    #   self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self.content)
    #   self.grid_layout.addWidget(self.slider, 0, 0, 1, 1)
    def setup_ui(self):
        pass

    # called by the main window right after the camera is connected (and before the first frame is grabbed)
    # use it to read/set camera parameters, e.g. to initialize controls from the camera:
    #   self.exposure.setValue(int(self.camera.get_param('ExposureTime')))
    def after_connection(self):
        pass

    def array_to_QImage(self, frame):
        frame = np.ascontiguousarray(frame)
        height, width = frame.shape[:2]
        if frame.ndim == 2:
            q_img = QtGui.QImage(frame.data, width, height, width, QtGui.QImage.Format_Grayscale8).copy()
        else:
            q_img = QtGui.QImage(frame.data, width, height, 3 * width, QtGui.QImage.Format_RGB888).rgbSwapped()
        return q_img

    # converts pylon grab result to numpy array. Pixel Format of the camera is used
    def to_array(self, grab_result):
        return grab_result.GetArray()

    # converts pylon grab_result to numpy array. Converters format is used (BGR default)
    def convert(self, grab_result):
        return self.camera.convert(grab_result)

    # receives pylon grab result (already checked with GrabSucceeded) from the main window.
    # return numpy array (HxW grayscale uint8 or HxWx3 BGR uint8) to be displayed in the main window,
    # or None to display the unprocessed camera frame.
    def process_image(self, grab_result):
        pass
