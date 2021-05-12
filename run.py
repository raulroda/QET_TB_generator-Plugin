#!/usr/bin/env python3
# encoding: utf-8

#---------|---------|---------|---------|---------|---------|---------|---------|
# Copyright (C) 2018 Raul Roda <raulroda@yahoo.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#---------|---------|---------|---------|---------|---------|---------|---------|


#
# Este proyecto permite dibujar borneros partiende de un esquema del software QElectrotech.
# Los borneros dibujados se añaden a la sección xml del fichero .qet: 
#  <collection>
#    <category name="import">
#
#
# Se buscan todos los bornes en el esquema. Los bornes son elementos del tipo TERMINAL. 
# Además deben tener un 'label' de tipo X1:3. 
#
#
# Hay configuración que afecta a cada borne y otra que afecta a todo el bornero.
# Toda la configuración se guarda en el campo 'function' de cada elemento de QET.
# Ese campo es accesible desde <elementInformation name="function"> de cada borne. 
# La configuración se guarda como una cadena de texto, con unos TAGS que sirven
# para identificar cada uno de los parámetros.
#   Ejemplo:
#       <elementInformation name="function">
#           %p2%tSTANDARD%c%n%b
#       </elementInformation>    
# Todos los bornes de un mismo bornero, tiene la misma configuración arriba
# mencionada, de forma que si se borra un borne  quedará algun otro borne de ese
# bornero del que extraer la configuración
#
#
#
# La info leida para cada borne se almacen en la variable global 'data'.
# Esta variable tiene un key para cada bornero y luego una lista con la config
# de cada terminal. La variable 'data' tambien tendra una variable de tipo
# 'tk' que nos permitirá enlazar con el valor de los widgets del GUI
#   {
#       borne_id1: [ {term1}, {term2}, ... ]
#       borne_id2: [ {term1}, {term2}, ... ]
#       borne_id3: [ {term1}, {term2}, ... ]
#   }
# Para cada terminal hay configuración propia y configuración del bornero entero.
# En la siguiente lista se muestran las variables que enlazan con los TK widgets
# y  el TAG con el que se guarda cada valor en el XML del esquema. 
#   {
#     'uuid': From QET. identificador of the terminal in the QET xml file,
#     'block_name': From QET.terminal block that belong the terminal,
#     'terminal_name': From QET.
#     'terminal_xref': Calculated from QET,
#     'cable': From QET,
#
#     'terminal_pos %p': From Plugin. For sortering purposes,
#     'terminal_type %t': From Plugin. STANDARD, GROUND, FUSE. For representing purposes,
#     'hose %h': From Plugin. Name of the cable of the electric hose,
#     'conductor %n': From Plugin. Name of the electric hose,
#     'bridge %b: From Plugin. True/False for a bridge to next terminal
#     'num_reserve %r': Config for entire terminal block. Num of reserve terminals
#     'reserve_positions %z': Config for entire terminal block. Position for the
#           reserve terminals. Not used for now
#     'size %s': number of terminals per page
#   }
#
#
# Los borneros creados en el XML del esquema QET se nombran según TB_x##y.elmt
# donde:
#   x: es el nombre del bornero (X1, X34, -XL3,...)
#   y: es un número direfente para el mismo bornero que se he troceado para que
#      quepa en una página.



# PARA CREAR NUEVA COLUMNA EN LA TABLA
# - QETProject: documentar la clase
# - documentar en comentar init_ui
# - añadir nueva columna en GRID_CONFIG
# - definir la funcion callback si la columna permite clicks
# - Insertar tag para almacenar info en el elemento de QET: getElementMetadata
# - Modificar : get_list_of_used_terminals
# - Modificar: save_tb
# - Modificar last_trmnl en drawTerminalBlock. Añadir funciones de dibujo 
#   si la columa lo requiere
# - Modificar click_on_reorder si la columna afecta a la ordenacion



## Imports
import logging as log
import os
import re
import shutil
import sys
import json
from functools import cmp_to_key
#~ import lxml.etree as etree  # python3-lxml
from operator import itemgetter as i

import PySimpleGUI as sg

from src.qetproject import QETProject
from src.terminalblock import TerminalBlock

## Globals (allows access from callbacks events)
frmFoot = None  # the bottom widget of GUI to show info
qet_project = None  # class to manage QET_Projects
qet_terminals = []  # list of terminals and its config
wdg_data = {}
selection = []  # stores checkboxes selected to dray terminal blocks
edited_terminals = []  # to propose the terminal-blocks to create

# CONSTANTS
ALL = '-- ALL --'
THEME = 'SystemDefaultForReal'  # pysimplegui
VERSION = '1.2.0f'
FECHA = 'April, 2020'
TITLE = 'QET Terminal Block Generator - v{}'.format(VERSION)
STRIP_LONG = 30
SEP = '%'  # separator of info in the metadata field
CONFIG_FILE = 'qet_tb_generator.json'
CONFIG_UI_INPUT_FIELDS_KEYS = [ '-CFG_SPLIT-', '-CFG_A-', '-CFG_B-', '-CFG_C-', \
    '-CFG_D-', '-CFG_E-', '-CFG_F-', '-CFG_G-', '-CFG_H-', '-CFG_I-', '-CFG_J-', \
    '-CFG_HEAD_FONT-', '-CFG_TERMINAL_FONT-', '-CFG_XREF_FONT-', '-CFG_CONDUCTOR_FONT-']


