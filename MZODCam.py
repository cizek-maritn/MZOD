import time

from pypylon import pylon


# Basler camera wrapper: holds all pylon objects and hides pylon details from the application
class MZODCam:
    def __init__(self, trigger_time=200):
        # basler tl_factory and enumerated devices
        self.tl_factory = None
        self.devices = None
        # basler camera instance (pylon.InstantCamera), None when not connected
        self.PylonCamera = None
        # basler converter
        self.converter = None

        # True when camera supports frame trigger ready wait (trigger mode), detected on first trigger
        self.sw_trigger = None
        # time.perf_counter() of the last trigger
        self.last_trigger_time = 0.0

        self._trigger_time = trigger_time

        # parameter changes waiting for the next trigger: {param: value}, applied in insertion order.
        # some params cannot be changed while grabbing, so they are applied with grabbing stopped.
        self.parameter_queue = {}
        # last value requested for each param, used to ignore repeated requests of the same value
        self._requested = {}
    # maximum time [ms] to wait for the camera to be ready for the trigger
    @property
    def trigger_time(self):
        return self._trigger_time

    @trigger_time.setter
    def trigger_time(self, value):
        self._trigger_time = int(value)

    @property
    def is_connected(self):
        return self.PylonCamera is not None

    # returns camera model names list
    # populates devices prop.
    def get_available_cameras(self):
        self.tl_factory = pylon.TlFactory.GetInstance()
        self.devices = self.tl_factory.EnumerateDevices()
        if not self.devices:
            print("No camera found")
            # raise Exception("No camera found")
        model_name_list = []
        # return list of all cameras
        for dev_info in self.devices:
            # do not connect to emulator
            model_name_list.append(dev_info.GetModelName())
        return model_name_list

    # connects to the first camera with given model name and starts grabbing
    def connect(self, model_name):
        if self.is_connected:
            self.disconnect()
        if self.devices is None:
            self.get_available_cameras()

        camera = None
        for dev_info in self.devices:
            # connect to devices with selected model name
            if model_name == dev_info.GetModelName():
                camera = pylon.InstantCamera(self.tl_factory.CreateDevice(dev_info))
                break

        # success
        if camera is None:
            raise Exception('Failed to connect to the camera')
        self.PylonCamera = camera

        # register configuration for triggered grabbing
        self.PylonCamera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(),
                                               pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)

        # configuration for continuous grabbing
        # this is not convenient for us, since some task will require more time
        # self.PylonCamera.RegisterConfiguration(pylon.AcquireContinuousConfiguration(),
        #                                        pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)

        # converter
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_Mono8
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        # open camera, start grabbing
        self.PylonCamera.Open()
        self.PylonCamera.StartGrabbing(pylon.GrabStrategy_OneByOne)

        self.sw_trigger = None
        self.last_trigger_time = 0.0
        self.parameter_queue.clear()
        self._requested.clear()

    # stops grabbing and closes the camera
    def disconnect(self):
        if self.PylonCamera is not None:
            self.stop()
            self.PylonCamera.Close()
        self.PylonCamera = None
        self.converter = None
        self.parameter_queue.clear()
        self._requested.clear()

    # camera stop
    def stop(self):
        if self.PylonCamera is not None:
            self.PylonCamera.StopGrabbing()

    # converts grab result using converter, returns numpy array
    def convert(self, grab_result):
        return self.converter.Convert(grab_result).GetArray()

    # trigger camera and return grab result / None
    def trigger(self):
        if self.PylonCamera is None:
            return None

        self._apply_parameter_queue()

        # run only once and only in trigger mode
        if self.sw_trigger is None:
            self.sw_trigger = True
            try:
                self.PylonCamera.WaitForFrameTriggerReady(self.trigger_time, pylon.TimeoutHandling_ThrowException)
            except pylon.GenericException:
                self.sw_trigger = False

        self.last_trigger_time = time.perf_counter()
        if self.sw_trigger:
            if self.PylonCamera.WaitForFrameTriggerReady(self.trigger_time, pylon.TimeoutHandling_Return):
                self.PylonCamera.ExecuteSoftwareTrigger()
            else:
                return None
        else:
            # should do some trigger time loop
            self.PylonCamera.ExecuteSoftwareTrigger()

        # blocks until the frame arrives
        grab_result = self.PylonCamera.RetrieveResult(1000, pylon.TimeoutHandling_Return)
        if grab_result is None:
            return None
        if not grab_result.GrabSucceeded():
            grab_result.Release()
            return None

        return grab_result

    # requests camera parameter change - applicable on Basler cameras only
    # param is str - parameter to be changed
    # value is value to be set
    # the change is queued and applied before the next trigger, so get_param may return the old value until then.
    # returns False when not connected, True otherwise (invalid values are reported when the queue is applied)
    def set_param(self, param, value):
        if self.PylonCamera is None:
            return False
        if param in self._requested and self._requested[param] == value \
                and type(self._requested[param]) is type(value):
            return True
        self._requested[param] = value
        # re-queued param moves to the end, so the latest request wins
        self.parameter_queue.pop(param, None)
        self.parameter_queue[param] = value
        return True

    # applies queued parameter changes with grabbing stopped, then restarts grabbing
    def _apply_parameter_queue(self):
        if not self.parameter_queue:
            return
        queue = list(self.parameter_queue.items())
        self.parameter_queue.clear()
        was_grabbing = self.PylonCamera.IsGrabbing()
        if was_grabbing:
            self.PylonCamera.StopGrabbing()
        try:
            for param, value in queue:
                if not self._set_param(param, value):
                    # forget the failed value so the same request can be retried
                    self._requested.pop(param, None)
        finally:
            if was_grabbing:
                self.PylonCamera.StartGrabbing(pylon.GrabStrategy_OneByOne)

    # sets camera parameter immediately, returns True on success
    def _set_param(self, param, value):
        if self.PylonCamera is None:
            return False
        try:
            if param in dir(self.PylonCamera):
                node = getattr(self.PylonCamera, param)
                if type(value) is str:
                    # check symbolics
                    if value in node.GetSymbolics():
                        node.SetValue(value)
                    else:
                        print('Value {} of param{} is out of available values {}\r\n'.format(
                            value, param, node.GetSymbolics()))
                        return False
                else:
                    if type(value) is bool:
                        node.SetValue(value)
                    else:
                        if node.GetMin() <= value <= node.GetMax():
                            node.SetValue(value)
                        else:
                            print('Value {} of {} out of bounds {},{}\r\n'.format(
                                value, param, node.GetMin(), node.GetMax()))
                            return False
            else:
                print('Param {} is not supported with this camera\r\n'.format(param))
                return False
        except pylon.GenericException as err:
            print('ERROR;Pylon exception while setting {} {} {}\r\n'.format(value, param, err))
            return False
        return True

    # returns current value of given camera parameter
    # returns value or none
    def get_param(self, param, silent=False):
        try:
            return getattr(self.PylonCamera, param).GetValue()
        except (pylon.GenericException, AttributeError) as err:
            if not silent:
                print('Pylon exception\r\n{}\r\n'.format(err))
        return None

    # return low and high bounds of given camera param
    # returns min, max if param is available, None if not.
    def get_bounds(self, param, silent=False):
        try:
            if param in dir(self.PylonCamera):
                node = getattr(self.PylonCamera, param)
                if 'GetMin' in dir(node):
                    return node.GetMin(), node.GetMax()
                else:
                    return node.GetSymbolics()
        except pylon.GenericException as err:
            if not silent:
                print('Pylon exception\r\n{}\r\n'.format(err))
        return None
