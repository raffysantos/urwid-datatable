#!/usr/bin/env python
from __future__ import division
import logging
logger = logging.getLogger(__name__)

import urwid
import urwid.raw_display
import random
import string
from datetime import datetime, timedelta, date
from operator import itemgetter


DEFAULT_BORDER_WIDTH = 1
DEFAULT_BORDER_CHAR = " "
DEFAULT_BORDER_ATTR = "table_border"
DEFAULT_CELL_PADDING = 1

intersperse = lambda e,l: sum([[x, e] for x in l],[])[:-1]

class DataTableHeaderLabel(str):
    pass

class ScrollingListBox(urwid.ListBox):

    signals = ["select",
               "drag_start", "drag_continue", "drag_stop",
               "load_more"]

    def __init__(self, body, infinite = False):
        self.mouse_state = 0
        self.drag_from = None
        self.drag_last = None
        self.drag_to = None
        self.requery = False
        self.infinite = infinite
        super(ScrollingListBox, self).__init__(body)


    # @property
    # def contents(self):
    #     return super(ScrollingListBox, self).contents()

    def mouse_event(self, size, event, button, col, row, focus):
        """Overrides ListBox.mouse_event method.

        Implements mouse scrolling.
        """
        if row < 0 or row >= len(self.body):
            return
        if event == 'mouse press':
            if button == 1:
                self.mouse_state = 1
                self.drag_from = self.drag_last = (col, row)
            elif button == 4:
                # for _ in range(3):
                #     self.keypress(size, 'up')
                pct = self.focus_position / len(self.body)
                self.set_focus_valign(('relative', pct - 10))
                self._invalidate()
                return True
            elif button == 5:
                # for _ in range(3):
                #     self.keypress(size, 'down')
                pct = self.focus_position / len(self.body)
                self.set_focus_valign(('relative', pct + 5))
                self._invalidate()
                return True
        elif event == 'mouse drag':
            if self.drag_from is None:
                return
            if button == 1:
                self.drag_to = (col, row)
                if self.mouse_state == 1:
                    self.mouse_state = 2
                    urwid.signals.emit_signal(
                        self, "drag_start",self, self.drag_from
                    )
                    # self.on_drag_start(self.drag_from)
                else:
                    urwid.signals.emit_signal(
                        self, "drag_continue",self,
                        self.drag_last, self.drag_to
                    )

            self.drag_last = (col, row)

        elif event == 'mouse release':
            if self.mouse_state == 2:
                self.drag_to = (col, row)
                urwid.signals.emit_signal(
                    self, "drag_stop",self, self.drag_from, self.drag_to
                )
            self.mouse_state = 0
        return self.__super.mouse_event(size, event, button, col, row, focus)


    def keypress(self, size, key):
        """Overrides ListBox.keypress method.

        Implements vim-like scrolling.
        """
        if len(self.body):
            if key == 'j':
                self.keypress(size, 'down')
            elif key == 'k':
                self.keypress(size, 'up')
            elif key == 'g':
                self.focus_position = 0
            elif key == 'G':
                self.focus_position = len(self.body) - 1
                self.set_focus_valign('bottom')
            elif key == 'home':
                self.focus_position = 0
                self._invalidate()
            elif key == 'end':
                self.focus_position = len(self.body)-1
                self._invalidate()
            elif (self.infinite
                  and key in ['page down', "down"]
                  and self.focus_position == len(self.body)-1):
                self.requery = True
                self._invalidate()
            elif key == "enter":
                urwid.signals.emit_signal(self, "select", self, self.selection)
            else:
                return super(ScrollingListBox, self).keypress(size, key)
        else:
            return super(ScrollingListBox, self).keypress(size, key)

    @property
    def selection(self):

        if len(self.body):
            return self.body[self.focus_position]


    def render(self, size, focus=False):
        maxcol, maxrow = size
        if self.requery and "bottom" in self.ends_visible(
                (maxcol, maxrow) ):
            self.requery = False
            urwid.signals.emit_signal(
                self, "load_more", len(self.body))

        return super(ScrollingListBox, self).render( (maxcol, maxrow), focus)


    def disable(self):
        self.selectable = lambda: False

    def enable(self):
        self.selectable = lambda: True


