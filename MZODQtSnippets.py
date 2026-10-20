import os
import sys
import re
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QApplication, QGridLayout


# image with mouse wheel zoom (around the cursor) and left button drag panning.
# it grows with the image up to the space given by its layout (window width), then scrollbars appear.
class MZODImageWidget(QtWidgets.QScrollArea):
    MIN_SCALE = 0.05
    MAX_SCALE = 20.0
    ZOOM_STEP = 0.8

    def __init__(self, pixmap=None):
        QtWidgets.QScrollArea.__init__(self)
        self.scale = 1
        self.pixmap = None
        self._drag_pos = None
        self._last_hint = None

        self.label = QtWidgets.QLabel()
        self.setWidget(self.label)
        self.setWidgetResizable(False)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        # never larger than the image, but may shrink when there is not enough space
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        if pixmap is not None:
            self.load_pixmap(pixmap)

    def sizeHint(self):
        if self.pixmap is None:
            return super().sizeHint()
        frame = 2 * self.frameWidth()
        width = self.label.width() + frame
        height = self.label.height() + frame
        # room for scrollbars, so they do not make each other appear
        if self.horizontalScrollBar().maximum() > 0:
            height += self.horizontalScrollBar().sizeHint().height()
        if self.verticalScrollBar().maximum() > 0:
            width += self.verticalScrollBar().sizeHint().width()
        return QtCore.QSize(width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_geometry_if_needed()

    def _update_geometry_if_needed(self):
        hint = self.sizeHint()
        if hint != self._last_hint:
            self._last_hint = hint
            self.updateGeometry()

    def wheelEvent(self, event):
        if self.pixmap is None:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1 / self.ZOOM_STEP if delta > 0 else self.ZOOM_STEP
        new_scale = min(max(self.scale * factor, self.MIN_SCALE), self.MAX_SCALE)
        if new_scale == self.scale:
            return

        # keep the point under the cursor in place
        pos = event.pos()
        label_pos = self.label.mapFrom(self.viewport(), pos)
        fx = label_pos.x() / max(1, self.label.width())
        fy = label_pos.y() / max(1, self.label.height())
        self.scale = new_scale
        self._apply_pixmap()
        self.horizontalScrollBar().setValue(int(fx * self.label.width() - pos.x()))
        self.verticalScrollBar().setValue(int(fy * self.label.height() - pos.y()))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.pos()
            self.viewport().setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            delta = event.pos() - self._drag_pos
            self._drag_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._drag_pos is not None:
            self._drag_pos = None
            self.viewport().unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _apply_pixmap(self):
        pm = self.pixmap
        if self.scale != 1:
            pm = pm.scaled(max(1, int(pm.width() * self.scale)), max(1, int(pm.height() * self.scale)),
                           aspectRatioMode=QtCore.Qt.KeepAspectRatio)
        self.label.setPixmap(pm)
        self.label.resize(pm.size())
        self._update_geometry_if_needed()

    def load_pixmap(self, pixmap):
        self.pixmap = pixmap
        self._apply_pixmap()


# base of the labeled widgets: horizontal layout with label on the left, the control (and extras) on the right.
# the whole API of the control (QSlider, QSpinBox, ...) is available on the labeled widget through delegation,
# including signals, so only what differs has to be written here.
# generic QWidget methods (setEnabled, setToolTip, resize, ...) act on the whole row; use `.control` for the control.
class MZODLabelWidget(QtWidgets.QWidget):
    def __init__(self, text='', control=None, parent=None):
        super().__init__(parent)
        self.h_layout = QtWidgets.QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.label = QtWidgets.QLabel(text, self)
        self.control = control
        self.h_layout.addWidget(self.label)
        self.h_layout.addWidget(control, 1)

    def __getattr__(self, name):
        # called only when `name` is not found on the labeled widget itself
        control = self.__dict__.get('control')
        if control is None or name.startswith('__'):
            raise AttributeError(name)
        return getattr(control, name)

    # sets text of the label on the left
    def SetLabel(self, text):
        self.label.setText(text)

    # setRange(minimum, maximum) or setRange((minimum, maximum))
    @staticmethod
    def _bounds(minimum, maximum=None):
        if maximum is None:
            minimum, maximum = minimum
        return minimum, maximum

    def setRange(self, minimum, maximum=None):
        self.control.setRange(*self._bounds(minimum, maximum))


# label | slider | current value label
class MZODLabelSlider(MZODLabelWidget):
    def __init__(self, text='', minimum=0, maximum=100, value=0, parent=None):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        super().__init__(text, slider, parent)
        self.slider = slider
        self.label_value = QtWidgets.QLabel(str(slider.value()), self)
        slider.valueChanged.connect(lambda v: self.label_value.setText(str(v)))
        self.h_layout.addWidget(self.label_value)


# label | combobox
class MZODLabelComboBox(MZODLabelWidget):
    def __init__(self, text='', items=(), parent=None):
        combobox = QtWidgets.QComboBox()
        combobox.addItems(list(items))
        super().__init__(text, combobox, parent)
        self.combobox = combobox


# label | checkbox
class MZODLabelCheckBox(MZODLabelWidget):
    def __init__(self, text='', checked=False, parent=None):
        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(checked)
        super().__init__(text, checkbox, parent)
        self.checkbox = checkbox


# label | spinbox | current value label
class MZODLabelSpinBox(MZODLabelWidget):
    def __init__(self, text='', minimum=0, maximum=100, value=0, step=1, parent=None):
        spinbox = QtWidgets.QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        spinbox.setValue(value)
        super().__init__(text, spinbox, parent)
        self.spinbox = spinbox
        self.label_value = QtWidgets.QLabel(str(spinbox.value()), self)
        spinbox.valueChanged.connect(lambda v: self.label_value.setText(str(v)))
        self.h_layout.addWidget(self.label_value)


# label | double spinbox | current value label
class MZODLabelDoubleSpinBox(MZODLabelWidget):
    def __init__(self, text='', minimum=0.0, maximum=100.0, value=0.0, step=1.0, decimals=2, parent=None):
        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setDecimals(decimals)
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        spinbox.setValue(value)
        super().__init__(text, spinbox, parent)
        self.spinbox = spinbox
        self.label_value = QtWidgets.QLabel(self._format(spinbox.value()), self)
        spinbox.valueChanged.connect(lambda v: self.label_value.setText(self._format(v)))
        self.h_layout.addWidget(self.label_value)

    def _format(self, value):
        return f'{value:.{self.spinbox.decimals()}f}'


# label | spinbox | slider, both hold the same value
# the control is the spinbox, so value(), setValue() and valueChanged come from it
class MZODLabelSpinSlider(MZODLabelWidget):
    def __init__(self, text='', minimum=0, maximum=100, value=0, step=1, parent=None):
        spinbox = QtWidgets.QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        super().__init__(text, spinbox, parent)
        self.spinbox = spinbox
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider.setRange(minimum, maximum)
        self.slider.setSingleStep(step)
        spinbox.setValue(value)
        self.slider.setValue(spinbox.value())
        # setting an equal value emits nothing, so the two do not loop
        spinbox.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(spinbox.setValue)
        self.h_layout.setStretch(1, 0)
        self.h_layout.addWidget(self.slider, 1)

    # the range and steps belong to both spinbox and slider
    def setRange(self, minimum, maximum=None):
        minimum, maximum = self._bounds(minimum, maximum)
        self.spinbox.setRange(minimum, maximum)
        self.slider.setRange(minimum, maximum)

    def setMinimum(self, minimum):
        self.setRange(minimum, self.spinbox.maximum())

    def setMaximum(self, maximum):
        self.setRange(self.spinbox.minimum(), maximum)

    def setSingleStep(self, step):
        self.spinbox.setSingleStep(step)
        self.slider.setSingleStep(step)

    def setPageStep(self, step):
        self.slider.setPageStep(step)


# label | double spinbox | slider, both hold the same value
# the control is the spinbox, so value(), setValue(), setDecimals() and valueChanged come from it.
# slider moves in singleStep increments, spinbox accepts any value with given number of decimals
class MZODLabelSpinSliderDouble(MZODLabelWidget):
    def __init__(self, text='', minimum=0.0, maximum=100.0, value=0.0, step=1.0, decimals=2, parent=None):
        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setDecimals(decimals)
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        super().__init__(text, spinbox, parent)
        self.spinbox = spinbox
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self._update_slider_range()
        spinbox.setValue(value)
        self._sync_slider()
        spinbox.valueChanged.connect(self._sync_slider)
        self.slider.valueChanged.connect(self._slider_changed)
        self.h_layout.setStretch(1, 0)
        self.h_layout.addWidget(self.slider, 1)

    # slider holds integer positions 0..N, position i means minimum + i * singleStep
    def _update_slider_range(self):
        span = self.spinbox.maximum() - self.spinbox.minimum()
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(1, round(span / self.spinbox.singleStep())))
        self.slider.blockSignals(False)

    def _sync_slider(self, _=None):
        self.slider.blockSignals(True)
        self.slider.setValue(round((self.spinbox.value() - self.spinbox.minimum()) / self.spinbox.singleStep()))
        self.slider.blockSignals(False)

    def _slider_changed(self, position):
        value = self.spinbox.minimum() + position * self.spinbox.singleStep()
        self.spinbox.setValue(min(value, self.spinbox.maximum()))

    def setRange(self, minimum, maximum=None):
        minimum, maximum = self._bounds(minimum, maximum)
        self.spinbox.setRange(minimum, maximum)
        self._update_slider_range()
        self._sync_slider()

    def setMinimum(self, minimum):
        self.setRange(minimum, self.spinbox.maximum())

    def setMaximum(self, maximum):
        self.setRange(self.spinbox.minimum(), maximum)

    def setSingleStep(self, step):
        self.spinbox.setSingleStep(step)
        self._update_slider_range()
        self._sync_slider()

    def setPageStep(self, step):
        self.slider.setPageStep(step)

    def setValue(self, value):
        self.slider.blockSignals(True)
        self.spinbox.setValue(value)
        self._sync_slider()
        self.slider.blockSignals(False)


class MZODSnippetWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

        self.central_widget = None
        self.grid_layout = None

        self.button = None
        self.combobox = None
        self.label_combobox = None
        self.lineedit = None
        self.slider = None
        self.label_slider = None
        self.checkbox = None
        self.spinbox = None
        self.doublespinbox = None
        self.timer = None
        self.timer_cnt = 0

        self.cw = None

        self.setup_ui()

    def setup_ui(self):
        self.resize(1200, 800)
        self.central_widget = QtWidgets.QWidget(self)
        self.grid_layout = QtWidgets.QGridLayout(self.central_widget)

        # button snippet
        self.button = QtWidgets.QPushButton(self)
        self.button.setText('Hello World')
        self.button.clicked.connect(self.button_clicked)
        # creating a grid in here, pos y, pos x, height, width
        self.grid_layout.addWidget(self.button, 0, 0, 1, 2)

        # combobox snippet
        self.combobox = QtWidgets.QComboBox(self)
        for i in range(4):
            self.combobox.addItem(f'Item{i}')
        self.combobox.currentIndexChanged.connect(self.combobox_idx_changed)
        self.label_combobox = QtWidgets.QLabel(self)
        self.grid_layout.addWidget(self.combobox, 1, 0, 1, 1)
        self.grid_layout.addWidget(self.label_combobox, 1, 1, 1, 1)

        # line edit snippet
        self.lineedit = QtWidgets.QLineEdit(self)
        self.lineedit.textEdited.connect(self.lineedit_edited)
        onlyInt = QIntValidator()
        onlyInt.setRange(0, 5)
        self.lineedit.setValidator(onlyInt)
        self.grid_layout.addWidget(self.lineedit, 2, 0, 1, 2)

        # slider snippet
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider.setMinimum(0)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(10)
        self.slider.setMaximum(100)
        self.slider.valueChanged.connect(self.slider_changed)
        self.label_slider = QtWidgets.QLabel(self)
        self.grid_layout.addWidget(self.slider, 3, 0, 1, 1)
        self.grid_layout.addWidget(self.label_slider, 3, 1, 1, 1)

        # checkbox snippet
        self.checkbox = QtWidgets.QCheckBox(self)
        self.checkbox.setText('this one has its own label')
        self.checkbox.stateChanged.connect(self.checkbox_changed)
        self.grid_layout.addWidget(self.checkbox, 4, 0, 1, 2)

        # spinbox snippet
        self.spinbox = QtWidgets.QSpinBox(self)
        self.spinbox.setRange(0, 50)
        self.spinbox.setSingleStep(3)
        self.spinbox.valueChanged.connect(self.spinbox_changed)

        # double spinbox snippet
        self.doublespinbox = QtWidgets.QDoubleSpinBox(self)
        self.doublespinbox.setRange(0.0, 50.0)
        self.doublespinbox.setSingleStep(3.0)
        self.doublespinbox.valueChanged.connect(self.doublespinbox_changed)

        self.grid_layout.addWidget(self.spinbox, 6, 0, 1, 1)
        self.grid_layout.addWidget(self.doublespinbox, 6, 1, 1, 1)

        # timer snippet
        # set timer to ms period
        # check what self.timer_hanler does
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(int(1000 / 30))
        self.timer.timeout.connect(self.timer_handler)
        self.timer.start()

        # !!! CONFIDENTIAL !!!
        # !!! HIDE FROM PUBLIC AT ANY COSTS !!!
        # !!! DO NOT UNCOMMENT !!!
        nb = QtWidgets.QLCDNumber(self)
        self.grid_layout.addWidget(nb, 8, 0, 1, 2)

        self.setCentralWidget(self.central_widget)

    # advanced button clicked snippet
    def button_clicked(self):
        btn = self.sender()
        btn.setText('Hello World @{:.3f}'.format(self.timer_cnt/self.timer.interval()))

    # cool combobox clicked snippet
    def combobox_idx_changed(self):
        cb = self.sender()
        self.label_combobox.setText(f'{cb.currentText()} @ {cb.currentIndex()}')

    # lineedit edited polite snippet
    def lineedit_edited(self, text):
        # no code here, sir, as you may have noticed
        # go away
        # please
        pass

    # Awesome slider changed code snippet
    def slider_changed(self):
        sl = self.sender()
        self.label_slider.setText(f'{sl.value()}')

    # What a snippet for a checkbox changed signal !!!
    def checkbox_changed(self):
        ch = self.sender()
        ch.setText(f'this one has its own label and is{"" if ch.isChecked() else " not"} checked')

    # A miraculous perpetuum mobile spinbox snippets
    # Will these two run forever?
    # Execute now and find out!
    def spinbox_changed(self):
        sb = self.sender()
        self.doublespinbox.setValue(float(sb.value()))

    def doublespinbox_changed(self):
        dsb = self.sender()
        self.spinbox.setValue(int(dsb.value()))

    # it is a timer handler snippet time
    def timer_handler(self):
        self.setWindowTitle('{:.3f}'.format(self.timer_cnt / self.timer.interval()))
        self.timer_cnt += 1


class MZODSnippetsApp:
    def __init__(self, argv):
        self.app = QtWidgets.QApplication(argv)
        self.app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        self.ui = MZODSnippetWindow()
        self.ui.setup_ui()

    def run(self):
        self.ui.show()
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    MZCAMgui = MZODSnippetsApp(sys.argv)
    MZCAMgui.run()