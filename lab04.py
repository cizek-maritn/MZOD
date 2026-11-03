import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui
from pypylon import pylon
import numpy as np
import cv2 as cv

from cython_codes import c_pixel_sum
from time import perf_counter

class Lab04(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 04 - calibration'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.pixel_format = None
        self.image = None
        self.screenshots = []
        self.camera_matrix = None
        self.distortion_coefficients = None
        self.new_camera_matrix = None
        self.calibration_size = None
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 2, 0)

        self.button_label = MSnippets.MZODLabelWidget('Lab 04 - Calibration', parent=self.content)
        self.grid_layout.addWidget(self.button_label, 3, 0)

        self.screenshot_button = MSnippets.MZODPushButton('Take Screenshot', parent=self.content)
        self.grid_layout.addWidget(self.screenshot_button, 3, 1)
        self.screenshot_button.clicked.connect(self.take_screenshot)

        self.calibration_button = MSnippets.MZODPushButton('Calibrate', parent=self.content)
        self.grid_layout.addWidget(self.calibration_button, 3, 2)
        self.calibration_button.clicked.connect(self.calibrate)

        self.image = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(self.image, 4, 0)

        self.chessboard_image = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(self.chessboard_image, 5, 0)

        self.calibrated_image = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(self.calibrated_image, 5, 1)

    def take_screenshot(self):
        pixmap = self.image.pixmap
        if pixmap is not None and not pixmap.isNull():
            image = pixmap.toImage().convertToFormat(QtGui.QImage.Format_RGB888)
            self.screenshots.append(self._qimage_to_array(image))
            print(f'Screenshot taken. Total screenshots: {len(self.screenshots)}')
        else:
            print('No image to take a screenshot of.')

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

    def calibrate(self):
        print('Calibration started.')
        # termination criteria
        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
 
        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
        objp = np.zeros((6*7,3), np.float32)
        objp[:,:2] = np.mgrid[0:7,0:6].T.reshape(-1,2)
 
        # Arrays to store object points and image points from all the images.
        objpoints = [] # 3d point in real world space
        imgpoints = [] # 2d points in image plane.
 
        # Loop through the images and find the chessboard corners
        # Replace 'images' with the actual list of image files
        for img in self.screenshots:
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
 
            # Find the chess board corners
            ret, corners = cv.findChessboardCorners(gray, (7,6), None)
 
            # If found, add object points, image points (after refining them)
            if ret == True:
                objpoints.append(objp)
 
                corners2 = cv.cornerSubPix(gray,corners, (11,11), (-1,-1), criteria)
                imgpoints.append(corners2)
 
                # Draw and display the corners
                copy = img.copy()
                cv.drawChessboardCorners(copy, (7,6), corners2, ret)
                self.chessboard_image.load_pixmap(
                    QtGui.QPixmap.fromImage(self.array_to_QImage(copy)))

        if not objpoints:
            print('Calibration failed: no chessboard corners found.')
            return

        image_size = self.screenshots[0].shape[1::-1]
        ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(
            objpoints, imgpoints, image_size, None, None)
        if not ret:
            print('Calibration failed.')
            return

        self.camera_matrix = mtx
        self.distortion_coefficients = dist
        self.calibration_size = image_size
        img = self.screenshots[-1]
        h, w = img.shape[:2]
        self.new_camera_matrix, roi = cv.getOptimalNewCameraMatrix(
            mtx, dist, (w, h), 1, (w, h))
        dst = self._undistort_frame(img)
        x, y, w, h = roi
        if w > 0 and h > 0:
            dst = dst[y:y + h, x:x + w]
        self.calibrated_image.load_pixmap(
            QtGui.QPixmap.fromImage(self.array_to_QImage(dst)))
        print(f'Calibration complete using {len(objpoints)} screenshot(s).')

    def _undistort_frame(self, frame):
        if self.camera_matrix is None or self.distortion_coefficients is None:
            return frame

        height, width = frame.shape[:2]
        if self.calibration_size == (width, height):
            new_camera_matrix = self.new_camera_matrix
        else:
            new_camera_matrix, _ = cv.getOptimalNewCameraMatrix(
                self.camera_matrix, self.distortion_coefficients,
                (width, height), 1, (width, height))
        return cv.undistort(
            frame, self.camera_matrix, self.distortion_coefficients,
            None, new_camera_matrix)

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
        converted_array = self._undistort_frame(converted_array)
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