class ListBoxScrollBar(urwid.WidgetWrap):


    def __init__(self, parent):
        self.parent = parent
        self.pile = urwid.Pile([])
        self.pile.contents.append(
            (urwid.Text("."), self.pile.options("pack"))
        )
        super(ListBoxScrollBar, self).__init__(self.pile)

    def update(self, size, offset, inset, middle, top, bottom):

        width, height = size
        del self.pile.contents[:]
        # raise Exception(bottom)
        # limit = len(self.parent.body) if len(self.parent.body) > height else
        scroll_position = int(
            (self.parent.focus_position) / len(self.parent.body) * height
        )
        for i in range(height):
            if i == scroll_position:
                # marker = "* %d,%d,%d,%d,%s" %(i, self.parent.focus_position, offset, scroll_position, middle[0])
                marker = u"\N{LIGHT SHADE}"
            else:
                marker = " "
                # marker = "  %d,%d,%d,%d,%s" %(i, self.parent.focus_position, offset, scroll_position, middle[0])
            # marker = "%d, %d" %(self.parent.listbox.get_focus_offset_inset(size))
            self.pile.contents.append(
                (urwid.Text(marker), self.pile.options("pack"))
            )
        self._invalidate()


class ScrollingListBoxWithScrollbar(urwid.WidgetWrap):

    signals = ScrollingListBox.signals

    def __init__(self, *args, **kwargs):
        self.listbox = ScrollingListBox(*args, **kwargs)
        self.scroll_bar = ListBoxScrollBar(self)
        self.columns = urwid.Columns([
            (1, self.scroll_bar),
            ('weight', 3, self.listbox),
        ])
        # self.filler = urwid.Filler(self.columns)

        self.pile = urwid.Pile([
            ('weight', 1, self.columns)
         ])
        super(ScrollingListBoxWithScrollbar, self).__init__(self.pile)

    def render(self, size, focus=False):
        (offset, inset) = self.listbox.get_focus_offset_inset(size)
        (middle, top, bottom) = self.listbox.calculate_visible(size, focus)
        self.scroll_bar.update(size, offset, inset, middle, top, bottom)
        return super(ScrollingListBoxWithScrollbar, self).render(size, focus)

    @property
    def body(self):
        return self.listbox.body

    @property
    def focus_position(self):
        return self.listbox.focus_position

    @focus_position.setter
    def focus_position(self, value):
        self.listbox.focus_position = value


class DataTableColumn(object):

    def __init__(self, name, label=None, width=('weight', 1),
                 align="left", wrap="space", padding = None,
                 format_fn=None, attr = None,
                 sort_key = None, sort_fn = None,
                 footer_fn = None,
                 attr_map = None, focus_map = None):

        self.name = name
        self.label = label if label else name
        self.width = width
        self.align = align
        self.wrap = wrap
        self.padding = padding
        self.format_fn = format_fn
        self.attr = attr
        self.sort_key = sort_key
        self.sort_fn = sort_fn
        self.footer_fn = footer_fn
        self.attr_map = attr_map if attr_map else {}
        self.focus_map = focus_map if focus_map else {}
        if isinstance(self.width, tuple):
            if self.width[0] != "weight":
                raise Exception(
                    "Column width %s not supported" %(col.width[0])
                )
            self.sizing, self.width = self.width
        else:
            self.sizing = "given"


    def _format(self, v):

        if isinstance(v, DataTableHeaderLabel):
            return urwid.Text(v, align=self.align, wrap=self.wrap)
        else:
            # First, call the format function for the column, if there is one
            if self.format_fn:
                try:
                    v = self.format_fn(v)
                except TypeError, e:
                    logger.info("format function raised exception: %s" %e)
                    return urwid.Text("", align=self.align, wrap=self.wrap)
                except:
                    raise
            return self.format(v)


    def format(self, v):

        # Do our best to make the value into something presentable
        if v is None:
            v = ""
        elif isinstance(v, int):
            v = "%d" %(v)
        elif isinstance(v, float):
            v = "%.03f" %(v)
        elif isinstance(v, datetime):
            v = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, date):
            v = v.strftime("%Y-%m-%d")

        if not isinstance(v, urwid.Widget):
            v = urwid.Text(v, align=self.align, wrap=self.wrap)
        return v

