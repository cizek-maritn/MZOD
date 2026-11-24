import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui
from pypylon import pylon
import numpy as np
import cv2 as cv

from cython_codes import c_pixel_sum
from time import perf_counter

class Lab05(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 05 - image focusing'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.pixel_format = None
        self.image = None
        self.focusing_label = None
        self.previous_focus_measure = None
        self.current_focus_measure = None
        self.check_focus_time_interval = 1.0  # seconds
        self.last_focus_check_time = perf_counter()
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 2, 0)

        self.focusing_label = MSnippets.MZODLabelWidget('Lab 05 - Image Focusing', parent=self.content)
        self.grid_layout.addWidget(self.focusing_label, 3, 0)

        self.image = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(self.image, 4, 0)

    @staticmethod
    def _qimage_to_array(image):
        image = image.convertToFormat(QtGui.QImage.Format_RGB888)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        data = image.bits()
        data.setsize(image.byteCount())
        array = np.frombuffer(data, dtype=np.uint8).reshape((height, bytes_per_line))
        return array[:, :width * 3].reshape((height, width, 3)).copy()

    def array_to_QImage(self, array):
        if array.ndim == 2:
            height, width = array.shape
            q_image = QtGui.QImage(
                array.data, width, height, width, QtGui.QImage.Format_Grayscale8)
            return q_image.copy()

        height, width = array.shape[:2]
        bytes_per_line = 3 * width
        q_image = QtGui.QImage(array.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
        return q_image

    def focus_measure_by_contrast(self, image):
        if image.ndim == 2:
            gray = image
        elif image.ndim == 3 and image.shape[2] == 1:
            gray = image[:, :, 0]
        else:
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

        laplacian = cv.Laplacian(gray, cv.CV_64F)
        contrast_measure = np.var(laplacian)
        return contrast_measure

    def after_connection(self):
        super().after_connection()
        exposure_bounds = self.camera.get_bounds('ExposureTime')
        self.exposure.setRange(exposure_bounds)
        self.exposure.setValue(int(self.camera.get_param('ExposureTime')))
        self.exposure.valueChanged.connect(lambda v: self.camera.set_param('ExposureTime', v))

        methods = self.camera.get_bounds('ExposureAuto')
        self.exposure_methods.clear()
        self.exposure_methods.addItems(methods)
        self.exposure_methods.setCurrentText(self.camera.get_param('ExposureAuto'))
        self.exposure_methods.currentIndexChanged.connect(
            lambda _: self.camera.set_param('ExposureAuto', self.exposure_methods.currentText()))

        formats = self.camera.get_bounds('PixelFormat')
        self.pixel_format.clear()
        self.pixel_format.addItems(formats)
        self.pixel_format.setCurrentText(self.camera.get_param('PixelFormat'))
        self.pixel_format.currentIndexChanged.connect(
            lambda _: self.camera.set_param('PixelFormat', self.pixel_format.currentText()))

    def process_image(self, grab_result):
        self.camera.converter.OutputPixelFormat = pylon.PixelType_Mono8
        converted_array = self.convert(grab_result)
        self.current_focus_measure = self.focus_measure_by_contrast(converted_array)

        if perf_counter() - self.last_focus_check_time >= self.check_focus_time_interval:
            self.last_focus_check_time = perf_counter()
            if self.previous_focus_measure is not None:
                if self.current_focus_measure > self.previous_focus_measure:
                    self.focusing_label.SetLabel(f'Focusing: Improving (Focus Measure: {self.current_focus_measure:.2f})')
                elif self.current_focus_measure < self.previous_focus_measure:
                    self.focusing_label.SetLabel(f'Focusing: Worsening (Focus Measure: {self.current_focus_measure:.2f})')
                else:
                    self.focusing_label.SetLabel(f'Focusing: No Change (Focus Measure: {self.current_focus_measure:.2f})')

            self.previous_focus_measure = self.current_focus_measure

        q_image = self.array_to_QImage(converted_array)
        self.image.load_pixmap(QtGui.QPixmap(q_image))