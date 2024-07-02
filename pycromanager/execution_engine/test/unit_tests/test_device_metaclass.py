import pytest
from unittest.mock import MagicMock, call
from typing import Any

# Assuming these are imported from your actual implementation
from pycromanager.execution_engine.internal.device import (Device, AttrGetAcquisitionEvent,
                                                           AttrSetAcquisitionEvent, MethodCallAcquisitionEvent)



class MockExecutionEngine:
    def __init__(self):
        self.execute = MagicMock()
        self.execute.return_value.await_execution = MagicMock()

    def reset_mock(self):
        self.execute.reset_mock()
        self.execute.return_value.await_execution.reset_mock()

    def submit(self, event: Any):
        return self.execute(event)


@pytest.fixture
def mock_executor():
    return MockExecutionEngine()


class TestDevice(Device):
    def __init__(self, executor):
        self._executor = executor
        self.public_attr = 0

    def public_method(self, arg):
        return arg * 2

    def _private_method(self):
        return "private"


@pytest.fixture
def test_device(mock_executor):
    return TestDevice(mock_executor)


def test_public_method_call(test_device, mock_executor):
    """
    Test that public method calls are intercepted and executed through the executor.

    This test verifies:
    1. The executor's execute method is called once.
    2. A MethodCallAcquisitionEvent is created with the correct method name and arguments.
    3. The await_execution method of the executor is called.
    4. The correct result is returned from the method.
    """
    result = test_device.public_method(5)

    # check for only one MethodCallAcquisitionEvent in the calls (other types of events are ok)
    # get the list of method calls events
    method_call_events = [call[0][0] for call in mock_executor.execute.call_args_list if isinstance(call[0][0], MethodCallAcquisitionEvent)]
    assert len(method_call_events) == 1, "MethodCallAcquisitionEvent was not created"
    method_call_event = method_call_events[0]

    assert method_call_event is not None, "MethodCallAcquisitionEvent was not created"
    assert method_call_event.method_name == 'public_method'
    assert method_call_event.args == (5,)

    mock_executor.execute.return_value.await_execution.assert_called()
    assert result == mock_executor.execute.return_value.await_execution.return_value

def test_private_method_call(test_device, mock_executor):
    """
    Test that private method calls (methods starting with '_') are not intercepted and run on the executor.
    """
    result = test_device._private_method()

    # search through the calls to see if there is one with a MethodCallAcquisitionEvent with this name
    method_call_events = [call[0][0] for call in mock_executor.execute.call_args_list if isinstance(call[0][0], MethodCallAcquisitionEvent)]
    assert len(method_call_events) == 0, "MethodCallAcquisitionEvent was created for a private method"


def test_public_attribute_get(test_device, mock_executor):
    """
    Test that getting a public attribute is intercepted and executed through the executor.

    This test verifies:
    1. The executor's execute method is called once.
    2. An AttrAccessAcquisitionEvent is created with the correct attribute name.
    """
    _ = test_device.public_attr

    # get the list of attribute access events
    attr_access_events = [call[0][0] for call in mock_executor.execute.call_args_list if isinstance(call[0][0], AttrGetAcquisitionEvent)]
    # filter to only AttrAccessAcquisitionEvents with the correct attribute name
    attr_access_events = [event for event in attr_access_events if event.attr_name == 'public_attr']
    # check for only one AttrAccessAcquisitionEvent in the calls (other types of events are ok)
    assert len(attr_access_events) == 1, "AttrAccessAcquisitionEvent was not created"


def test_public_attribute_set(test_device, mock_executor):
    """
    Test that setting a public attribute is intercepted and executed through the executor.

    This test verifies:
    1. The executor's execute method is called once.
    2. An AttrSetAcquisitionEvent is created with the correct attribute name and value.
    """
    test_device.public_attr = 10

    # get the list of attribute set events
    attr_set_events = [call[0][0] for call in mock_executor.execute.call_args_list if isinstance(call[0][0], AttrSetAcquisitionEvent)]
    # valled once on initialization and once on setting the attribute
    assert len(attr_set_events) == 2, "AttrSetAcquisitionEvent was not created"
    attr_set_event = attr_set_events[1]

    assert attr_set_event.attr_name == 'public_attr'
    assert attr_set_event.value == 10

def test_private_attribute_access(test_device, mock_executor):
    """
    Test that accessing private attributes (attributes starting with '_') is not intercepted.

    This test verifies:
    1. Setting and getting a private attribute does not involve the executor.
    2. The private attribute can be set and retrieved directly.
    """
    test_device._private_attr = 20
    assert test_device._private_attr == 20

if __name__ == "__main__":
    pytest.main()