class DataTableCell(urwid.WidgetWrap):

    # attr_map = { None: "table_content" }
    # focus_map = { "table_content": "table_content focused" }

    signals = ["click", "select"]

    def __init__(self, table, column, row, value,
                 attr_map = None, focus_map = None,
                 *args, **kwargs):

        self.table = table
        self.column = column
        self.row = row
        self.value = value
        self.contents = self.column._format(self.value)

        self.attr_map = {}
        self.focus_map = {}

        if table.attr_map:
            self.attr_map.update(table.attr_map)
        if column.attr_map:
            self.attr_map.update(column.attr_map)
        if row.attr_map:
            self.attr_map.update(row.attr_map)
        if column.attr and isinstance(row.data, dict):
            a = row.data.get(column.attr, {})
            if isinstance(a, basestring):
                a = {None: a}
            self.attr_map.update(a)

        if attr_map:
            self.attr_map.update(attr_map)

        # if table.focus_map:
        #     self.attr_map.update(table.focus_map)
        if column.focus_map:
            self.focus_map.update(column.focus_map)
        if row.focus_map:
            self.focus_map.update(row.focus_map)
        if focus_map:
            self.focus_map.update(focus_map)

        # print "[%s] [%s]" %(self.attr_map, self.focus_map)

        # print self.focus_map
        padding = (self.column.padding
                   if self.column.padding
                   else self.table.padding)

        self.padding = urwid.Padding(self.contents,
                                     left=padding, right=padding)

        self.attr = urwid.AttrMap(self.padding,
                                  attr_map = self.attr_map,#)
                                  focus_map = self.focus_map)

        self.orig_attr_map = self.attr.get_attr_map()
        self.orig_focus_map = self.attr.get_focus_map()

        self.highlight_attr_map = self.attr.get_attr_map()
        for k in self.highlight_attr_map.keys():
            self.highlight_attr_map[k] = self.highlight_attr_map[k] + " column_focused"

        self.highlight_focus_map = self.attr.get_attr_map()
        for k in self.highlight_focus_map.keys():
            self.highlight_focus_map[k] = self.highlight_focus_map[k] + " column_focused focused"

        super(DataTableCell, self).__init__(self.attr)


    def selectable(self):
        return True

    def keypress(self, size, key):
        return super(DataTableCell, self).keypress(size, key)

    def highlight(self):
        self.attr.set_attr_map(self.highlight_attr_map)
        self.attr.set_focus_map(self.highlight_focus_map)

        # print self.attr_map

    def unhighlight(self):
        self.attr.set_attr_map(self.orig_attr_map)
        self.attr.set_focus_map(self.orig_focus_map)

    def keypress(self, size, key):
        if key != "enter":
            return key
        urwid.emit_signal(self, "select")

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press':
            urwid.emit_signal(self, "click")



class HeaderColumns(urwid.Columns):

    def __init__(self, contents, header = None):

        self.selected_column = None
        super(HeaderColumns, self).__init__(contents)


class BodyColumns(urwid.Columns):

    def __init__(self, contents, header = None):

        self.header = header
        super(BodyColumns, self).__init__(contents)


    @property
    def selected_column(self):

        # print "get focus_position"
        return self.header.selected_column

    @selected_column.setter
    def selected_column(self, value):
        return


