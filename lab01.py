import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui
from pypylon import pylon
import numpy as np

from cython_codes import c_pixel_sum
from time import perf_counter

class Lab01(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 01 - controlling the camera'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.pixel_format = None
        self.image = None
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 2, 0)

        self.image = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(self.image, 3, 0)

        img2 = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(img2, 4, 0)

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
        raw_array = self.to_array(grab_result)
        self.camera.converter.OutputPixelFormat = pylon.PixelType_Mono8
        converted_array = self.convert(grab_result)
        # time0 = perf_counter()
        # E_cython = c_pixel_sum(converted_array)
        # time1 = perf_counter()
        # E_numpy = np.sum(converted_array)
        # time2 = perf_counter()
        # E_python = 0;
        # for i in range(converted_array.shape[0]):
        #     for j in range(converted_array.shape[1]):
        #         E_python += converted_array[i, j]
        # time3 = perf_counter()

        #print(f'cython: {time1 - time0}, {E_cython}')
        #print(f'np.sum: {time2 - time1}, {E_numpy}')
        #print(f'python: {time3 - time2}, {E_python}')
        # if AE:
            # E < Te
            # exposure ++
            # else
            # exposure --

        q_image = self.array_to_QImage(converted_array)
        self.image.load_pixmap(QtGui.QPixmap(q_image))
