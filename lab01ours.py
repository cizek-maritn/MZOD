import MZODTabTemplate
import MZODQtSnippets as MSnippets
from PyQt5 import QtGui


class Lab01Ours(MZODTabTemplate.MZODTabTemplate):
    title = 'Lab 01 - controlling the camera'

    def __init__(self, camera, parent=None):
        self.exposure = None
        self.exposure_methods = None
        self.exposure_auto = None
        self.pixel_format = None
        self.image = None
        super().__init__(camera, parent)

    def setup_ui(self):
        self.exposure = MSnippets.MZODLabelSpinSliderDouble('ExposureTime', 100, 10000, 1000, parent=self.content)
        self.grid_layout.addWidget(self.exposure, 0, 0)

        self.exposure_methods = MSnippets.MZODLabelComboBox('Exposure Methods', [], parent=self.content)
        self.grid_layout.addWidget(self.exposure_methods, 1, 0)

        self.exposure_auto = MSnippets.MZODLabelCheckBox('Exposure Auto', parent=self.content)
        self.grid_layout.addWidget(self.exposure_auto, 2, 0)

        self.exposure_auto_target = MSnippets.MZODLabelSpinSliderDouble('Exposure Auto Target', minimum=0.01, maximum=1.0, value=0.1, step=0.01, parent=self.content)
        self.grid_layout.addWidget(self.exposure_auto_target, 2, 1)

        self.pixel_format = MSnippets.MZODLabelComboBox('Pixel Format', [], parent=self.content)
        self.grid_layout.addWidget(self.pixel_format, 3, 0)

        self.image = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(self.image, 4, 0)

        img2 = MSnippets.MZODImageWidget(QtGui.QPixmap('micro.png'))
        self.grid_layout.addWidget(img2, 5, 0)

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
        converted_array = self.convert(grab_result)

        if self.exposure_auto.isChecked():
            img_energy = converted_array.sum() / converted_array.size
            img_energy_normalized = img_energy / 255.0
            if img_energy_normalized < self.exposure_auto_target.value():
                new_exposure_coef = self.exposure_auto_target.value() - img_energy_normalized
                new_exposure = self.exposure.value() * (new_exposure_coef + 1)
                self.exposure.setValue(new_exposure)
            elif img_energy_normalized > self.exposure_auto_target.value():
                new_exposure_coef = img_energy_normalized - self.exposure_auto_target.value()
                new_exposure = self.exposure.value() / (new_exposure_coef + 1)
                self.exposure.setValue(new_exposure)

        q_image = self.array_to_QImage(converted_array)
        self.image.load_pixmap(QtGui.QPixmap(q_image))
        #print(f'slider value: {self.exposure_auto_target.value()}')
        #print(f'image energy: {img_energy}')