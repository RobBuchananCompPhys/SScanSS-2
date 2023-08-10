"""
Class for JSON text editor
"""
from PyQt6 import QtGui, QtCore
from PyQt6.Qsci import QsciScintilla, QsciLexerJSON, QsciAPIs
from autocomplete import instrument_autocompletions

char_dict={"{":"}","[":"]","(":")","'":"'",'"':'"'}

class Editor(QsciScintilla):
    """Creates a QScintilla text editor with JSON Lexer

    :param parent: main window instance
    :type parent: MainWindow
    """
    def __init__(self, parent):

        super().__init__(parent)

        self.parent = parent

        self.updateFont()
        self.setMarginsFont(self.font())
        font_metrics = QtGui.QFontMetrics(self.font())
        self.setMarginsFont(self.font())
        self.setMarginWidth(0, font_metrics.horizontalAdvance("00000") + 6)
        self.setMarginLineNumbers(0, True)
        self.setMarginsBackgroundColor(QtGui.QColor("#cccccc"))
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QtGui.QColor("#ffe4e4"))

        self.editorLexer = QsciLexerJSON()
        self.editorLexer.setDefaultFont(self.font())
        
        self.api = QsciAPIs(self.editorLexer)
        for enum in instrument_autocompletions:
            for keyword in enum:
                descriptor = f'TYPE={keyword.value.Type}, OPTIONAL={keyword.value.Optional}, DESCRIPTION={keyword.value.Description}'
                self.api.add(f"{keyword.value.Key} - {descriptor}")
        self.api.prepare()
        
        self.setLexer(self.editorLexer)
        self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, 1, b'Courier')

        self.setAutoCompletionThreshold(1)
        self.setAutoCompletionCaseSensitivity(False)
        self.setAutoCompletionSource(self.AutoCompletionSource.AcsAPIs)

        self.setScrollWidth(1)
        self.setEolMode(QsciScintilla.EolMode.EolUnix)
        self.setScrollWidthTracking(True)
        self.setMinimumSize(200, 200)
        self.setFolding(QsciScintilla.FoldStyle.PlainFoldStyle)
        self.setIndentationsUseTabs(False)
        self.setIndentationGuides(True)
        self.setAutoIndent(True)
        self.setTabWidth(4)

    def updateFont(self):
        """Updates the editor font"""
        font = QtGui.QFont()
        font.setFamily(self.parent.editor_font_family)
        font.setFixedPitch(True)
        font.setPointSize(self.parent.editor_font_size)
        self.setFont(font)

    def keyPressEvent(self, event):
        if event.text() in char_dict.keys():
            init_pos = self.cursor().pos()
            self.append(char_dict[event.text()])
            self.cursor().setPos(init_pos)
        super().keyPressEvent(event)



        


