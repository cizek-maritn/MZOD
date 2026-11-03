import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui
from pypylon import pylon
import numpy as np
import cv2

from cython_codes import c_pixel_sum
from time import perf_counter


class Lab02T(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 02T - byerova maska without camera'

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
        cat = self.bayer_rggb(self.load_image('test_pictures/bayer_cat.png'))
        self.image = MSnippets.MZODImageWidget(QtGui.QPixmap.fromImage(cat))
        self.grid_layout.addWidget(self.image, 3, 0)

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
    # every 2x2 superpixel R G / G B becomes one color pixel -> half resolution RGB image
    def bayer_rggb(self, grab_result):
        raw = self.to_array(grab_result)
        height, width = raw.shape[:2]
        raw = raw[:height - height % 2, :width - width % 2]

        r = raw[0::2, 0::2]
        g = ((raw[0::2, 1::2].astype(np.uint16) + raw[1::2, 0::2]) // 2).astype(np.uint8)
        b = raw[1::2, 1::2]

        # array_to_QImage expects BGR
        bgr_array = np.dstack((b, g, r))

        q_image = self.array_to_QImage(bgr_array)
        return q_image

    def process_image(self, grab_result):
        raw_array = self.to_array(grab_result)
        #self.camera.converter.OutputPixelFormat = pylon.PixelType_Mono8
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

        
        

        height, width = converted_array.shape[:2]

        superpixel_array = converted_array[:height - height % 2,
                                            :width - width % 2]

        superpixel_array = superpixel_array.reshape(
            height // 2,
            2,
            width // 2,
            2
        ).mean(axis=(1, 3))

        q_image = self.array_to_QImage(superpixel_array)
        self.image.load_pixmap(QtGui.QPixmap(q_image))