class DataTableRow(urwid.WidgetWrap):

    column_class = urwid.Columns

    # attr_map = {}
    # focus_map = {}

    # border_attr_map = { None: "table_border" }
    # border_focus_map = { None: "table_border focused" }

    decorate = True

    def __init__(self, table, data,
                 header = None,
                 cell_click = None, cell_select = None,
                 border_attr_map = None, border_focus_map = None,
                 **kwargs):

        self.table = table
        self.data = data
        self.header = header
        self.cell_click = cell_click
        self.cell_select = cell_select
        # self.selected_column = None
        self.contents = []
        self._values = dict()

        if self.decorate:
            if table.attr_map:
                self.attr_map.update(table.attr_map)
            if table.focus_map:
                self.focus_map.update(table.focus_map)


        if border_attr_map:
            self.border_attr_map = border_attr_map
        else:
            self.border_attr_map = self.attr_map

        if border_focus_map:
            self.border_focus_map = border_focus_map
        else:
            self.border_focus_map = self.focus_map

        for i, col in enumerate(self.table.columns):
            l = list()
            if col.sizing == "weight":
                l += [col.sizing, col.width]
            else:
                l.append(col.width)

            if isinstance(self.data, (list, tuple)):
                val = self.data[i]
            elif isinstance(data, dict):
                val = data.get(col.name, None)
                # details = data.get(c.details, None)
            else:
                raise Exception(data)

            cell = DataTableCell(self.table, col, self, val)
            if self.cell_click:
                urwid.connect_signal(cell, 'click', self.cell_click, i*2)
            if self.cell_select:
                urwid.connect_signal(cell, 'select', self.cell_select, i*2)

            l.append(cell)
            self.contents.append(tuple(l))

        border_width = DEFAULT_BORDER_WIDTH
        border_char = DEFAULT_BORDER_CHAR
        border_attr = DEFAULT_BORDER_ATTR

        if isinstance(table.border, tuple):

            try:
                border_width, border_char, border_attr = table.border
            except IndexError:
                try:
                    border_width, border_char = table.border
                except Indexerror:
                    border_width = table.border

        elif isinstance(table.border, int):
            border_width = table.border

        else:
            raise Exception("Invalid border specification: %s" %(table.border))

        if self.header:
            self.row = self.column_class(self.contents, header = self.header)
        else:
            self.row = self.column_class(self.contents)

        self.row.contents = intersperse(
            (urwid.AttrMap(urwid.Divider(border_char),
                          attr_map = self.border_attr_map,
                          focus_map = self.border_focus_map),
             ('given', border_width, False)),
            self.row.contents)


        self.attr = urwid.AttrMap(self.row,
                                  attr_map = self.attr_map,
                                  focus_map = self.focus_map)

        super(DataTableRow, self).__init__(self.attr)


    def set_attr_map(self, attr_map):
        self.attr.set_attr_map(attr_map)

    def set_focus_map(self, focus_map):
        self.attr.set_focus_map(focus_map)

    def __len__(self): return len(self.contents)

    def __getitem__(self, i): return self.row.contents[i*2][0]

    def __delitem__(self, i): del self.row.contents[i*2]

    def __setitem__(self, i, v):

        self.row.contents[i*2] = (
            v, self.row.options(self.table.columns[i].sizing,
                                self.table.columns[i].width)
        )

    def selectable(self):
        return True

    def keypress(self, size, key):
        return super(DataTableRow, self).keypress(size, key)

    # def focus_position(self):
    #     return self.table.header.focus_position


    @property
    def focus_position(self):
        return self.row.focus_position

    @focus_position.setter
    def focus_position(self, value):
        self.row.focus_position = value

    @property
    def selected_column(self):
        return self.row.selected_column

    @selected_column.setter
    def selected_column(self, value):
        self.row.selected_column = value


    # def cycle_focus(self, step):

    #     if not self.selected_column:
    #         self.selected_column = -1
    #     index = (self.selected_column + 2*step)
    #     if index < 0:
    #         index = len(self.row.contents)-1
    #     if index > len(self.row.contents)-1:
    #         index = 0

    #     self.focus_position = index


    def highlight_column(self, index):
        self.selected_column = index
        for i in range(0, len(self.row.contents), 2):
            if i == index:
                self.row[i].highlight()
            else:
                self.row[i].unhighlight()

    def cycle_columns(self, step):

        if self.selected_column is None:
            index = 0
        else:
            index = (self.row.selected_column + 2*step)
            if index < 0:
                index = len(self.row.contents)-1
            if index > len(self.row.contents)-1:
                index = 0

        # print "index: %s" %(index)
        self.highlight_column(index)


