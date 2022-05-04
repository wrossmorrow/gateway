from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.duration_pb2 import Duration

class Timer:
    """ Simple timer object implementing the "with" 
    interface for capturing start, end, and duration
    of a block of compute. Uses protobuf objects. 
    """

    def __init__(self):
        self.start, self.end = Timestamp(), Timestamp()
        self.duration = Duration()

    def __enter__(self):
        self.start.GetCurrentTime()

    def __exit__(self, exc_type, exc_value, exc_trace):
        self.end.GetCurrentTime()
        self.duration.FromNanoseconds( 
            self.end.ToNanoseconds() - self.start.ToNanoseconds()
        )