'''
AppError 类：
    为应用错误提供异常类
'''

class AppError(Exception):
    title = "Error!"
    message = "Application error"
    def __init__(self, message = None):
        if message is not None:
            self.message = message

class DataFileNotOpenedError(AppError):
    title = "DataFileNotOpenedError"
    message = "Data file has not been opened!"

class RootFileNotOpenedError(AppError):
    title = "RootFileNotOpenedError"
    message = "Root file has not been opened!"

class OptimalFilterCreatedError(AppError):
    title = "OptimalFilterCreatedError"
    message = "Optimal filter has not been created!"

class CutNotAppliedError(AppError):
    title = "CutNotAppliedError"
    message = "Cut has not been applied!"

class BinFileInfoChangedError(AppError):
    title = "BinFileInfoChangedError"
    message = "This BIN2 file is encoded, and its info cannot be changed! \n If you insist to change the info, please use recode method to change the header."

class ParasChangedError(AppError):
    title = "ParasChangedError"
    message = ""

class SignalTemplateNotGoodError(AppError):
    title = "SignalTemplateNotGoodError"
    message = "Signal template is not good, please construct a good signal template."

class FilterNotConstructedError(AppError):
    title = "FilterNotConstructedError"
    message = "Filter has not been constructed!"
