from PyQt5 import QtCore, QtWidgets, QtGui
from ui.main_window import Ui_MainWindow
import datetime
import os
import pandas as pd
import numpy as np
import cv2
import time
import gc

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

class LeafScanner:
    def __init__(self):
        self.app = self.setup_app()
        self.window = MainWindow()

        self.field_name = self.window.ui.field_name_combo.currentText()
        
        self.date = datetime.datetime.now().strftime("%Y-%m-%d")
        self.data_path, self.field_path, self.date_path = self.setup_data_directories(self.field_name, self.date)

        self.datasheet = None
        self.load_datasheet()
        self.datasheet_index = 0
        self.plot = None
        self.plant = None
        self.scan = None

        self.sample_id = f'{self.field_name}_{self.date}_{self.plot}_{self.plant}_{self.scan}'

        # Change this to folder where scanner is placing images
        self.scan_dir = os.path.join('scan_dir')
        self.scan_path = None

        # Make sure there are no existing files in this directory

        self.new_scan_path = os.path.join(self.date_path, self.sample_id + '.png')

        self.window.ui.harvest_combo.currentIndexChanged.connect(self.load_datasheet)

        self.window.ui.harvest_combo.currentIndexChanged.connect(self.sample_changed)
        self.window.ui.plot_spin.valueChanged.connect(self.sample_changed)
        self.window.ui.plant_spin.valueChanged.connect(self.sample_changed)
        self.window.ui.scan_spin.valueChanged.connect(self.sample_changed)
        self.window.ui.next_plant.clicked.connect(self.next_plant)
        self.window.ui.next_scan.clicked.connect(self.next_scan)
        self.window.ui.delete_scan.clicked.connect(self.delete_message)

        self.window.ui.scan_scene = QtWidgets.QGraphicsScene()
        self.window.ui.pixmap = QtWidgets.QGraphicsPixmapItem()
        self.window.ui.scan_view.setScene(self.window.ui.scan_scene)


        self.scan_checking_thread = QtCore.QThread()
        self.scan_checker = ScanChecker(self.scan_dir)
        self.scan_checker.moveToThread(self.scan_checking_thread)
        #self.scan_checker.new_scan_detected.connect(self.scan_checking_thread.quit)
        self.scan_checker.new_scan_detected.connect(self.process_scan)
        self.scan_checking_thread.start()

        self.scan_checking_timer = QtCore.QTimer(interval=1000, timeout=self.scan_checker.check_for_new_scan)
        # self.scan_checking_timer = QtCore.QTimer(interval=1000, timeout=self.check_for_new_scan)
        self.scan_checking_timer.start()

        self.initial_image_loaded = False
        self.load_initial_image_timer = QtCore.QTimer(interval=2000, timeout=self.load_initial_image)
        self.load_initial_image_timer.start()

        self.pix_map = None
        #self.scan_processing_thread = QtCore.QThread()
        #self.scan_processing_timer = QtCore.QTimer(interval=2000, timeout=self.process_scan)
        #self.scan_processing_timer.start()
        #

    @staticmethod
    def setup_app():
        app = QtWidgets.QApplication([])
        app.setStyle('Fusion')

        return app

    @staticmethod
    def app_exec(app):
        app.exec_()

    def load_initial_image(self):
        if not self.initial_image_loaded:
            self.sample_changed()
            self.initial_image_loaded = True
            self.load_initial_image_timer.stop()


    def setup_data_directories(self, field_name, date):
        if not os.path.exists('scan_dir'):
            os.mkdir('scan_dir')

        data_path = 'data'
        if not os.path.exists(data_path):
            os.mkdir(data_path)

        field_path = os.path.join(data_path, field_name)
        if not os.path.exists(field_path):
            os.mkdir(field_path)

        date_path = os.path.join(field_path, date)
        if not os.path.exists(date_path):
            os.mkdir(date_path)

        return data_path, field_path, date_path

    def load_datasheet(self):
        sheet_number = self.window.ui.harvest_combo.currentText()
        file_name = f'leaf_harvest_date_{sheet_number}.xlsx'
        file_path = os.path.join(self.field_path, 'datasheets', file_name)
        df = pd.read_excel(file_path)

        self.plot = int(df['plot'][0])
        self.plant = int(df['plant'][0])
        self.scan = 1

        self.window.ui.plot_spin.setValue(self.plot)
        self.window.ui.plant_spin.setValue(self.plant)
        self.window.ui.scan_spin.setValue(self.scan)

        self.datasheet = df

    def process_scan(self):

        self.scan_checking_timer.stop()

        while True:
            try:
                files = os.listdir(self.scan_dir)
                break
            except Exception as e:
                print(f'Listdir error: {e}. Retrying in 2 seconds...')
                time.sleep(2)

        print(f'File(s) received by process_scan: {files}')
        for file in files:
            file_path = os.path.join(self.scan_dir, file)
            self.scan_path = file_path


        # Since file may not be done writing to the directory before attempting to read it
        # Try reading file and transposing it... reading only give warning, but transpose will raise error
        # Sometimes transposing works, but fails later... that's why this whole code block is in one try/except
        # Low memory may also be an issue
        while True:
            try:
                scan = cv2.imread(self.scan_path)
                transposed = cv2.transpose(scan)
                scan = None
                flipped = cv2.flip(transposed, flipCode=1)
                transposed = None
                self.scan_image = flipped
                flipped = None

                gc.collect()


                self.write_scan()
                os.remove(self.scan_path)
                self.show_scan()
                self.window.ui.delete_scan.setVisible(True)
                break
            except Exception as e:
                print(f'Processing error: {e}. Retrying in 2 seconds...')
                time.sleep(2)

        print('Process scan done.')
        self.scan_checking_timer.start()

    def write_scan(self):
        print('Writing scan started')
        new_path = os.path.join(self.date_path, self.sample_id + '.png')
        print(f'Scan will be written to {new_path}')
        if os.path.exists(new_path):
            self.overwrite_message()
            if self.overwrite is True:
                written = cv2.imwrite(new_path, self.scan_image)
                print(f'Overwritten: {written}')
                self.overwrite = False
            else:
                print('Image is not overwritten')
        else:
            written = cv2.imwrite(new_path, self.scan_image)
            print(f'Written: {written}')



    def show_scan(self):
        print('Show scan started')

        resized = cv2.resize(self.scan_image, (1360, 960))
        qt_scan = np.require(resized, np.uint8, 'C')
        resized = None
        qt_scan = QtGui.QImage(qt_scan, 1360, 960, QtGui.QImage.Format_RGB888).rgbSwapped()
        self.pix_map = QtGui.QPixmap(qt_scan)
        qt_scan = None

        gc.collect()

        self.window.ui.scan_scene = QtWidgets.QGraphicsScene()  # Resets scene, but probably should just remove existing items
        self.window.ui.pixmap = QtWidgets.QGraphicsPixmapItem()
        self.window.ui.scan_view.setScene(self.window.ui.scan_scene)

        self.pix_map.detach()

        self.window.ui.pixmap.setPixmap(self.pix_map)
        self.window.ui.scan_scene.addItem(self.window.ui.pixmap)

        if self.scan == 1:
            scan_type = 'Sheath Scan'
        elif self.scan >= 2:
            scan_type = 'Leaf Scan'
        else:
            scan_type = ''

        self.window.ui.scan_scene.addText(f'Plot: {self.plot}, Plant: {self.plant}, Scan: {self.scan} ({scan_type})',
                                          QtGui.QFont('Helvetica', 35, QtGui.QFont.Light)).setDefaultTextColor(
            QtGui.QColor.fromRgb(255, 255, 255))
        print('Show scan almost finished')
        QtWidgets.QApplication.processEvents()

        print('Show scan finished')

    def delete_message(self):
        msg = QtWidgets.QMessageBox(self.window)
        msg.setWindowTitle("Delete Confirmation")
        msg.setText("Are you sure you want to delete this scan?")
        msg.setIcon(QtWidgets.QMessageBox.Question)
        msg.setStandardButtons(QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes)
        msg.setDefaultButton(QtWidgets.QMessageBox.Yes)
        msg.buttonClicked.connect(self.delete_scan)

        msg.exec_()

    def delete_scan(self, message):
        text = message.text()
        if text == '&Yes':
            if os.path.exists(self.new_scan_path):
                os.remove(self.new_scan_path)
                self.window.ui.delete_scan.setVisible(False)
            self.sample_changed()

    def overwrite_message(self):
        msg = QtWidgets.QMessageBox(self.window)
        msg.setWindowTitle("Overwrite Confirmation")
        msg.setText("Are you sure you want to overwrite this scan?")
        msg.setIcon(QtWidgets.QMessageBox.Question)
        msg.setStandardButtons(QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes)
        msg.setDefaultButton(QtWidgets.QMessageBox.Yes)
        msg.buttonClicked.connect(self.confirm_overwrite)

        msg.exec_()

    def confirm_overwrite(self, message):
        text = message.text()
        if text == '&Yes':
            self.overwrite = True
        else:
            self.overwrite = False

    def start(self):
        self.app.exec_()
        self.next_plant()

    def next_plant(self):
        self.datasheet_index += 1

        # Might run into issue if index extends beyond df length
        datasheet_len = len(self.datasheet)

        if self.datasheet_index < datasheet_len:
            self.plot = int(self.datasheet['plot'][self.datasheet_index])
            self.window.ui.plot_spin.setValue(self.plot)
            self.plant = int(self.datasheet['plant'][self.datasheet_index])
            self.window.ui.plant_spin.setValue(self.plant)
            self.scan = 1
            self.window.ui.scan_spin.setValue(self.scan)
            self.sample_changed()
        else:
            msg = QtWidgets.QMessageBox(self.window)
            msg.setWindowTitle("Datasheet Finished")
            msg.setText("You have reached the end of the datasheet. \n\nUnless something has gone terribly wrong, "
                        "this means you are done for the day! \n\nCongrats!")
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setStandardButtons(QtWidgets.QMessageBox.Close)
            msg.setDefaultButton(QtWidgets.QMessageBox.Close)

            msg.exec_()

    def next_scan(self):
        self.scan += 1
        self.window.ui.scan_spin.setValue(self.scan)
        self.sample_changed()

    def sample_changed(self):
        self.field_name = self.window.ui.field_name_combo.currentText()
        self.plot = int(self.window.ui.plot_spin.text())
        self.plant = int(self.window.ui.plant_spin.text())
        self.scan = int(self.window.ui.scan_spin.text())
        self.sample_id = f'{self.field_name}_{self.date}_{self.plot}_{self.plant}_{self.scan}'
        self.new_scan_path = os.path.join(self.date_path, self.sample_id + '.png')

        self.scan_image = None
        gc.collect()

        if os.path.exists(self.new_scan_path):
            self.scan_image = cv2.imread(self.new_scan_path)
            self.window.ui.delete_scan.setVisible(True)
        else:
            self.scan_image = np.zeros((960, 1360, 3), dtype=np.uint8) # Does this need to be full size? (9600, 13600, 3)
            self.window.ui.delete_scan.setVisible(False)
        self.show_scan()


class ScanChecker(QtCore.QObject):
    new_scan_detected = QtCore.pyqtSignal()

    def __init__(self, scan_dir):
        super().__init__()
        self.scan_dir = scan_dir

    @QtCore.pyqtSlot()
    def check_for_new_scan(self):
        files = os.listdir(self.scan_dir)
        if len(files) > 0:
            print(f'New file(s) found: {files}')
            self.new_scan_detected.emit()


if __name__ == '__main__':
    scanner = LeafScanner()
    scanner.window.show()
    scanner.start()
