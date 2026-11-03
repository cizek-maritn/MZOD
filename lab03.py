import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui
from pypylon import pylon
import numpy as np
import cv2

from cython_codes import c_pixel_sum
from time import perf_counter


class Lab03(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 03 - cerna'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.pixel_format = None
        self.black = None
        self.black_to_value = None
        self.image = None
        # test image shown without camera
        self.test_image = None
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 2, 0)

        self.black = MSnippets.MZODLabelSpinSlider('Black value', 0, 255, 0, parent=self.content)
        self.grid_layout.addWidget(self.black, 3, 0)

        # checked: pixels lower than black are set to black, unchecked: set to zero
        self.black_to_value = MSnippets.MZODLabelCheckBox('Set to black value (else 0)', False, parent=self.content)
        self.grid_layout.addWidget(self.black_to_value, 4, 0)

        self.image = MSnippets.MZODImageWidget()
        self.grid_layout.addWidget(self.image, 5, 0)
        # without camera re-render the test image, with camera the next frame uses the new value
        self.black.valueChanged.connect(lambda _: self.show_test_image())
        self.black_to_value.stateChanged.connect(lambda _: self.show_test_image())

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

    # if any color of a pixel is lower than black, all colors of that pixel are set
    # to black (to_value=True) or to zero (to_value=False)
    # pixel is HxWx3 color pixel, or 2x2 superpixel R G / G B of raw bayer mosaic (HxW)
    def black_min(self, array, black, to_value=False):
        result = array.copy()
        new_value = np.uint8(black) if to_value else 0
        if array.ndim == 3:
            mask = (array < black).any(axis=2)
            result[mask] = new_value
        else:
            height, width = array.shape
            # view of the even part, so the changes go to result
            blocks = result[:height - height % 2, :width - width % 2].reshape(height // 2, 2, width // 2, 2)
            mask = (blocks < black).any(axis=(1, 3))
            blocks[mask[:, None, :, None].repeat(2, axis=1).repeat(2, axis=3)] = new_value
        return result

    # bayer -> RGB -> black min, returns QImage
    def render(self, grab_result):
        array = self.black_min(self.to_array(grab_result), self.black.value(), self.black_to_value.isChecked())
        return self.array_to_QImage(array)

    def show_test_image(self):
        if not self.camera.is_connected and self.test_image is not None:
            self.image.load_pixmap(QtGui.QPixmap.fromImage(self.render(self.test_image)))

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

        self.image.load_pixmap(QtGui.QPixmap.fromImage(self.render(grab_result)))
