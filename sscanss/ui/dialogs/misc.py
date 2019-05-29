import os
import re
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from sscanss.core.util import DockFlag
from sscanss.ui.widgets import AlignmentErrorModel, ErrorDetailModel, Banner, Accordion, Pane, create_tool_button

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class ProjectDialog(QtWidgets.QDialog):

    formSubmitted = QtCore.pyqtSignal(str, str)
    recentItemDoubleClicked = QtCore.pyqtSignal(str)
    # max number of recent projects to show in dialog is fixed because of the
    # dimensions of the dialog window
    max_recent_size = 5

    def __init__(self, recent, parent):
        super().__init__(parent)

        self.parent = parent
        self.recent = recent
        self.instruments = list(parent.presenter.model.instruments.keys())
        data = parent.presenter.model.project_data
        self.selected_instrument = None if data is None else data['instrument'].name

        if len(self.recent) > self.max_recent_size:
            self.recent_list_size = self.max_recent_size
        else:
            self.recent_list_size = len(self.recent)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setMinimumSize(640, 480)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.createImageHeader()
        self.createTabWidgets()
        self.createStackedWidgets()
        self.createNewProjectWidgets()
        self.createRecentProjectWidgets()
        self.create_project_button.clicked.connect(self.createProjectButtonClicked)

        presenter = self.parent.presenter
        self.formSubmitted.connect(lambda name, inst: presenter.useWorker(presenter.createProject, [name, inst],
                                                                          presenter.updateView,
                                                                          presenter.projectCreationError, self.accept))
        self.recentItemDoubleClicked.connect(lambda name: presenter.useWorker(presenter.openProject, [name],
                                                                              presenter.updateView,
                                                                              presenter.projectOpenError, self.accept))

        self.project_name_textbox.setFocus()

    def createImageHeader(self):
        img = QtWidgets.QLabel()
        img.setPixmap(QtGui.QPixmap('../static/images/banner.png'))
        self.main_layout.addWidget(img)

    def createTabWidgets(self):
        self.group = QtWidgets.QButtonGroup()
        self.button_layout = QtWidgets.QHBoxLayout()
        self.new_project_button = QtWidgets.QPushButton('Create New Project')
        self.new_project_button.setObjectName('CustomTab')
        self.new_project_button.setCheckable(True)
        self.new_project_button.setChecked(True)

        self.load_project_button = QtWidgets.QPushButton('Open Existing Project')
        self.load_project_button.setObjectName('CustomTab')
        self.load_project_button.setCheckable(True)

        self.group.addButton(self.new_project_button, 0)
        self.group.addButton(self.load_project_button, 1)
        self.button_layout.addWidget(self.new_project_button)
        self.button_layout.addWidget(self.load_project_button)
        self.button_layout.setSpacing(0)

        self.main_layout.addLayout(self.button_layout)

    def createStackedWidgets(self):
        self.stack = QtWidgets.QStackedLayout(self)
        self.main_layout.addLayout(self.stack)

        self.stack1 = QtWidgets.QWidget()
        self.stack1.setContentsMargins(30, 0, 30, 0)
        self.stack2 = QtWidgets.QWidget()
        self.stack2.setContentsMargins(30, 0, 30, 0)
        self.group.buttonClicked[int].connect(self.stack.setCurrentIndex)

        self.stack.addWidget(self.stack1)
        self.stack.addWidget(self.stack2)

    def createNewProjectWidgets(self):
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel('Project Name:'))

        self.project_name_textbox = QtWidgets.QLineEdit()
        layout.addWidget(self.project_name_textbox)
        self.validator_textbox = QtWidgets.QLabel('')
        self.validator_textbox.setObjectName('Error')
        layout.addWidget(self.validator_textbox)
        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel('Select Instrument:'))

        self.instrument_combobox = QtWidgets.QComboBox()
        self.instrument_combobox.setView(QtWidgets.QListView())
        self.instrument_combobox.addItems(self.instruments)
        self.instrument_combobox.setCurrentText(self.selected_instrument)
        layout.addWidget(self.instrument_combobox)
        layout.addStretch(1)

        button_layout = QtWidgets.QHBoxLayout()
        self.create_project_button = QtWidgets.QPushButton('Create')
        button_layout.addWidget(self.create_project_button)
        button_layout.addStretch(1)

        layout.addLayout(button_layout)
        layout.addStretch(1)

        self.stack1.setLayout(layout)

    def createProjectButtonClicked(self):
        name = self.project_name_textbox.text().strip()
        instrument = self.instrument_combobox.currentText()
        if name:
            self.formSubmitted.emit(name, instrument)
        else:
            self.validator_textbox.setText('Project name cannot be left blank.')

    def createRecentProjectWidgets(self):
        layout = QtWidgets.QVBoxLayout()
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setObjectName('Recents')
        self.list_widget.setSpacing(10)

        for i in range(self.recent_list_size):
            item = QtWidgets.QListWidgetItem(self.recent[i])
            item.setIcon(QtGui.QIcon('../static/images/file-black.png'))
            self.list_widget.addItem(item)

        item = QtWidgets.QListWidgetItem('Open ...')
        item.setIcon(QtGui.QIcon('../static/images/folder-open.png'))
        self.list_widget.addItem(item)

        self.list_widget.itemDoubleClicked.connect(self.projectItemDoubleClicked)
        layout.addWidget(self.list_widget)

        self.stack2.setLayout(layout)

    def projectItemDoubleClicked(self, item):
        index = self.list_widget.row(item)

        if index == self.recent_list_size:
            filename = self.parent.showOpenDialog('hdf5 File (*.h5)', title='Open Project',
                                                  current_dir=self.parent.presenter.model.save_path)
            if not filename:
                return
        else:
            filename = item.text()

        self.recentItemDoubleClicked.emit(filename)


class ProgressDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setTextVisible(False)
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(0)

        self.message = QtWidgets.QLabel('')
        self.message.setAlignment(QtCore.Qt.AlignCenter)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addStretch(1)
        main_layout.addWidget(progress_bar)
        main_layout.addWidget(self.message)
        main_layout.addStretch(1)

        self.setLayout(main_layout)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setMinimumSize(300, 120)
        self.setModal(True)

    def show(self, message):
        self.message.setText(message)
        super().show()

    def keyPressEvent(self, _):
        """
        This ensure the user cannot close the dialog box with the Esc key
        """
        pass


class AlignmentErrorDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        self.measured_points = np.empty(0)
        self.transform_result = None
        self.main_layout = QtWidgets.QVBoxLayout()
        self.banner = Banner(Banner.Type.Info, self)
        self.main_layout.addWidget(self.banner)
        self.banner.hide()

        self.main_layout.addSpacing(5)
        self.result_text = '<p style="font-size:14px">The Average (RMS) Error is ' \
                           '<span style="color:{};font-weight:500;">{:.3f}</span> {}</p>'
        self.result_label = QtWidgets.QLabel()
        self.result_label.setTextFormat(QtCore.Qt.RichText)
        self.updateResultText(0.0)
        self.main_layout.addWidget(self.result_label)
        self.main_layout.addSpacing(10)
        self.createTabWidgets()
        self.createStackedWidgets()
        self.createSummaryTable()
        self.createDetailTable()

        self.main_layout.addStretch(1)

        button_layout = QtWidgets.QHBoxLayout()
        self.accept_button = QtWidgets.QPushButton('Accept')
        self.accept_button.clicked.connect(self.submit)
        self.recalculate_button = QtWidgets.QPushButton('Recalculate')
        self.recalculate_button.clicked.connect(self.recalculate)
        self.cancel_button = QtWidgets.QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setDefault(True)

        button_layout.addWidget(self.recalculate_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.cancel_button)

        self.main_layout.addLayout(button_layout)
        self.setLayout(self.main_layout)

        self.setMinimumWidth(450)
        self.setWindowTitle('Error Report for Sample Alignment')

    def createTabWidgets(self):
        self.tabs = QtWidgets.QButtonGroup()
        tab_layout = QtWidgets.QHBoxLayout()
        self.summary_tab = QtWidgets.QPushButton('Summary')
        self.summary_tab.setObjectName('CustomTab')
        self.summary_tab.setCheckable(True)
        self.summary_tab.setChecked(True)

        self.detail_tab = QtWidgets.QPushButton('Detailed Analysis')
        self.detail_tab.setObjectName('CustomTab')
        self.detail_tab.setCheckable(True)

        self.tabs.addButton(self.summary_tab, 0)
        self.tabs.addButton(self.detail_tab, 1)
        tab_layout.addWidget(self.summary_tab)
        tab_layout.addWidget(self.detail_tab)
        tab_layout.setSpacing(0)

        self.main_layout.addLayout(tab_layout)

    def createStackedWidgets(self):
        self.stack = QtWidgets.QStackedLayout()
        self.main_layout.addLayout(self.stack)
        self.stack1 = QtWidgets.QWidget()
        self.stack2 = QtWidgets.QWidget()

        self.stack.addWidget(self.stack1)
        self.stack.addWidget(self.stack2)
        self.tabs.buttonClicked[int].connect(self.changeTab)

    def createSummaryTable(self):
        layout = QtWidgets.QVBoxLayout()
        self.summary_table_view = QtWidgets.QTableView()
        self.summary_table_model = AlignmentErrorModel()
        self.summary_table_view.setModel(self.summary_table_model)
        self.summary_table_view.verticalHeader().setVisible(False)
        self.summary_table_view.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.summary_table_view.setFocusPolicy(QtCore.Qt.NoFocus)
        self.summary_table_view.setAlternatingRowColors(True)
        self.summary_table_view.setMinimumHeight(300)
        self.summary_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.summary_table_view.horizontalHeader().setMinimumSectionSize(40)
        self.summary_table_view.horizontalHeader().setDefaultSectionSize(40)

        layout.addWidget(self.summary_table_view)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack1.setLayout(layout)

    def createDetailTable(self):
        layout = QtWidgets.QVBoxLayout()
        self.detail_table_view = QtWidgets.QTableView()
        self.detail_table_model = ErrorDetailModel()
        self.detail_table_view.setModel(self.detail_table_model)
        self.detail_table_view.verticalHeader().setVisible(False)
        self.detail_table_view.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.detail_table_view.setFocusPolicy(QtCore.Qt.NoFocus)
        self.detail_table_view.setAlternatingRowColors(True)
        self.detail_table_view.setMinimumHeight(300)
        self.detail_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.detail_table_view.horizontalHeader().setMinimumSectionSize(40)
        self.detail_table_view.horizontalHeader().setDefaultSectionSize(40)

        layout.addWidget(self.detail_table_view)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack2.setLayout(layout)

    def recalculate(self):
        if self.measured_points.size == 0:
            return

        if np.count_nonzero(self.summary_table_model.enabled) < 3:
            self.banner.showMessage('A minimum of 3 points is required for sample alignment.',
                                    Banner.Type.Error)
            return

        self.transform_result = self.parent().presenter.rigidTransform(self.summary_table_model.point_index,
                                                                       self.measured_points,
                                                                       self.summary_table_model.enabled)
        error = np.full(self.summary_table_model.enabled.size, np.nan)
        error[self.summary_table_model.enabled] = self.transform_result.error
        self.summary_table_model.error = error
        self.updateResultText(self.transform_result.average)

        self.detail_table_model.details = self.transform_result.distance_analysis
        self.detail_table_model.index_pairs = self.summary_table_model.point_index[self.summary_table_model.enabled]
        self.updateTable()

    def updateTable(self):
        self.detail_table_model.update()
        self.detail_table_view.update()
        self.summary_table_model.update()
        self.summary_table_view.update()

    def indexOrder(self, new_order):
        self.banner.actionButton('FIX', lambda ignore, n=new_order: self.__correctIndexOrder(n))
        self.banner.showMessage('Incorrect Point Indices have been detected.',
                                Banner.Type.Warn, False)

    def __correctIndexOrder(self, new_index):
        self.summary_table_model.point_index = new_index
        self.recalculate()

    def updateResultText(self, average_error):
        if average_error < 0.1:
            colour = 'SeaGreen'
            self.banner.hide()
        else:
            colour = 'firebrick'
            self.banner.showMessage('If the errors are larger than desired, '
                                    'Try disabling points with the large errors then recalculate.',
                                    Banner.Type.Info)
        self.result_label.setText(self.result_text.format(colour, average_error, 'mm'))

    def updateModel(self, index, enabled, measured_points, transform_result):
        error = np.full(enabled.size, np.nan)
        error[enabled] = transform_result.error

        self.summary_table_model.point_index = index
        self.summary_table_model.error = error
        self.summary_table_model.enabled = enabled
        self.transform_result = transform_result
        self.measured_points = measured_points
        self.updateResultText(self.transform_result.average)
        self.detail_table_model.details = self.transform_result.distance_analysis
        self.detail_table_model.index_pairs = index[enabled]
        self.updateTable()

    def changeTab(self, index):
        self.stack.setCurrentIndex(index)
        self.cancel_button.setDefault(True)

    def submit(self):
        if self.transform_result is None:
            return
        self.parent().scenes.switchToInstrumentScene()
        self.parent().presenter.alignSample(self.transform_result.matrix)

        self.accept()