class DataTableBodyRow(DataTableRow):


    column_class = BodyColumns

    attr_map = { None: "table_row" }
    focus_map = {
        None: "table_row focused",
        "table_row": "table_row focused",
        # "table_row column_focused": "table_row column_focused focused"
    }
    # focus_map = {}


class DataTableHeaderRow(DataTableRow):

    signals = ['column_click']

    column_class = HeaderColumns

    border_attr_map = { None: "table_border" }
    border_focus_map = { None: "table_border focused" }


    def __init__(self, table, *args, **kwargs):

        self.attr_map = {}
        self.focus_map = {}

        self.attr_map = { None: "table_header" }
        self.focus_map = { None: "table_header focused" }

        self.decorate = False

        self.table = table
        self.contents = [ DataTableHeaderLabel(x.label) for x in self.table.columns ]
        if not self.table.ui_sort:
            self.selectable = lambda: False

        super(DataTableHeaderRow, self).__init__(
            self.table,
            self.contents,
            border_attr_map = self.border_attr_map,
            border_focus_map = self.border_focus_map,
            cell_click = self.header_clicked,
            cell_select = self.header_clicked,
            *args, **kwargs)

    def header_clicked(self, index):
        # print "click: %d" %(index)
        # index = [x[0] for x in self.contents].index(self.focus) / 2
        urwid.emit_signal(self, "column_click", index)


class DataTableFooterRow(DataTableRow):

    # column_class = HeaderColumns

    border_attr_map = { None: "table_border" }
    border_focus_map = { None: "table_border focused" }

    def __init__(self, table, *args, **kwargs):

        self.attr_map = {}
        self.focus_map = {}

        self.attr_map = { None: "table_footer" }
        self.focus_map = { None: "table_footer focused" }

        self.table = table
        self.contents = [ DataTableHeaderLabel("")
                          for i in range(len(self.table.columns)) ]


        super(DataTableFooterRow, self).__init__(
            self.table,
            self.contents,
            border_attr_map = self.border_attr_map,
            border_focus_map = self.border_focus_map,
            *args, **kwargs)

    def selectable(self):
        return False

    def update(self):

        columns = self.table.columns

        for i, col in enumerate(columns):
            if not col.footer_fn:
                continue
            try:
                # col_data = [ r.data.get(col.name, None)
                #              for r in self.table.body ]
                data = [ r.data for r in self.table.body ]
                footer_content = col.footer_fn(data, col.name)
                if not isinstance(footer_content, urwid.Widget):
                    footer_content = col._format(footer_content)
                self[i] = footer_content
            except Exception, e:
                logger.exception(e)


