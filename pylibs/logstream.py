import threading
import os

class LogStream(threading.Thread):
    """Provide an interface to redirect stdio/stdin to a logging instance."""
    def __init__(self, log_level):
        threading.Thread.__init__(self)
        self.log_level = log_level
        self.fd_read, self.fd_write = os.pipe()
        self.pipe = os.fdopen(self.fd_read)
        self.start()

    def run(self):
        for line in iter(self.pipe.readline, ''):
            self.log_level(line.strip('\n'))

        self.pipe.close()

    def join(self, timeout=1):
        self.close()
        super(LogStream, self).join(timeout)

    def close(self):
        os.close(self.fd_write)

    def fileno(self):
        return self.fd_write