# UI CONSTANTS. 
# - key is the dict id of the terminals list getted from QETproject
# - the extra info with no column asigned are stored as metadata in
#   the first CELL of every row: uuid, num_reserve, reserve_positions, size
# - tip: shows when mouse over header
# - Edit: True to create a Input instead of a Text
# - Disabled: True to disable events
TABLE = [
    {'col':0, 'text':'ORDER', 'size':8, 'edit': False, 'disabled': False, 'key': '', 'tip': 'Click to move up/down the terminal'},  # UP/DW buttons
    {'col':1 , 'text':'POS.', 'size':6, 'edit': False, 'disabled': True, 'key': 'terminal_pos', 'tip': 'Position of the terminal in the terminal-block'},
    {'col':2 , 'text':'BLOCK', 'size':10, 'edit': False, 'disabled': True, 'key': 'block_name', 'tip': "Terminal-block's name (comes from the schema)"},
    {'col':3 , 'text':'ID', 'size':8, 'edit': False, 'disabled': True, 'key': 'terminal_name', 'tip': "Terminal's label (comes from the schema)"},
    {'col':4 , 'text':'XREF', 'size':9, 'edit': False, 'disabled': True, 'key': 'terminal_xref', 'tip': "Terminal's place (comes from the schema)"},
    {'col':5 , 'text':'CABLE', 'size':10, 'edit': False, 'disabled': True, 'key': 'cable', 'tip': "Cable's name connected to the terminal (comes from the schema)"},
    {'col':6 , 'text':'BRIGE?', 'size':8, 'edit': False, 'disabled': False, 'key': 'bridge', 'tip': 'If selected, a bridge will be drawn between the terminal and the next one'},
    {'col':7 , 'text':'TYPE', 'size':11, 'edit': False, 'disabled': False, 'key': 'terminal_type', 'tip': 'Defines the graphical representation of the terminal'},
    {'col':8 , 'text':'HOSE', 'size':18, 'edit': True, 'disabled': False, 'key': 'hose', 'tip': "Hose's name the conductor belongs to. Several terminals can share hose (i.e. -W1, -WXL12,...)"},
    {'col':9 , 'text':'CONDUCTOR', 'size':14, 'edit': True, 'disabled': False, 'key': 'conductor', 'tip': "Conductor's name of the hose (i.e. 1, br, yellow, ...)"}
]