class DataTable(urwid.WidgetWrap):

    signals = ["select", "refresh",
               "focus", "unfocus", "row_focus", "row_unfocus",
               "drag_start", "drag_continue", "drag_stop"]

    columns = []
    attr_map = {}
    focus_map = {}
    # attr_map = { None: "table" }
    # focus_map = { None: "table focused" }
    border = (DEFAULT_BORDER_WIDTH, DEFAULT_BORDER_CHAR, DEFAULT_BORDER_ATTR)
    padding = DEFAULT_CELL_PADDING
    with_header = True
    with_footer = False
    sort_field = None
    initial_sort = None
    sort_reverse = False
    query_sort = False
    ui_sort = False
    limit = None

    def __init__(self, border=None, padding=None,
                 with_header=True, with_footer=False,
                 initial_sort = None, query_sort = None, ui_sort = False,
                 limit = None):

        if border: self.border = border
        if padding: self.padding = padding
        if with_header: self.with_header = with_header
        if with_footer: self.with_footer = with_footer
        if initial_sort:
            if isinstance(initial_sort, tuple):
                self.sort_field, self.sort_reverse = initial_sort
            else:
                self.sort_field = initial_sort

        self.sort_field = self.column_label_to_field(self.sort_field)
        # print "init sort: %s, %s" %(self.sort_field, self.sort_reverse)

        if query_sort: self.query_sort = query_sort
        if ui_sort: self.ui_sort = ui_sort
        if limit: self.limit = limit

        self.walker = urwid.SimpleFocusListWalker([])
        self.listbox = ScrollingListBoxWithScrollbar(self.walker, infinite=self.limit)

        self.selected_column = None

        urwid.connect_signal(
            self.listbox, "select",
            lambda source, selection: urwid.signals.emit_signal(
                self, "select", self, selection)
        )
        urwid.connect_signal(
            self.listbox, "drag_start",
            lambda source, drag_from: urwid.signals.emit_signal(
                self, "drag_start", self, drag_from)
        )
        urwid.connect_signal(
            self.listbox, "drag_continue",
            lambda source, drag_from, drag_to: urwid.signals.emit_signal(
                self, "drag_continue", self, drag_from, drag_to)
        )
        urwid.connect_signal(
            self.listbox, "drag_stop",
            lambda source, drag_from ,drag_to: urwid.signals.emit_signal(
                self, "drag_stop", self, drag_from, drag_to)
        )


        if self.limit:
            urwid.connect_signal(self.listbox, "load_more", self.load_more)
            self.offset = 0


        self.pile = urwid.Pile([])

        self.header = DataTableHeaderRow(self)
        if self.with_header:
            self.pile.contents.append(
                (self.header, self.pile.options('pack'))
             )
            if self.ui_sort:
                urwid.connect_signal(
                    self.header, "column_click", self.sort_by_column
                )

        self.pile.contents.append(
            (self.listbox, self.pile.options('weight', 1))
         )

        # self.pile = urwid.Pile([
        #     ('pack', self.header),
        #     ('weight', 1, self.listbox)
        # ])

        if self.with_footer:
            self.footer = DataTableFooterRow(self)
            self.pile.contents.append(
                (self.footer, self.pile.options('pack'))
             )


        self.attr = urwid.AttrMap(
            self.pile,
            attr_map = self.attr_map
        )
        super(DataTable, self).__init__(self.attr)
        self.refresh()
        if not self.query_sort and self.sort_field:
            self.sort_by_column(self.sort_field)


    # @property
    # def selected_column(self):
    #     return self.header.focus_position

    @property
    def focus_position(self):
        return self.listbox.focus_position

    @focus_position.setter
    def focus_position(self, value):
        self.listbox.focus_position = value

    @property
    def body(self):
        return self.listbox.body

    @property
    def selection(self):
        return self.body[self.focus_position]

    def highlight_column(self, index):
        self.header.highlight_column(index)
        for row in self.listbox.body:
            row.highlight_column(index)

    def column_label_to_field(self, label):
        for i, col in enumerate(self.columns):
            if col.label == label:
                return col.name


    def sort_by_column(self, index):

        if isinstance(index, basestring):
            sort_field = index
            for i, col in enumerate(self.columns):
                if col.name == sort_field:
                    index = i*2
                    break
        else:
            sort_field = self.columns[index//2].name

        if not isinstance(index, int):
            raise Exception("invalid column index: %s" %(index))

        # logger.warning("sort: %s, %s" %(self.sort_field, self.sort_reverse))
        # raise Exception("%s, %s" %(index//2, self.selected_column))
        # print "%s, %s" %(index//2, self.selected_column)
        if sort_field != self.sort_field:
            self.sort_reverse = False
        else:
            self.sort_reverse = not self.sort_reverse
        self.sort_field = sort_field
        # print self.sort_reverse
        self.selected_column = index
        if self.query_sort:
            self.refresh()
        else:
            self.sort_by(index//2, reverse=self.sort_reverse)

        self.highlight_column(index)
        if len(self.listbox.body):
            self.listbox.focus_position = 0

    # def cycle_columns(self, step):

    #     index = (self.header.focus_position + 2*step)
    #     if index < 0:
    #         index = len(self.row.contents)-1
    #     if index > len(self.row.contents)-1:
    #         index = 0
    #     self.highlight_column(index)
    #     raise Exception(self.selected_column)


    def sort_by(self, index, **kwargs):

        sort_key = self.columns[index].sort_key

        if sort_key:
            kwargs['key'] = lambda x: sort_key(x[index].value)
        else:
            kwargs['key'] = lambda x: x[index].value

        if self.columns[index].sort_fn:
            kwargs['cmp'] = self.columns[index].sort_fn
        # print kwargs
        self.listbox.body.sort(**kwargs)

    def selectable(self):
        return True

    def keypress(self, size, key):

        if self.ui_sort and key in [ "<", ">" ]:

            self.header.cycle_columns( -1 if key == "<" else 1 )
            self.sort_by_column(self.header.row.selected_column)
        else:
            return super(DataTable, self).keypress(size, key)
            # return key

    def add_row(self, data, position=None):
        row = DataTableBodyRow(self, data, header = self.header.row)
        if position is None:
            self.listbox.body.append(row)
            position = len(self.listbox.body)-1
        else:
            self.listbox.body.insert(position, row)

        item = self.listbox.body[position]
        return item


    def query(self, sort=None, offset=None):
        pass

    def refresh(self, offset=0, **kwargs):
        orig_offset = offset
        if not offset:
            self.clear()

        kwargs = {"sort": (self.sort_field, self.sort_reverse)}
        if self.limit:
            kwargs["offset"] = offset
        # logger.error("sort: %s, %s" %(self.sort_field, self.sort_reverse))
        # print kwargs
        for r in self.query(**kwargs):
            # row = DataTableBodyRow(self, r, header = self.header.row)
            if isinstance(r, (tuple, list)):
                r = dict(zip( [c.name for c in self.columns], r))
            self.add_row(r)
            # self.listbox.body.append(row)

        if offset and orig_offset < len(self.body):
            self.listbox.set_focus(orig_offset)

        if self.with_footer:
            self.footer.update()

        urwid.emit_signal(self, "refresh", self)

    def load_more(self, offset):

        self.refresh(offset)
        # print self.selected_column
        if self.selected_column is not None:
            self.highlight_column(self.selected_column)


    def clear(self):
        # del self.data[:]
        del self.listbox.body[:]



def main():

    import os
    from optparse import OptionParser

    from urwid_utils.palette import PaletteEntry, Palette

    loop = None

    screen = urwid.raw_display.Screen()
    screen.set_terminal_properties(256)

    foreground_map = {
        "table_row": [ "light gray", "light gray" ],
        "red": [ "light red", "#a00" ],
        "green": [ "light green", "#0a0" ],
        "blue": [ "light blue", "#00a" ],
        "yellow": [ "yellow", "#aa0" ],
    }

    background_map = {
        None: [ "black", "black" ],
        "focused": [ "dark gray", "g7" ],
        "column_focused": [ "dark gray", "g7" ],
        "column_focused focused": [ "dark gray", "g11" ],
    }

    entries = dict()
    FOCUS_MAP = dict()

    for prefix in ["table_row", "red", "yellow", "green", "blue"]:
        for suffix in [None, "focused", "column_focused", "column_focused focused"]:
            if suffix:
                attr = ' '.join([prefix, suffix])
            else:
                attr = prefix
            entries[attr] = PaletteEntry(
                mono = "white",
                foreground = foreground_map[prefix][0],
                background = background_map[suffix][0],
                foreground_high = foreground_map[prefix][1],
                background_high = background_map[suffix][1],
            )

        FOCUS_MAP[prefix] = "%s focused" %(prefix)
        # FOCUS_MAP["%s column_focused" %(prefix)] = "%s column_focused focused" %(prefix)


    # raise Exception(FOCUS_MAP)
    header_foreground_map = {
        None: ["black,bold", "g7,bold"],
        "focused": ["white,bold", "white,bold"],
        "column_focused": ["yellow,bold", "yellow,bold"],
        "column_focused focused": ["yellow,bold", "yellow,bold"],

    }

    header_background_map = {
        None: ["light gray", "g40"],
        "focused": ["light gray", "g40"],
        "column_focused": ["white", "g40"],
        "column_focused focused": ["light gray", "g40"],
    }

    for prefix in ["table_header", "table_footer"]:
        for suffix in [None, "focused", "column_focused", "column_focused focused"]:
            if suffix:
                attr = ' '.join([prefix, suffix])
            else:
                attr = prefix
            entries[attr] = PaletteEntry(
                mono = "white",
                foreground = header_foreground_map[suffix][0],
                background = header_background_map[suffix][0],
                foreground_high = header_foreground_map[suffix][1],
                background_high = header_background_map[suffix][1],
            )

    palette = Palette("default", **entries)



    def avg(data, attr):
        values = [ d[attr] for d in data ]
        return sum(values)/len(values)

    class ExampleDataTable(DataTable):

        focus_map = FOCUS_MAP
        query_sort = True
        with_footer = True
        ui_sort = True

        columns = [
            DataTableColumn(
                "foo", width=5,
            ),
            DataTableColumn("bar", width=12, align="right", footer_fn = avg),
            DataTableColumn("baz", width=('weight', 1), attr="baz_attr"),
        ]

        def __init__(self, *args, **kwargs):
            super(ExampleDataTable, self).__init__(*args, **kwargs)

        def selectable(self):
            return True

        def query(self, sort=(None, None), offset=None):

            sort_field, sort_reverse = sort

            # print "%s, %s" %(sort_field, sort_reverse)
            l = [ dict(foo=random.randint(1, 10),
                       bar =random.uniform(0, 100),
                       baz =''.join(random.choice(
                           string.ascii_uppercase
                           + string.lowercase
                           + string.digits + ' ' * 20
                       ) for _ in range(32))) for i in range(1000)]

            if sort_field:
                kwargs = {}
                kwargs["reverse"] = sort_reverse
                kwargs["key"] = itemgetter(sort_field)
                l.sort(**kwargs)
            # print l[0]
            if offset is not None:
                start = offset
                end = offset + self.limit
                r = l[start:end]
            else:
                r = l

            for d in r:
                yield d


    # class MainView(urwid.WidgetWrap):

    #     def __init__(self):
    #         self.walker = urwid.SimpleFocusListWalker([])
    #         self.listbox = ScrollingListBoxWithScrollbar(self.walker)
    #         self.filler = urwid.Filler(self.listbox)
    #         for i in range(0, 10):

    #             self.listbox.body.append(DataTableRow("a"))

    #         self.pile = urwid.Pile([
    #             ('weight', 1, self.listbox)

    #         ])
    #         super(MainView,self).__init__(self.pile)

    class MainView(urwid.WidgetWrap):

        def __init__(self):

            self.tables = list()

            self.tables.append(
                ExampleDataTable(initial_sort="foo", limit=10)
            )

            self.tables.append(
                ExampleDataTable(initial_sort="bar", limit=20)
            )

            self.tables.append(
                ExampleDataTable(initial_sort="baz", ui_sort=False)
            )

            for t in self.tables:
                urwid.connect_signal(
                    t, "refresh", lambda source: loop.draw_screen()
                )

            self.grid_flow = urwid.GridFlow(
                [urwid.BoxAdapter(t, 40) for t in self.tables], 55, 1, 1, "left"
            )
            #     [ ('weight', 1, urwid.LineBox(t)) for t in self.tables ]
            # )


            self.pile = urwid.Pile([
                ('weight', 1, urwid.Filler(self.grid_flow))

            ])
            # w = urwid.WidgetPlaceholder(self.pile)
            super(MainView,self).__init__(self.pile)


    def parse_list(option, opt, value, parser):
        setattr(parser.values, option.dest, value.split(','))

    parser = OptionParser()
    parser.add_option("-H", "--hide-teams", type="string",
                      action="callback", callback=parse_list,
                      default=[],
                      help="hide stats/results for players on these teams"),

    (options, args) = parser.parse_args()

    main_view = MainView()

    def global_input(key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        else:
            return False


    loop = urwid.MainLoop(main_view,
                          palette,
                          screen=screen,
                          pop_ups=True,
                          unhandled_input=global_input,
                          event_loop=urwid.TwistedEventLoop())
    loop.run()

if __name__ == "__main__":
    main()