class FileDialog(QtWidgets.QFileDialog):
    def __init__(self, parent, caption, directory, filters):
        super().__init__(parent, caption, directory, filters)

        self.filters = self.extractFilters(filters)
        self.setOptions(QtWidgets.QFileDialog.DontConfirmOverwrite)

    def extractFilters(self, filters):
        filters = re.findall(r'\*.\w+', filters)
        return [f[1:] for f in filters]

    @property
    def filename(self):
        filename = self.selectedFiles()[0]
        _, ext = os.path.splitext(filename)
        expected_ext = self.extractFilters(self.selectedNameFilter())[0]
        if ext not in self.filters:
            filename = f'{filename}{expected_ext}'

        return filename

    @staticmethod
    def getOpenFileName(parent, caption, directory, filters):
        dialog = FileDialog(parent, caption, directory, filters)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptOpen)
        if dialog.exec() != QtWidgets.QFileDialog.Accepted:
            return ''

        filename = dialog.filename

        if not os.path.isfile(filename):
            message = f'{filename} file not found.\nCheck the file name and try again.'
            QtWidgets.QMessageBox.warning(parent, caption, message, QtWidgets.QMessageBox.Ok,
                                          QtWidgets.QMessageBox.Ok)
            return ''

        return filename

    @staticmethod
    def getSaveFileName(parent, caption, directory, filters):
        dialog = FileDialog(parent, caption, directory, filters)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        if dialog.exec() != QtWidgets.QFileDialog.Accepted:
            return ''

        filename = dialog.filename

        if os.path.isfile(filename):
            buttons = QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            message = f'{filename} already exists.\nDo want to replace it?'
            reply = QtWidgets.QMessageBox.warning(parent, caption, message, buttons,
                                                  QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.No:
                return ''

        return filename


class SampleExportDialog(QtWidgets.QDialog):

    def __init__(self, sample_list, parent):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setMinimumHeight(200)
        self.list_widget.setSpacing(2)
        self.list_widget.addItems(sample_list)
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemClicked.connect(self.deselection)
        layout.addWidget(self.list_widget)

        button_layout = QtWidgets.QHBoxLayout()
        self.accept_button = QtWidgets.QPushButton('OK')
        self.accept_button.clicked.connect(self.accept)
        self.cancel_button = QtWidgets.QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setDefault(True)

        button_layout.addStretch(1)
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setWindowTitle('Select Sample to Save ...')

    def deselection(self, item):
        """prevent deselection by ensuring the clicked item is always selected"""
        if not item.isSelected():
            self.list_widget.setCurrentItem(item)

    @property
    def selected(self):
        return self.list_widget.currentItem().text()


class SimulationDialog(QtWidgets.QWidget):
    dock_flag = DockFlag.Full

    def __init__(self, simulation, parent):
        super().__init__(parent)

        self.parent = parent
        main_layout = QtWidgets.QVBoxLayout()

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        self.path_length_button = create_tool_button(tooltip='Plot Path Length', style_name='ToolButton',
                                                     icon_path='../static/images/line-chart.png')
        self.path_length_button.clicked.connect(self.parent.showPathLength)

        self.clear_button = create_tool_button(tooltip='Clear Result', style_name='ToolButton',
                                               icon_path='../static/images/cross.png')
        self.clear_button.clicked.connect(self.clearResults)
        self.export_button = create_tool_button(tooltip='Export Script', style_name='ToolButton',
                                                icon_path='../static/images/export.png')
        self.export_button.clicked.connect(self.parent.showScriptExport)

        button_layout.addWidget(self.path_length_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.export_button)
        main_layout.addLayout(button_layout)

        self.progress_label = QtWidgets.QLabel()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_label)
        main_layout.addWidget(self.progress_bar)

        self.result_list = Accordion()
        main_layout.addWidget(self.result_list)
        self.setLayout(main_layout)

        self.title = 'Simulation Result'
        self.setMinimumWidth(400)

        self._simulation = None
        self.simulation = simulation
        if self._simulation is not None and self.simulation.isRunning():
            self.parent.scenes.switchToInstrumentScene()
        self.showResult()

    @property
    def simulation(self):
        return self._simulation

    @simulation.setter
    def simulation(self, value):
        # Disconnect previous simulation
        if self._simulation is not None and self._simulation.receivers(self._simulation.point_finished) > 0:
            self._simulation.point_finished.disconnect()

        self._simulation = value
        if self._simulation is not None:
            self._simulation.point_finished.connect(self.showResult)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(self._simulation.count)
            self.progress_label.setText(f'Completed 0 of {self.progress_bar.maximum()}')

    def updateProgress(self):
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.progress_label.setText(f'Completed {self.progress_bar.value()} of {self.progress_bar.maximum()}')

    def showResult(self):
        if self.simulation is None:
            return

        results = self.simulation.results[len(self.result_list.panes):]

        for result in results:
            result_text = '\n'.join('{}:\t {:.3f}'.format(*t) for t in zip(result.joint_labels, result.formatted))
            label = QtWidgets.QLabel()
            label.setTextFormat(QtCore.Qt.RichText)
            info = (f'{result.id}<br/><b>Position Error:</b> {result.error[0]:.3f}'
                    f'<br/><b>Orientation Error:</b> (X.) {result.error[1][0]:.3f}, (Y.) {result.error[1][1]:.3f}, '
                    f'(Z.) {result.error[1][2]:.3f}')

            if self.simulation.compute_path_length:
                detector_labels = self.simulation.detector_names
                path_length_info = ', '.join('({}) {:.3f}'.format(*l) for l in zip(detector_labels, result.path_length))
                info = f'{info}<br/><b>Path Length:</b> {path_length_info}'

            label.setText(info)
            label2 = QtWidgets.QLabel()
            label2.setText(result_text)
            status = self.simulation.positioner.ik_solver.Status
            if result.code == status.Converged:
                style = Pane.Type.Info
            elif result.code == status.NotConverged:
                style = Pane.Type.Warn
            else:
                style = Pane.Type.Error

            self.result_list.addPane(Pane(label, label2, style))
            self.updateProgress()


    def clearResults(self):
        if self.simulation is None:
            return

        if self.simulation.isRunning():
            options = ['Clear', 'Cancel']
            res = self.parent.showSelectChoiceMessage('The current simulation will be terminated before results are '
                                                      'cleared.\n\nDo you want proceed with this action?',
                                                      options, default_choice=1)
            if res == options[1]:
                return

            self.simulation.abort()

        self.result_list.clear()
        self.simulation.results = []
        self.progress_label.setText('')
        self.progress_bar.setValue(0)


