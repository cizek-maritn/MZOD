import MZODQtSnippets as Snippets
from PyQt5 import QtWidgets, QtGui, QtCore
from MZODTabTemplate import MZODTabTemplate


class Lab00(MZODTabTemplate):
    title = 'Lab01 - Qt Snippets'

    def __init__(self, camera, parent=None):
        self.button = None
        self.combobox = None
        self.lineedit = None
        self.slider = None
        self.checkbox = None
        self.spinbox = None
        self.doublespinbox = None
        self.timer = None
        self.timer_label = None
        self.timer_cnt = 0
        super().__init__(camera, parent)

    def setup_ui(self):
        self.button = QtWidgets.QPushButton(self)
        self.button.setText('Hello World')
        self.button.clicked.connect(self.button_clicked)
        self.grid_layout.addWidget(self.button, 0, 0)

        # combobox snippet
        self.combobox = Snippets.MZODLabelComboBox('Combobox', [], parent=self)
        for i in range(4):
            self.combobox.addItem(f'Item{i}')
        self.combobox.currentIndexChanged.connect(self.combobox_idx_changed)
        self.grid_layout.addWidget(self.combobox, 1, 0)

        # line edit snippet
        self.lineedit = QtWidgets.QLineEdit(self)
        self.lineedit.textEdited.connect(self.lineedit_edited)
        onlyInt = QtGui.QIntValidator()
        onlyInt.setRange(0, 5)
        self.lineedit.setValidator(onlyInt)
        self.grid_layout.addWidget(self.lineedit, 2, 0)

        self.slider = Snippets.MZODLabelSlider('Slider', parent=self)
        self.slider.setMinimum(0)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(10)
        self.slider.setMaximum(100)
        self.grid_layout.addWidget(self.slider, 3, 0)

        # checkbox snippet
        self.checkbox = Snippets.MZODLabelCheckBox('Check Box', parent=self)
        self.checkbox.stateChanged.connect(self.checkbox_changed)
        self.grid_layout.addWidget(self.checkbox, 4, 0)

        # spinbox snippet
        self.spinbox = Snippets.MZODLabelSpinBox('Spinbox', parent=self)
        self.spinbox.setRange(0, 50)
        self.spinbox.setSingleStep(3)
        self.spinbox.valueChanged.connect(self.spinbox_changed)
        self.grid_layout.addWidget(self.spinbox, 5, 0)

        # double spinbox snippet
        self.doublespinbox = Snippets.MZODLabelDoubleSpinBox('DoubleSpinbox', parent=self)
        self.doublespinbox.setRange(0.0, 50.0)
        self.doublespinbox.setSingleStep(3.0)
        self.doublespinbox.valueChanged.connect(self.doublespinbox_changed)
        self.grid_layout.addWidget(self.doublespinbox, 6, 0)

        # label snippet
        self.timer_label = QtWidgets.QLabel(self)
        self.timer_label.setText('0')
        self.grid_layout.addWidget(self.timer_label, 7, 0)

        # timer snippet
        # set timer to ms period
        # check what self.timer_hanler does
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(int(1000 / 30))
        self.timer.timeout.connect(self.timer_handler)
        self.timer.start()

    # advanced button clicked snippet
    def button_clicked(self):
        btn = self.sender()
        btn.setText('Hello World @{:.3f}'.format(self.timer_cnt / self.timer.interval()))

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
        self.timer_label.setText('{:.3f}'.format(self.timer_cnt / self.timer.interval()))
        self.timer_cnt += 1