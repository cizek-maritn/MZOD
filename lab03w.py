import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui, QtWidgets
from pypylon import pylon
import numpy as np
import cv2

from cython_codes import c_pixel_sum
from time import perf_counter


class Lab03w(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 03 - white'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.pixel_format = None
        # average white per pixel measured by the button, None until measured
        self.white = None
        self.white_button = None
        self.white_label = None
        # slider with target value, read with self.target.value()
        self.target = None
        self.image = None
        # test image shown without camera
        self.test_image = None
        # copy of the last frame (raw array), used by the white button
        self.last_frame = None
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 2, 0)

        self.white_button = QtWidgets.QPushButton('Measure white', self.content)
        self.white_button.clicked.connect(self.measure_white)
        self.grid_layout.addWidget(self.white_button, 3, 0)
        self.white_label = QtWidgets.QLabel('White: not measured', self.content)
        self.grid_layout.addWidget(self.white_label, 3, 1)

        self.target = MSnippets.MZODLabelSpinSlider('Target value', 0, 255, 230, parent=self.content)
        self.grid_layout.addWidget(self.target, 4, 0, 1, 2)

        self.image = MSnippets.MZODImageWidget()
        self.grid_layout.addWidget(self.image, 5, 0, 1, 2)
        if self.test_image is not None:
            self.last_frame = self.to_array(self.test_image).copy()
            self.show_frame()
        self.target.valueChanged.connect(lambda _: self.show_frame())

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
        # bayer_rggb needs raw RGGB mosaic
        if formats and 'BayerRG8' in formats:
            self.camera.set_param('PixelFormat', 'BayerRG8')
        self.pixel_format.clear()
        self.pixel_format.addItems(formats)
        self.pixel_format.setCurrentText('BayerRG8' if 'BayerRG8' in formats else self.camera.get_param('PixelFormat'))
        self.pixel_format.currentIndexChanged.connect(
            lambda _: self.camera.set_param('PixelFormat', self.pixel_format.currentText()))
    # testing without camera: loads raw bayer mosaic from path and returns it as pylon image,
    # so it can be used the same way as grab result from the camera
    def load_image(self, path, pixel_type=pylon.PixelType_BayerRG8):
        array = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if array is None:
            raise FileNotFoundError(f'Could not load image: {path}')
        attached = pylon.PylonImage()
        attached.AttachArray(array, pixel_type)
        # copy, so the image owns its buffer
        image = pylon.PylonImage()
        image.CopyImage(attached)
        return image

    # expects grab result from the camera (or pylon image from load_image) with raw RGGB bayer mosaic
    # every 2x2 superpixel R G / G B becomes one color pixel -> half resolution BGR array

    # multiplies array by constant target / measured white, so the measured white becomes target
    # returns array unchanged until white is measured
    def white_level(self, array):
        if not self.white:
            return array
        constant = self.target.value() / self.white
        return np.clip(array * constant, 0, 255).astype(np.uint8)



    # takes the current picture and saves its average value per pixel into self.white
    def measure_white(self):
        if self.last_frame is None:
            self.white_label.setText('White: no picture yet')
            return
        self.white = float(np.mean(self.last_frame))
        self.white_label.setText(f'White: {self.white:.2f}')
        self.show_frame()

    # displays last frame after white level
    def show_frame(self):
        if self.last_frame is None:
            return
        self.image.load_pixmap(QtGui.QPixmap.fromImage(self.array_to_QImage(self.white_level(self.last_frame))))

    def process_image(self, grab_result):
        #self.camera.converter.OutputPixelFormat = pylon.PixelType_Mono8

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

        # grab result is released after this method, so keep a copy
        self.last_frame = self.to_array(grab_result).copy()
        self.show_frame()