class ScriptExportDialog(QtWidgets.QDialog):
    def __init__(self, simulation, parent):
        super().__init__(parent)

        self.parent = parent
        self.parent_model = parent.presenter.model
        self.results = simulation.results

        self.template = self.parent_model.instrument.script_template
        self.createTemplateKeys()

        main_layout = QtWidgets.QVBoxLayout()
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel('Duration of Measurements (microamps):'))
        self.micro_amp_textbox = QtWidgets.QLineEdit(self.template.keys[self.template.Key.mu_amps.value])
        validator = QtGui.QDoubleValidator(self.micro_amp_textbox)
        validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
        validator.setDecimals(3)
        self.micro_amp_textbox.setValidator(validator)
        self.micro_amp_textbox.textEdited.connect(self.preview)
        layout.addStretch(1)
        layout.addWidget(self.micro_amp_textbox)
        main_layout.addLayout(layout)

        self.preview_label = QtWidgets.QTextEdit()
        self.preview_label.setDisabled(True)
        self.preview_label.setMinimumHeight(350)
        main_layout.addWidget(self.preview_label)
        self.preview()

        layout = QtWidgets.QHBoxLayout()
        self.export_button = QtWidgets.QPushButton('Export')
        self.export_button.clicked.connect(self.export)
        self.cancel_button = QtWidgets.QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.close)
        layout.addStretch(1)
        layout.addWidget(self.export_button)
        layout.addWidget(self.cancel_button)
        main_layout.addLayout(layout)

        self.setLayout(main_layout)
        self.setMinimumSize(450, 400)
        self.setWindowTitle('Export Script')
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)

    def createTemplateKeys(self):
        # TODO: only include values of specified keys in the template not all
        Key = self.template.Key
        self.template.keys[Key.script.value] = []
        self.template.keys[Key.filename.value] = self.parent_model.save_path
        self.template.keys[Key.mu_amps.value] = '0.000'
        self.template.keys[Key.count.value] = len(self.results)

        header = []
        for h in self.template.header_order:
            if h == Key.position.value:
                header.extend(self.results[0].joint_labels)
            else:
                header.append(h)
        self.template.keys[Key.header.value] = '\t'.join(header)

    def renderScript(self, preview=False):
        Key = self.template.Key
        count = len(self.results)
        size = 10 if count > 10 and preview else count
        script = []
        for i in range(size):
            script.append({Key.position.value: '\t'.join('{:.3f}'.format(l) for l in self.results[i].formatted)})

        self.template.keys[Key.mu_amps.value] = self.micro_amp_textbox.text()
        self.template.keys[Key.script.value] = script

        return self.template.render()

    def preview(self):
        script = self.renderScript(preview=True)
        if len(self.results) > 10:
            self.preview_label.setText(f'{script} \n\n[Maximum of 10 points shown in preview]')
        else:
            self.preview_label.setText(script)

    def export(self):
        if self.parent.presenter.exportScript(self.renderScript):
            self.accept()


