class Log:
    def __init__(self):
        self.new_log = False
        self.logs = []
        # self.current_index = 0
        # self.socket = None
    def add_log(self, message):
        self.new_log = True
        self.logs.append(message)

    # def set_socket(self, socket):
    #     self.socket = socket
    def get_logs(self):
        self.new_log = False
        # log = "\n".join(self.logs[self.current_index:])
        # self.current_index = len(self.logs) - 1
        return self.logs[-1]


log_service = Log()


