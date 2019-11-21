import tkinter as tk
from tkinter import filedialog
import os
import metrics

def select_file():
    """Specify a video file for processing."""
    filename = filedialog.askopenfilename(title="Open file...", initialdir=os.getcwd(),
                                             filetypes=(("MP4 videos", "*.mp4"),))
    window.path.set(filename.replace("/", "\\"))

def process(preview):
    """Convert a video file to music.

    This first reads the paths of all helper tools,
    as well as the track-specific settings influencing MIDI generation.
    The video file must be already selected by the user.
    If preview is True, only the MIDI file will be created and played back.
    Otherwise a copy of the original video with the MIDI track will be made.
    """
    modified = False
    # Prompting the user for helper executables
    if window.config["old_pythonpath"] == "":
        target = filedialog.askopenfilename(title="Please locate the Python 2.7 interpreter", initialdir=os.getcwd(), filetypes=(("Python executable", "*.exe"), ))
        window.config["old_pythonpath"] = target
        modified = True
    if window.config["ffmpegpath"] == "":
        target = filedialog.askopenfilename(title="Please locate the ffmpeg binary", initialdir=os.getcwd(), filetypes=(("ffmpeg executable", "*.exe"), ))
        window.config["ffmpegpath"] = target
        modified = True
    if window.config["vlcpath"] == "":
        target = filedialog.askopenfilename(title="Please locate the VLC media player", initialdir=os.getcwd(),
                                               filetypes=(("VLC executable", "*.exe"), ))
        window.config["vlcpath"] = target
        modified = True
    # Update the config file, if needed
    if modified:
        file = open("config.txt", "w")
        for key in window.config:
            file.write(key+"="+window.config[key]+"\n")
        file.close()

    settings = []
    instr = ["piano", "guitar", "cello", "flute", "vibraphone", "marimba", "strings", "drums"]
    for i in range(0, window.index, window.con_count):
        temp = {}
        temp["muted"] = window.vars[i + 1].get()
        if temp["muted"] == 1:
            continue # Skipping muted tracks
        temp["feature"] = window.vars[i].get()
        temp["instrument"] = str(instr.index(window.vars[i + 2].get()))
        temp["controls"] = window.vars[i + 3].get()
        temp["scale"] = window.vars[i + 4].get()
        settings.append(dict(temp))
    # Launch the processing sequence
    metrics.main(window, settings, preview)
    if not preview:
        filename = filedialog.asksaveasfilename(title="Save file...", initialdir=os.getcwd(),
                                                   filetypes=(("MP4 videos", "*.mp4"),))
        if filename:
            if ".mp4" not in filename:
                filename += ".mp4"
            os.replace(window.scriptpath + "\\test.mp4", filename)

def remove_track(number):
    """Remove the current track and its UI components from view."""
    for i in range(number-window.con_count+1, number+1):
        window.controls[i].destroy()

def add_track():
    """Add a new track and its UI components on the screen."""
    var_types = ["string", "int", "string", "string", "string", "int"]
    fields = [["amplitude", "brightness", "contrast", "histogram", "joint"], [], ["piano", "guitar", "cello", "flute", "vibraphone", "marimba",
                   "strings", "drums"], ["notes", "pitch", "volume", "rhythm"], ["c-minor", "c-major", "blues"], []]
    for i in range(0, window.con_count):
        if var_types[i] == "string":
            window.vars.append(tk.StringVar())
        elif var_types[i] == "int":
            window.vars.append(tk.IntVar())
        if i == 1: # Mute checkbox
            window.controls.append(tk.Checkbutton(text="Mute", variable=window.vars[window.index]))
        elif i == 5: # Remove track button
            # This button's IntVar is only a dummy, needed to keep the numbering straight
            window.controls.append(tk.Button(window, text="Remove track", command=lambda x=window.index: remove_track(x)))

        else: # Dropdown menu
            window.controls.append(tk.OptionMenu(window, window.vars[window.index], *fields[i]))
            window.vars[window.index].set(fields[i][0])
        window.controls[window.index].grid(row=7 + int(window.index / window.con_count),
                                           column=(window.index % window.con_count) + 1)
        window.index += 1

# Main window and config
window = tk.Tk()
window.title("Music generation tool")
window.geometry("1000x500")
window.scriptpath = "\\".join(os.path.realpath(__file__).split("\\")[:-1])
window.config = {}
configfile = open("config.txt", )
for line in configfile:
    sp = line.replace("\n", "").split("=")
    window.config[sp[0]] = sp[1]
configfile.close()

# Labels and text fields
heading = tk.Label(text="Welcome to Data to Music application", bg="black", fg="white")
heading.grid(column=1, row=0)
enterpath = tk.Label(text="Enter the path of the video file")
enterpath.grid(column=0, row=1, sticky=tk.E)
window.path = tk.StringVar()
pathtext = tk.Entry(textvariable=window.path)
pathtext.grid(column=1, row=1)
window.status = tk.StringVar()
tk.Label(textvariable=window.status).grid(column=2, row=12)

# Buttons
tk.Button(window, text="Select", command=select_file).grid(column=2, row=1)
tk.Button(text="Add instrument", command=add_track).grid(row=0, column=0)
tk.Button(text="Convert", command=lambda: process(False)).grid(row=6, column=0)
tk.Button(text="Preview", command=lambda: process(True)).grid(row=6, column=1)

# Other variables
window.controls = [] # Widgets responsible for every track's instruments and other parameters
window.vars = [] # Variables holding the current value of every such component
window.index = 0 # Total number of track-specific components
window.con_count = 6 # Number of components per track
window.mainloop()
