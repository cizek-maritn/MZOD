import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui, QtWidgets
from pypylon import pylon
import numpy as np
import cv2

from cython_codes import c_pixel_sum
from time import perf_counter


class Lab04(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 04 corektion'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.pixel_format = None
        self.foto_button = None
        self.matrix_button = None
        self.status_label = None
        # frames saved by the button (raw arrays)
        self.frames = []
        # live image from the camera
        self.image = None
        # live image undistorted by the matrix, hidden until the matrix is computed
        self.undistorted_image = None
        # results of compute_matrix, None until computed
        self.camera_matrix = None
        self.dist_coeffs = None
        self.new_camera_matrix = None
        # pixel maps for cv2.remap, computing them once is much faster than cv2.undistort on every frame
        self.undistort_maps = None
        # test image shown without camera
        self.test_image = None
        # copy of the last frame (raw array), used by the button
        self.last_frame = None
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 2, 0)

        self.foto_button = QtWidgets.QPushButton('foto', self.content)
        self.foto_button.clicked.connect(self.save_frame)
        self.grid_layout.addWidget(self.foto_button, 3, 0)

        self.matrix_button = QtWidgets.QPushButton('compute matrix', self.content)
        self.matrix_button.clicked.connect(self.compute_matrix)
        self.grid_layout.addWidget(self.matrix_button, 3, 1)

        self.status_label = QtWidgets.QLabel('Frames: 0', self.content)
        self.grid_layout.addWidget(self.status_label, 4, 0, 1, 2)

        self.image = MSnippets.MZODImageWidget()
        self.grid_layout.addWidget(self.image, 5, 0, 1, 2)
        self.undistorted_image = MSnippets.MZODImageWidget()
        self.grid_layout.addWidget(self.undistorted_image, 6, 0, 1, 2)
        self.undistorted_image.hide()
        if self.test_image is not None:
            self.last_frame = self.to_array(self.test_image).copy()
            self.show_frame()

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

    # saves the current frame into self.frames
    def save_frame(self):
        if self.last_frame is None:
            return
        self.frames.append(self.last_frame)
        self.status_label.setText(f'Frames: {len(self.frames)}')

    # raw bayer mosaic (HxW) or color (HxWx3) array to HxW grayscale
    def to_gray(self, array):
        if array.ndim == 3:
            return cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(array, cv2.COLOR_BayerRGGB2GRAY)

    # displays last frame in the live image and, if there is a saved matrix, undistorted in the second image
    def show_frame(self):
        if self.last_frame is None:
            return
        self.image.load_pixmap(QtGui.QPixmap.fromImage(self.array_to_QImage(self.last_frame)))
        if self.undistort_maps is not None:
            undistorted = cv2.remap(self.to_gray(self.last_frame), *self.undistort_maps, cv2.INTER_LINEAR)
            self.undistorted_image.load_pixmap(QtGui.QPixmap.fromImage(self.array_to_QImage(undistorted)))

    # computes camera matrix from chessboard (7x8 inner corners) in saved frames and saves it
    # previous matrix is kept when it fails
    def compute_matrix(self):
        if not self.frames:
            self.status_label.setText('Frames: 0, take some fotos first')
            return

        # termination criteria
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        # fast check, so frames without chessboard do not freeze the program for long
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK

        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,7,0)
        objp = np.zeros((8 * 7, 3), np.float32)
        objp[:, :2] = np.mgrid[0:7, 0:8].T.reshape(-1, 2)

        # Arrays to store object points and image points from all the images.
        objpoints = []  # 3d point in real world space
        imgpoints = []  # 2d points in image plane.

        for frame in self.frames:
            gray = self.to_gray(frame)

            # Find the chess board corners
            ret, corners = cv2.findChessboardCorners(gray, (7, 8), flags=flags)

            # If found, add object points, image points (after refining them)
            if ret:
                objpoints.append(objp)

                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                imgpoints.append(corners2)

        if not objpoints:
            self.status_label.setText(f'Frames: {len(self.frames)}, chessboard not found in any of them')
            return

        h, w = gray.shape
        error, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, (w, h), None, None)
        newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))

        self.camera_matrix = mtx
        self.dist_coeffs = dist
        self.new_camera_matrix = newcameramtx
        self.undistort_maps = cv2.initUndistortRectifyMap(mtx, dist, None, newcameramtx, (w, h), cv2.CV_16SC2)

        self.status_label.setText(f'Frames: {len(self.frames)}, chessboard found in {len(objpoints)}, '
                                  f'reprojection error: {error:.3f} px')
        self.undistorted_image.show()
        self.show_frame()

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