txt : {
0:
"""
To change terminals order:
  - Left click on a number in POS. column to decrement
  - Right click on a number in POS. column to increment.
To edit BRIDGE and TYPE, just right click on the cell.
""", \
1: 
"""
Steps to follow.
  - In QET, optional: Choose Project> Clean Project.
  - In QET:  Close and reopen the project.
  - In QET: Start the plugin. Choose 'Start the terminal block creation plug-in' in the project menu.
  - In this plug-in: Edit the terminal blocks (described below).
  - In this plug-in: Press the 'CREATE TERMINAL BLOCKS' button.
  - In this plug-in: In the pop-up screen, choose the terminal blocks you want to create / update.
  - In this plug-in: Close 
  - In QET:  Close without saving project (very important) and reopen the project.
  - In QET: Under the 'COLLECTIONS' tree of the project, all the terminal blocks appear.

Considerations for creating a terminal block from a diagram.
  - This addon searches all the elements of type 'Terminal'.
  - Normally, the terminal elements appear in the filter of the QET collection by 'terminal block'.
  - Terminals must have a tag such as <terminal_block_name>: <terminal_name>. For example: -X1: 1, X34: +, X1: 23, Y3: R, ...
  - All terminals with the same <terminal_block_name> are grouped and displayed in a tab in this add-on.
  - In the add-on, for each terminal block, you can specify how many terminals fits per page and the number of reserve terminals.
  - The terminals are sorted by default, however the order can be modified.
  - You can also specify the hose and the conductor connected at the bottom of every terminal (columns 'HOSE' and 'CONDUCTOR').
  - There are 3 types of terminals that you can specify in the 'TYPE' column (standard, ground, fuse)
  - The 'BRIDGE' column indicates if there is a bridge from the current to the next terminal.

How to use:
  - To change the order of the terminals in the terminal block, just left-click or right-click
    on the corresponding number of 'POS.' column.
  - By right-clicking on the cells of the TYPE and HOSE columns, it will alternate betwenn all possible values.
  - For each block of terms:
    - You can specify how many terminals per page you will draw.
    - the number of reserve terminals that are drawn at the end.

          
Created by raulroda8@gmail.com ({})
""".format(FECHA)

}


ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABHNCSVQICAgIfAhkiAAAA4xJREFUeJztWj9L+0AYfu5MrDaKKX4DF8FJUEQ6OLk7OAvFL9HJ0d3N3a8hurgIHYprBxUklopgi6FG2uZ+U/NrmuTSXP5cbPNAh96b982Th/fPXRvCGGNYYFDZBGSjEEA2AdkoBJBNQDYKAWQTkI1CANkEZGPhBVCSCHJxcYHHx0fPumVZ+Pn5QaVSgW3b6PV6obG+vr5gWRZWVlY8tuFwiF6vB0VRYNu2y2bbNlZXV9FutyNxjy1Ap9NBo9FAvV732O7u7hwbpRQbGxuO7erqCtVqFQcHBy6f5eVlVKtVPDw8eOI1m01cXl7i9vYWlLqTt9VqoVarReYfW4But4vX11ccHx97bJ1OB29vb7620WgEXdext7fnWjdNEwCwtbXl8fn4+ECpVMLm5qbHpus6RM51sXsAISTwxiI2SqknvcdgjIEQ4mvj+fEgTYBAQoIPInIvoMgAeWNQRAAeFqIEcpkBSZcAz4cngGgP4I5B27ZxeHgI0zShaRp0XYemaTAMA41GIzS4qAAA/2H9IJoBXAGGwyGenp7QbDbR7/fR7Xbx/f2N09NTF+EkSwD4/zBLS0uu9TRKgCvAOOjOzo6LxCREH5LnFyTALFyjgtsD/IJOE0+6BwTdF0inB0QWIAqSFoCH1KaAH9HJtTR7wDSkjMGwMvjrJRB6GgxqSOfn53h+fkar1XJOcFGQlzPEzAJMghCCo6Mj1Go1lMtl11icvi7vJSAkAKUUZ2dnUFUVhmFkVgJRec7kJxJ4nnpAbAF4SLoEkvYBUh6DUeM6pPI+BieRZQnE4RnoJxK46AGSekBuSiDtDBARbuwTeQMVekGIAKZpJv4rrkgGjP2iCiC0ERqNRtjf34dhGM53P2Q5Bif9pv814vqEXUAI8ZBRFAU3Nzd4f3/Hy8sLNE0L9M2qCfL8eJipBKaJUkqxvb2N9fX13IzBsJhBkNYEo94TkJgBcX4VCsKfKoG8bIREuIb6iATN404wLGYQcrkTzHJ8hu4DPj8/sbu7C8uynDVVVZ1Zm6cMSEWAdruNwWCAcrnsa8/yOByGVARQVRWqqgba8zQGU+kBcTAXUyAMf70H5O4FCWCOSoCHhS8B3tk9yxIAi4nf31+mKAoDIO2ztrbGKpUKo5Sy6+vrSPwJEynSnME0TQwGA9zf3+Pk5ASKMvsLsHMhQBws/OvyhQCyCchGIYBsArJRCCCbgGz8A8M+BcbRRKw4AAAAAElFTkSuQmCC'

LEGEND_PICTURE = "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"


# class ScrollableFrame(ttk.Frame):
#     def __init__(self, container, *args, **kwargs):
#         super().__init__(container, *args, **kwargs)
#         canvas = tk.Canvas(self)
#         scrollbar = ttk.Scrollbar(
#             self, orient="vertical", command=canvas.yview)
#         self.scrollable_frame = ttk.Frame(canvas)

#         self.scrollable_frame.bind(
#             "<Configure>",
#             lambda e: canvas.configure(
#                 scrollregion=canvas.bbox("all")
#             )
#         )

#         canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

#         canvas.configure(yscrollcommand=scrollbar.set)

#         canvas.pack(side="left", fill="both", expand=True)
#         scrollbar.pack(side="right", fill="y")
        



def kkconvert_numerical(data):
    """Convert string values to integers. This allows 'more intelligent'
    sorting. Discards + and - signs, because are used naming terminals
    """
    regex_digits = r'^(\d+)$'
    for ter in data:
        if re.search(regex_digits, ter['terminal_name']):
            ter['terminal_name'] = int(ter['terminal_name'])
        if re.search(regex_digits, ter['terminal_pos']):
            ter['terminal_pos'] = int(ter['terminal_pos'])
        if re.search(regex_digits, ter['hose']):
            ter['hose'] = int(ter['hose'])
        if re.search(regex_digits, ter['conductor']):
            ter['conductor'] = int(ter['conductor'])
    return data


def cmp(a, b):
    """Returns 0, 1(a>b) or  -1(a<b)
    """
    
    if type(a) == type(b):
        return (a > b) - (a < b)
    elif (type(a) is int) and (type(b) is str):
        return -1
    elif (type(b) is int) and (type(a) is str):
        return 1


def multikeysort(items, columns):
    """ Sort list of dict using diferent keys. From
    https://stackoverflow.com/questions/1143671/
    python-sorting-list-of-dictionaries-by-multiple-keys
    @param items: dict to sort
    @param colums: list with keys names of dict
    """
    comparers = [
        ((i(col[1:].strip()), -1) if col.startswith('-') else (i(col.strip()), 1))
        for col in columns
    ]
    def comparer(left, right):
        comparer_iter = (
            cmp(fn(left), fn(right)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))