class PathLengthPlotter(QtWidgets.QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        self.simulation = parent.presenter.model.simulation

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        tool_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(tool_layout)

        self.grid_button = create_tool_button(tooltip='Toggle Grid', style_name='ToolButton', checkable=True,
                                              checked=False, icon_path='../static/images/grid.png')
        self.grid_button.toggled.connect(lambda: self.plot())  # avoid passing checked as index
        tool_layout.addWidget(self.grid_button)
        if self.simulation.alignments > 1:
            self.alignment_combobox = QtWidgets.QComboBox()
            self.alignment_combobox.setView(QtWidgets.QListView())
            self.alignment_combobox.addItems([f'{k + 1}' for k in range(self.simulation.alignments)])
            self.alignment_combobox.activated.connect(self.plot)
            tool_layout.addWidget(QtWidgets.QLabel('Select Alignment: '))
            tool_layout.addWidget(self.alignment_combobox)
        tool_layout.addStretch(1)

        self.createFigure()
        self.setMinimumSize(800, 600)
        self.setWindowTitle('Path Length')
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.plot()

    def createFigure(self):
        dpi = 100
        self.figure = Figure((5.0, 6.0), dpi=dpi)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self)

        self.axes = self.figure.add_subplot(111)
        self.canvas.mpl_connect('pick_event', self.pickEvent)

        self.main_layout.addWidget(self.canvas)

    def plot(self, index=0):
        self.axes.clear()

        if self.simulation.compute_path_length:
            path_length = list(zip(*self.simulation.path_lengths[index]))
            names = self.simulation.detector_names
            label = np.arange(1, len(path_length[0]) + 1)
            self.axes.set_xticks(label)
            for i in range(len(path_length)):
                self.axes.plot(label, path_length[i], '+--', label=names[i], picker=self.line_picker)

            self.axes.legend()
        else:
            self.axes.set_xticks([1, 2, 3, 4])
        self.axes.set_xlabel('Measurement Point', labelpad=10)
        self.axes.set_ylabel('Path Length (mm)')
        self.axes.grid(self.grid_button.isChecked())
        self.canvas.draw()

    def line_picker(self, line, event):
        """
        find the points within a certain distance from the mouseclick in
        data coords and attach some extra attributes, pickx and picky
        which are the data points that were picked
        """
        if event.xdata is None:
            return False, dict()
        x_data = line.get_xdata()
        y_data = line.get_ydata()
        maxd = 0.5
        d = np.sqrt((x_data - event.xdata) ** 2. + (y_data - event.ydata) ** 2.)
        print(x_data, y_data)
        ind = np.nonzero(np.less_equal(d, maxd))[0]
        if ind.size != 0:
            pick_y = np.take(y_data, ind[0])
            props = dict(ind=ind, pick_y=pick_y)
            return True, props
        else:
            return False, dict()

    def pickEvent(self, event):
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), f'{event.pick_y:.3f}')