#################################################################


def get_QET_fullpath(default=""):
    """
    Returns the QET project file from command line or from file dialog
    """

    if len(sys.argv) == 1:  # first data is the prg name
        f = sg.popup_get_file("Choose a diagram QET file", \
                title = TITLE, \
                default_path = default, \
                file_types = (("QET Files", '*.*'),),
            )
    else:
        f =  sys.argv[1]
    log.info('Using the file: {}'.format(f))

    if not f:
        return None
    
    if os.path.isfile(f):
        return f
    else:
        log.info('File {} does not exit'.format(f))
        return None




def initialize_logger():
    logger = log.getLogger()
    logger.setLevel(log.DEBUG)
     
    # console
    handler = log.StreamHandler()
    handler.setLevel(log.DEBUG)
    formatter = log.Formatter( \
            '%(asctime)s %(levelname)-8s %(message)s [%(module)s.%(funcName)s:%(lineno)i]', '%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
 
    # error file
    #handler = log.FileHandler(os.path.join(output_dir, "error.log"),"a", encoding=None, delay="true")
    #handler.setLevel(log.ERROR)
    #formatter = log.Formatter("%(asctime)s %(levelname)-8s %(message)s [%(module)s.%(funcName)s:%(lineno)i]")    
    #handler.setFormatter(formatter) 
    #logger.addHandler(handler)
 
    # log file
    #handler = log.FileHandler(os.path.join(output_dir, "all.log"),"a")
    #handler.setLevel(log.INFO)
    #formatter = log.Formatter("%(asctime)s %(module)-12s %(levelname)-8s %(message)s")
    #handler.setFormatter(formatter)
    #logger.addHandler(handler)



def choose_tb_to_create(tb_names, edited_terminals):
    """
    Shows a windows with a list of terminal-blocks preselecting
    the edited.
    If the user chooses -- ALL --, return the full list of names
    """
    msg = ("Select the terminal-blocks that \n"
           "you want to insert as elements\n"
           "in your schema. The edited\n"
           "terminal-blocks are preselected.")

    layout = [
        [sg.Text(msg)],
        [
            sg.Listbox(values=[ALL] + tb_names, \
                    default_values=edited_terminals, \
                    size=(30,20), \
                    enable_events=False, \
                    select_mode='multiple', \
                    key='-TB-')
        ],
        [sg.OK(), sg.Cancel()]
    ]

    window = sg.Window(TITLE, layout, modal=True)
    event, values = window.read()
    window.close()

    if event == 'OK':
        if ALL in values['-TB-']:
            return tb_names
        else:
            return values['-TB-']
    else:
        return []    



def backup_diagram():
    """ Backup the diagram WET file to a new filename adding a increment
    suffix"""

    # find new backup filename
    i = 1
    full_back_path = qet_file[:qet_file.rfind('.')] + '_' + str(i) + '.qet' 
    while os.path.isfile( full_back_path) or \
            os.path.isdir( full_back_path ) :
        i += 1
        full_back_path = qet_file[:qet_file.rfind('.')] + '_' + str(i) + '.qet' 
    
    # backup    
    shutil.copyfile(qet_file, full_back_path)
    return full_back_path




def add_to_edited_tb(memo_list, tb_name):
    """
    Memorize the edited terminal blocks to preselect them in the list 
    of terminal-blocks to create in the schema.
    """
    if not tb_name in memo_list:
        memo_list.append(tb_name)



def create_a_TB(tb_name, tb, slice_num, tb_splitted, settings, qet_project):
    """
    Creates a TB getted from the choosed TB to create by the user

    param tb_name: name of the TB
    param tb: list of terminals
    param tb_slice: num of the slice. Starts from 1.
    param tb_splitted: True if the TB have several parts
    param settings: a dict with the settings defined in the UI
    param qet_project: the object representing the XML tree
    """

    # The TB Head
    if tb_splitted:
        head_text = "{}({})".format( tb_name, slice_num )
    else:
        head_text = "{}".format( tb_name )

    print ( "Generating TB {}\n\n".format( tb_name ) )
    
    # Generating the XML element and inserting into the QET Project XML tree.
    a_block = TerminalBlock( head_text, tb, settings)
    qet_project.insert_tb(head_text, a_block.drawTerminalBlock())



def create_terminal_blocks(tb_list, max_tb_length, settings, qet_project):
    """
    Extract the data from the gui, generates the element component
    (the terminal block draw) and saves them to the original file project.

    Longs TB are splited into multiple elements.

    @param tb_list: list of terminal names to generate the QET element. 
        Exits if empty.
    @param (int)max_tb_length: to split terminal-blocks if has a lot of terminals
    @param settings: a dict with the settings
    @param qet_project: object
    """

    if not tb_list:
        return

    ## Loop selected blocks. Extract data from gui for a every terminal block
    full_back_path = backup_diagram()
    
    # Convert data from UI to dicts
    tb_from_ui = []  # list of dicts. Every dict is a terminal  
    for row in range(len(qet_project.terminals)):
        term = {}
        term['uuid'] = window[ '-1/{}-'.format(row) ].metadata
        term['block_name'] = window[ '-2/{}-'.format(row) ].get()
        term['terminal_name'] = window[ '-3/{}-'.format(row) ].get()
        term['terminal_xref'] = window[ '-4/{}-'.format(row) ].get()
        term['cable'] = window[ '-5/{}-'.format(row) ].get()
        term['terminal_pos'] = window[ '-1/{}-'.format(row) ].get()
        term['terminal_type'] = window[ '-7/{}-'.format(row) ].get()
        term['hose'] = window[ '-8/{}-'.format(row) ].get()
        term['conductor'] = window[ '-9/{}-'.format(row) ].get()
        term['bridge'] = window[ '-6/{}-'.format(row) ].get()
        #term['num_reserve'] = full_tb[-1]['num_reserve']
        #term['reserve_positions'] = full_tb[-1]['reserve_positions']
        tb_from_ui.append(term)

    # Filter the selected TB
    filtered_tb = [ t for t in tb_from_ui if t['block_name'] in tb_list]

    # Extract terminals until the list is empty
    memo_tb_name = filtered_tb[0]['block_name']
    current_tb = []
    tb_done = []  # if a TB already exists, is because of have several slices.
    for t in filtered_tb:
        if t['block_name'] == memo_tb_name and len(current_tb) < int(max_tb_length):
            current_tb.append(t)
            print( "TB {}: append terminal {}".format(t['block_name'], t['terminal_name']) )
        else:  # TB completed
            current_tb_name = current_tb[0]['block_name']
            tb_done.append( current_tb_name )  
            create_a_TB(tb_name=current_tb[0]['block_name'], \
                    tb=current_tb, \
                    slice_num=tb_done.count( current_tb_name), \
                    tb_splitted=len([1 for x in filtered_tb if x['block_name'] == current_tb_name]) >  max_tb_length, \
                    settings=settings, \
                    qet_project=qet_project )

            # starting the next TB
            current_tb = [t]
            memo_tb_name = current_tb[0]['block_name']
            print( "TB {}: append terminal {}".format(t['block_name'], t['terminal_name']) )

    # Create the last TB
    current_tb_name = current_tb[0]['block_name']
    tb_done.append( current_tb_name )
    create_a_TB(tb_name=current_tb[0]['block_name'], \
        tb=current_tb, \
        slice_num=tb_done.count( t['block_name'] ), \
        tb_splitted=len([1 for x in filtered_tb if x['block_name'] == current_tb_name]) >  max_tb_length, \
        settings=settings, \
        qet_project=qet_project )

    # The Plugin info is saved in the terminal itself.
    qet_project.update_terminals(filtered_tb)

    # save and messaging
    qet_project.save_tb(qet_file)
    msg = ("DONE.\n\n"
           "Reopen the schematic at QElectroTech.\n" \
           "The terminal blocks are under 'Imported elements' collection of your project.\n\n" \
           "Original diagram file saved as:\n{}".format(full_back_path) )      
    sg.popup(msg , title="QET", button_color=('black', 'light green'))


def move_terminal_up(row):
    """
    Moves a terminal up one position if is not the first yet.

    @param row: row of the table
    """

    row = int(row)
    if row == 0:
        return
    
    current_row_tb = window['-{}/{}-'.format(2,row)].get()
    previous_row_tb = window['-{}/{}-'.format(2,row-1)].get()
    if current_row_tb != previous_row_tb:
        return

    # exchange columns
    for c in range(3, len(TABLE)):  # col.0 buttons, col.1 position, col.2 block
        foo = window['-{}/{}-'.format(c,row)].get()
        window['-{}/{}-'.format(c,row)].update( window['-{}/{}-'.format(c,row-1)].get() )
        window['-{}/{}-'.format(c,row-1)].update (foo)

    # exchange UUID as metadata on the first field
    foo = window['-1/{}-'.format(row)].metadata
    window['-1/{}-'.format(row)].metadata =  window['-1/{}-'.format(row-1)].metadata 
    window['-1/{}-'.format(row-1)].metadata = foo 



def move_terminal_down(row, max_index_row):
    """
    Moves a terminal down one position in the terminal block
    if is not the last yet.

    @param row: row of the table
    @param num_rows: num rows of the table of terminals
    """

    row = int(row)
    if row >= (max_index_row - 1):  # row index starts 0
        return
    
    # not allow to mix terminals between terminal-blocks
    current_row_tb = window['-{}/{}-'.format(2,row)].get()
    next_row_tb = window['-{}/{}-'.format(2,row+1)].get()
    if current_row_tb != next_row_tb:
        return

    # exchange row columns
    for c in range(3, len(TABLE)):  # col.0 buttons, col.1 position, col.2 block
        foo = window['-{}/{}-'.format(c,row)].get()
        window['-{}/{}-'.format(c,row)].update( window['-{}/{}-'.format(c,row+1)].get() )
        window['-{}/{}-'.format(c,row+1)].update (foo)



def alter_bridge(cell_key):
    """
    Alter the Bridge cell between blank and |.
    If the value es |, a bridge line will be drawn between the terminal
    and the next one.

    @param cell_key: key of the clicked cell
    """
    loop = {'' : '|', \
            '|':''}
    window[cell_key].update( loop[window[cell_key].get()] )



def alter_type(cell_key):
    """
    Alter the Type cell contents between STANDARD, GROUND and FUSE.

    @param cell_key: key of the clicked cell
    """
    loop = {''        : 'STANDARD', \
            'STANDARD': 'GROUND', \
            'GROUND'  : 'FUSE', \
            'FUSE'    : 'STANDARD'}
    window[cell_key].update( loop[window[cell_key].get()] )



def filter_terminals(tb_names, max_index_row):
    """
    Shows only the selected terminal-block in the terminals list.
    To hide a row is enough to hide on element in the row layout.
    
    @param tb_names: list of tb names to filter.
    @param num_rows: num rows of the table of terminals
    """

    # Hide all first. If not the order or rows could change
    for row in range(max_index_row):
        id = '-2/{}-'.format(row)  # a random object in the row
        window[id].hide_row()
            

    for row in range(max_index_row):
        id = '-2/{}-'.format(row)
        if window[id].get() in tb_names or ALL in tb_names:
            window[id].unhide_row()



def header_cell(col):
    """
    Customized control for the table header

    @param col: starting by 0
    @return Input element
    """
    return sg.Input(default_text = TABLE[col]['text'], \
            disabled=True, \
            tooltip=TABLE[col]['tip'], \
            enable_events=False, \
            justification='center', \
            background_color= 'gray', \
            size=(TABLE[col]['size'],4), \
            border_width = 1, \
            pad=( (0,0), (0,5) ) 
            )



def table_sort_button(row, dir):
    """
    Customized control for the table sort UP buttonn

    @param row: starting by 0. 'HEAD' for the table HEADER
    @param dir: sort direction 'UP' or 'DW'
    @return Button element
    """
    return sg.Text( text=['▲', '▼'][dir=='DW'], \
            enable_events=[True, False][row=='HEAD'], \
            relief= 'raised', \
            justification='center',\
            text_color=['blue', 'black'][row=='HEAD'], \
            # tooltip= 'Press to move {}'.format(['up', 'down'][dir=='DW']), \
            key='-{}{}-'.format(dir, row), \
            size= ( int(TABLE[0]['size']/2-1), 1), \
            pad=(0,0)
    )



def table_cell(col, row, text = '', metadata='', bgcolor=0):
    """
    Customized control for the table cell. The first row
    are 2 buttons to change Terminals orden in the
    terminal-block.

    @param col: starting by 0
    @param row: roen index starting by 0. 'HEAD' for the table HEADER
    @param text: default cell content
    @param metadata: saves extra info about the terminal
    @param bgcolor: alternate cell background color (0 or 1). 2 for the HEADER color
    @return Input element
    """

    if TABLE[col]['edit'] and row !='HEAD':  # editable field
        return sg.Input(default_text = text, \
                key='-{}/{}-'.format(col,row), \
                disabled = TABLE[col]['disabled'], \
                enable_events=True, \
                background_color = ['white', 'wheat1', 'light gray'][bgcolor], \
                text_color= 'blue', \
                border_width=1, \
                size=(TABLE[col]['size'],1), \
                tooltip='-{}/{}-'.format(col,row), \
                pad=(0,0)
        )
    else:  # no editable field or table header
        disabled = TABLE[col]['disabled'] or row=='HEAD'
        return sg.Text( text=text, \
            enable_events=not disabled, \
            relief= 'raised', \
            justification='center',\
            metadata= metadata, \
            background_color = ['white', 'wheat1', 'light gray'][bgcolor], \
            text_color= ['blue', 'black'][ disabled] , \
            key='-{}/{}-'.format(col,row), \
            size= (TABLE[col]['size'],1), \
            tooltip='-{}/{}-'.format(col,row), \
            pad=(0,0)
        )



def load_settings():
    """
    Load setting from config file. If does not exist, set defaults values
    and creates the config file
    """

    # Get system config path
    config_file = os.path.join(
        os.environ.get('APPDATA') or
        os.environ.get('XDG_CONFIG_HOME') or
        os.path.join(os.environ['HOME'], '.config'),
        CONFIG_FILE
    )

    if os.path.isfile(config_file):
        # load files
        with open(config_file, 'r') as f:
            config = json.load(f)
            for k,v in config.items():
                window[k].update(v)
    else:
        set_default_settings()



def set_default_settings():
    """
    Fills the settings fields with default values,
    and saves to the config file too.
    """

    # General
    window['-CFG_SPLIT-'].update('30')

    # TB Graphical dimensions
    window['-CFG_A-'].update('120')
    window['-CFG_B-'].update('44')
    window['-CFG_C-'].update('70')
    window['-CFG_D-'].update('6')
    window['-CFG_E-'].update('160')
    window['-CFG_F-'].update('20')
    window['-CFG_G-'].update('50')
    window['-CFG_H-'].update('70')
    window['-CFG_I-'].update('80')
    window['-CFG_J-'].update('70')

    # Font size
    window['-CFG_HEAD_FONT-'].update('13')
    window['-CFG_TERMINAL_FONT-'].update('9')
    window['-CFG_XREF_FONT-'].update('6')
    window['-CFG_CONDUCTOR_FONT-'].update('6')

    # save to config file
    #save_settings()



def save_settings():
    """
    Save current setting to file

    @return: If parameters are correct, returns dict of parameters, else {}
    """

    # Get system config path
    config_file = os.path.join(
        os.environ.get('APPDATA') or
        os.environ.get('XDG_CONFIG_HOME') or
        os.path.join(os.environ['HOME'], '.config'),
        CONFIG_FILE
    )

    # Create config and check all are integers
    config = { k:window[k].get() for k in CONFIG_UI_INPUT_FIELDS_KEYS } 
    config_ok=True
    try:
        for v in config.values():
            foo = int(v)
    except:
        config_ok=False

    #save to file
    if config_ok:
        with open(config_file, 'w') as f:
            json.dump(config, f)
        return config
    else:
        sg.popup('Error saving settings.', 'Some values are not integers.')
        return {}


def get_layout(qet_project):
    """
    Return a list of list defining the layout of the main window.
    Creates a fake-table with a number of rows corresponding with
    the teminal-block with more elements.
    The unneeded rows are hidden.

    @param qet_project: instace of a QETProject. Used to get the list
        of terminal-blocks and the max. number or rows needed.
    @return List of list defining the layout.
    """

    # Calc layout parameters
    #rows = qet_project.get_max_tb_length()
    terminals = qet_project.terminals
    rows = len(terminals)
    tb_names = qet_project.tb_names


    # UI General settings area
    general_settings_area =[
        [ 
            sg.T("Show legend", justification='center', enable_events=True, relief= 'raised', key='-BTN_LEGEND-', size=(13,1)), \
            sg.T("Set default settings", justification='center', enable_events=True, relief= 'raised', key='-BTN_DEFAULT-', size=(22,1)), \
        ], \
        [ sg.T('Split terminal block every'), sg.In(key='-CFG_SPLIT-', size=(3,1)), sg.T('terminals.')]
    ]

    # UI Dimensions settings area
    dimensions_settings_area =[

        [ 
          sg.T("A", size=(1,1)), sg.In(key='-CFG_A-', size=(3,1)), \
          sg.T("B", size=(1,1)), sg.In(key='-CFG_B-', size=(3,1)), \
          sg.T("C", size=(1,1)), sg.In(key='-CFG_C-', size=(3,1)), \
          sg.T("D", size=(1,1)), sg.In(key='-CFG_D-', size=(3,1)), \
          sg.T("E", size=(1,1)), sg.In(key='-CFG_E-', size=(3,1)), \
        ], \

        [
          sg.T("F", size=(1,1)), sg.In(key='-CFG_F-', size=(3,1)), \
          sg.T("G", size=(1,1)), sg.In(key='-CFG_G-', size=(3,1)), \
          sg.T("H", size=(1,1)), sg.In(key='-CFG_H-', size=(3,1)), \
          sg.T("I", size=(1,1)), sg.In(key='-CFG_I-', size=(3,1)), \
          sg.T("J", size=(1,1)), sg.In(key='-CFG_J-', size=(3,1))
        ]

    ]


    # UI Font size settings area
    font_size_settings_area =[
        [
          sg.T("Head", size =(12,1)), sg.In(key='-CFG_HEAD_FONT-', size=(3,1)), \
          sg.T("Terminal ID",size =(12,1)), sg.In(key='-CFG_TERMINAL_FONT-', size=(3,1))
        ], \

        [ 
          sg.T("Conductors", size =(12,1)), sg.In(key='-CFG_CONDUCTOR_FONT-', size=(3,1)), \
          sg.T("Cross ref.", size =(12,1)), sg.In(key='-CFG_XREF_FONT-', size=(3,1))
        ]
    ]


    # UI List terminals
    tb_list =[
        [ sg.T("Filter Terminal blocks", text_color='black') ],

        [ sg.Listbox(values=[ALL] + tb_names, \
                default_values=[ALL], \
                size=(20,17), \
                enable_events=True, \
                key='-TB-')
        ],

        [ sg.Button("Create Term. Blocks...", key='-OK-') ],
        [ sg.Button("About...", key='-ABOUT-') ]
    ]


    # UI Fake table HEADER
    terminals_table = [  ]

    row =  [ table_sort_button('HEAD', 'UP') ]
    row += [ table_sort_button('HEAD', 'DW') ]
    cells = []
    for c in range(1,len(TABLE)):  # cols
        cells += [ table_cell(c, 'HEAD', text=TABLE[c]['text'], metadata=TABLE[c]['tip'], bgcolor = 2) ]
    row += cells
    terminals_table.append( row )


    # UI Fake table CONTENT
    back_color = 0; memo_block_name = ''  # for colorize cells of same terminal-block
    i = 0  # recorrer filas terminales
    
    for r in range(rows):  # rows
        row =  [ table_sort_button(r, 'UP') ]
        row += [ table_sort_button(r, 'DW') ]
        cells = []
    
        for c in range(1,len(TABLE)):  # cols
            if terminals[i]['block_name'] != memo_block_name:
                back_color = 1 - back_color
                memo_block_name = terminals[i]['block_name']

            if c == 1:  # the firs cell saves UUID
                meta = terminals[i]['uuid']
            text = terminals[i][TABLE[c]['key']]
            cells += [ table_cell(c, r, text=text, metadata=meta, bgcolor = back_color) ]

        i += 1  # new row in the terminals from project
        row += cells
        terminals_table.append( row )


    # UI Final layout
    return [ 
            # Section 1
            [
                sg.Frame("General settings", layout = general_settings_area, vertical_alignment='top'), \
                sg.Frame("Dimensions settings", layout = dimensions_settings_area, vertical_alignment='top'), \
                sg.Frame("Font size settings", layout = font_size_settings_area, vertical_alignment='top') 
            ], \
            
            # Warning
            [sg.T("Remember to save the QET project before using this plug-in.", text_color='red')], \

            # Separator
            [ sg.HorizontalSeparator(pad=(0,10)) ], \

            # Section 2
            [ 
                sg.Column(tb_list, expand_y=True), 
                sg.VSeperator(),
                sg.Column(terminals_table,scrollable=True, vertical_scroll_only=True, expand_y=True)
            ]
        ]


### MAIN

# logging
initialize_logger()
log.info (TITLE)

# QET file project
qet_file = get_QET_fullpath( os.path.expanduser("~") )
# qet_file = "/home/raul/Downloads/sample.qet"
# qet_file = "/home/raul/Nextcloud/Proyectos/QET_Terminal_Block/current_v1.2/sample_projects/achim_bugs/Basic.qet"
# qet_file = get_QET_fullpath( "/home/raul/Downloads/sample.qet" )

if not qet_file:
    exit()

# QET Project
qet_project = QETProject(qet_file)  # allows working with a QET XML file.

# UI
sg.theme (THEME)
#print = sg.EasyPrint  # print to a window
sg.popup_quick_message('Reading data...',' ','  ', \
        title=TITLE, auto_close=True, non_blocking=True)
layout = get_layout(qet_project)
window = sg.Window(TITLE, layout, icon = ICON,  resizable=True, size=(1000,500))

 
# Gestión eventos
initialized = False

while True:
    # Read and load settings
    if not initialized:
        event, values = window.read(timeout=10)
        load_settings()
        initialized = True

    event, values = window.read()
    #print ('Event: {}'.format(event))
    #print (values)

    if event == sg.WIN_CLOSED:
        break
    
    elif event == '-OK-':
        settings = save_settings()
        if settings:  # settings are OK
            choosed = choose_tb_to_create(tb_names=qet_project.tb_names, edited_terminals=edited_terminals)
            create_terminal_blocks(choosed, int(window['-CFG_SPLIT-'].get()), \
                        settings, qet_project)
    elif event == '-BTN_LEGEND-':  # show legend picture
        e, v = sg.Window('Terminal-block legend',
                    [
                      [sg.Image(data = LEGEND_PICTURE)],
                      [sg.B('OK')]
                    ]).read(close=True)

    elif event.startswith('-UP'):  # move terminal up
        row =  event[3:-1]
        move_terminal_up(row = row)
        add_to_edited_tb( edited_terminals, tb_name=window['-2/{}-'.format(row)].get() )


    elif event.startswith('-DW'):  #move terminal down
        row = event[3:-1]
        move_terminal_down(row = row, 
                max_index_row = len(qet_project.terminals))
        add_to_edited_tb ( edited_terminals, tb_name=window['-2/{}-'.format(row)].get() )
    
    elif event == '-TB-':   # click on filter list
        filter_terminals(values['-TB-'], \
                max_index_row = len(qet_project.terminals))
    
    elif event.startswith('-6/'):  # click en BRIDGE column
        row = event[3:-1]
        alter_bridge (event)
        add_to_edited_tb ( edited_terminals, tb_name=window['-2/{}-'.format(row)].get() )
    
    elif event.startswith('-7/'):  # click en TYPE column
        row = event[3:-1]
        alter_type (event)
        add_to_edited_tb ( edited_terminals, tb_name=window['-2/{}-'.format(row)].get() )

    elif event.startswith('-8/'):  # HOSE cell
        row = event[3:-1]
        add_to_edited_tb ( edited_terminals, tb_name=window['-2/{}-'.format(row)].get() )

    elif event.startswith('-9/'):  # click en TYPE column
        row = event[3:-1]
        add_to_edited_tb ( edited_terminals, tb_name=window['-2/{}-'.format(row)].get() )

    elif event == '-BTN_DEFAULT-':
        set_default_settings()
    
    elif event == '-ABOUT-':
        sg.popup("Terminal Block generator plug-on for QElectrotech\n\nhttps://qelectrotech.org/\n\nraulroda8@gmail.com" , title="QET")
