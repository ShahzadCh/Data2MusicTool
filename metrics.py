import time
import json
import wave
import os
import random
import numpy as np
import cv2 as video_library

def to_json(lists, features, file_name):
    """Converts metric data into a JSON file for Data2Music.

    Each metric is stored in a single sublist of lists.
    features contains the names of all respective metrics.
    file_name refers to the output file.
    """
    li2 = []
    di = {}
    # Data2Music expects timestamps with milliseconds,
    # while time() returns 6 decimal digits
    time_stamp = time.time() * 1000
    # Timestamps may be arbitrary, as long as they are distinct
    copy = time_stamp
    for i in range(0, len(lists)):
        for each in lists[i]:
            di["timestamp"] = int(time_stamp)
            time_stamp += 1000
            ## Originally we wanted to have one timestamp per frame,
            ## but it turned out the time itself was not important,
            ## as long as all the values were distinct
            di["feature"] = features[i]
            di["value"] = each
            di["parameters"] = {"system": "track1"}
            ## Lists only store references to objects, not objects themselves,
            ## so normally appending di just creates many references to a single dictionary.
            ## A copy is demanded on every iteration to create unique objects.
            li2.append(di.copy())
        time_stamp = copy # This ensures that items in parallel sublists have the same timestamps
    ## The shorthand for the inner loop used to be
    ## li2=[{"timestamp":1000000,"feature":feature,"value":x} for x in li],
    ## but now it cannot be used because the timestamp is variable
    file = open(file_name, "w")
    for item in li2:
        # Data2Music expects one object per line, NOT a list of objects
        json.dump(item, file)
        file.write("\n")
    file.close()

def brightness(video):
    """Compute the brightness metric.

    For every frame, this metric is simply
    the sum of all colour components of every pixel.
    """
    li = []
    fc = video.get(video_library.CAP_PROP_FRAME_COUNT)
    for k in range(0, int(video.get(video_library.CAP_PROP_FRAME_COUNT))):
        ret, frame = video.read()
        if frame is None:
            li.append(-1)
            continue
        try:
            total = np.sum(frame, dtype=np.uint32)
            li.append(np.asscalar(total))
        except TypeError:
            li.append(-1)
    video.release()
    return li

def contrast(video):
    """Compute the contrast metric.

    For every frame, this metric is the sum
    of per-pixel differences from the previous frame.
    The per-pixel difference refers to the distance between
    the red, blue and green colour values of the same pixel
    in the previous and the current frames.
    These three distances are taken as absolute values and averaged.
    The first frame is not given a contrast value.
    """
    li = []
    ret, frame = video.read()
    frame = frame.astype(np.int16)
    for k in range(0, int(video.get(video_library.CAP_PROP_FRAME_COUNT)) - 1):
        ret, frame2 = video.read()
        if frame2 is None:
            li.append(-1)
            continue
        frame2 = frame2.astype(np.int16)
        try:
            # Convert both frames to signed int16, so that their difference won't overflow
            # Subtract the arrays and convert every element to its absolute value, i.e. the true distance between R, G and B
            # Sum all the distances inside the pixel, and all the pixels in the frame
            # (a separate function can be used for either of these, e.g. sum first and then...)
            total = np.sum(np.absolute(frame2 - frame), dtype=np.uint32)
            li.append(np.asscalar(total))
        except TypeError:
            li.append(-1)
        frame = frame2
    video.release()
    return li

def histogram(video):
    """Compute the alternate histogram-based contrast metric.

    The entire space of distinct RGB values is first divided into
    BINLEN bins along every dimension, for a total of BINLEN^3 bins.
    Each frame pixel falls into one of these bins depending on
    its R, G and B values.
    This metric is the total number of pixels that changed their bin
    from the previous frame.
    """
    li = []
    BINLEN = 8
    counts = np.zeros(BINLEN ** 3)
    fc = video.get(video_library.CAP_PROP_FRAME_COUNT)
    for k in range(0, int(video.get(video_library.CAP_PROP_FRAME_COUNT)) - 1):
        ret, frame = video.read()
        # Expand the frame to a 16-bit array
        # Flatten the array by reinterpreting it:
        # array of (width arrays of (height pixels)) -> array of width*height pixels
        # (width and height are stored in frame.shape)
        # Divide every value to reduce the range from [0,255] to [0,BINSTEP-1]
        if frame is None:
            li.append(-1)
            continue
        frame = (frame.astype(np.uint16) // (256 // BINLEN)).reshape([frame.shape[0] * frame.shape[1], 3])
        # Convert every pixel array into an octal value with the dot product:
        # for 8 bins, value=R*8*8+G*8+B
        # A pixel with values of R in bin 5, G in bin 3, B in bin 4 becomes 348, i.e. 534 in base 8
        # Count the number of pixels with bincount, leaving zeroes for missing values
        # (index 348 stores the number of pixels converted to 348, i.e. the pixels in bins 5-3-4)
        # 348 won't fit into a uint8, hence the need to expand to uint16 above
        # (for BINS=6, the highest value would be 215 and still fit into 1 byte)
        tmp = np.bincount(np.dot(frame, np.array([BINLEN * BINLEN, BINLEN, 1])), minlength=BINLEN ** 3)
        # Subtract the difference from the previous frame and sum up the absolute values
        li.append(np.asscalar(np.sum(np.absolute(tmp - counts))))
        counts = tmp
    video.release()
    return li

def amplitude(video, audio_name):
    """Compute the amplitude metric.

    Similar to the brightness metric, this is simply
    the sum of (absolute) amplitudes of every audio sample.
    Since the metric is supposed to have one value per video frame,
    and the audio sampling rate differs from the video framerate,
    the sum is taken over (sampling_rate/framerate) samples at a time.
    """
    li = []
    frames = int(video.get(video_library.CAP_PROP_FRAME_COUNT))
    w = wave.open(audio_name, "rb")
    cn = w.getnchannels()  # Usually 2 channels, stereo
    size = w.getsampwidth()  # Usually 2 bytes, or 16 bits
    samples = w.getnframes()
    spf = samples // frames
    fmt = "<" + {1: "B", 2: "h", 4: "i"}[size]
	
    for k in range(0, frames):
        chunk = w.readframes(spf)
        tmp = np.frombuffer(chunk, dtype=fmt)
        # For 8-bit audio, which is signed, convert it to unsigned
        # (expand to 16-bit and change from [0..255] to [-128..127])
        if size == 1:
            tmp = tmp.astype(np.uint16) - 128
        li.append(round(np.average(np.absolute(tmp, dtype=np.int32)), 3))
    w.close()
    return li

def joint(data):
    """Create an aggregate metric out of all other metrics.

    Every sequence of metric data (every sublist of data)
    is rescaled to [0,1] by dividing its every element over the maximum.
    The average of such rescaled values for every metric becomes
    the corresponding element of the output metric.
    """
    result = np.zeros(len(data[0]))
    base = len(data[0])
    for d in data:
        temp = np.array(d, dtype=np.float64)
        if len(d) < base:
            temp.resize(result.shape)
        result += temp / np.max(temp)
    print(result.tolist())
    return result

def change_points(data):
    """Detect change points in a sequence of metric data.

    This can be used to introduce natural-sounding randomness
    into the data, modifying the values right after or before
    observed change points.
    The mechanism used here simply captures every occasion
    when the data values exceed 30% of the maximum value,
    as long as at least 30 values appear between such occasions.
    cp contains the ascending indices of all located change points,
    including necessarily the first and last index.
    """
    cutoff = max(data) * 0.3
    cp = []
    shot_length = 30
    curr_cp = 0
    i = 1
    while i < len(data):
        if data[i] >= cutoff:
            if i - curr_cp > shot_length:
                cp.append(curr_cp)
            curr_cp = i
        i += 1
    if cp[0] != 0:
        cp = [0] + cp
    if cp[-1] != len(data) - 1:
        cp.append(len(data) - 1)
    return cp

def edit_playlist(filename):
    """Introduce random variations in Data2Music playlist file.

    Since individual notes corresponding to data points are played
    at constant intervals, it may help to change their starting times
    (t) by random amounts. This change must depend on the note length
    (absoluteDuration).
    Such modifications may be worth applying
    to particular instruments only. This can be achieved
    by checking the instrument code (c).
    Instrument numbers are the same as in metrics.process(),
    see the instr list.
    """
    f = open(filename, "r")
    j = json.load(f)
    f.close()
    diff = j["playData"][0]["absoluteDuration"] # Initial durations are all the same
    for i in range(1, len(j["playData"])):
        if not j["playData"][i]["absoluteDuration"]:
            j["playData"][i]["absoluteDuration"] = 1
        if j["playData"][i]["c"] in [2, 4]:
            shift = j["playData"][i]["absoluteDuration"] * (0.2 + random.random() * 0.3)
            j["playData"][i]["t"] += shift
    # Other note properties, such as height, may also be altered:
    # if j["playData"][i]["c"] == 2:
    #	if j["playData"][i]["vel"] >= 50:
    #		j["playData"][i]["vel"] = 50

    # Setting all durations to 0 can silence an instrument:
    # if j["playData"][i]["c"] == 7:
    #	j["playData"][i]["absoluteDuration"] = 0
    f = open(filename, "w")
    json.dump(j, f, indent=2)
    f.close()

def write_settings(path, settings, length):
    """Write the settings file used by Data2Music.

    path should point to the base directory of the tool's code,
    from which the function will navigate further down.
    settings is the object passed by the main() function below.
    length is the duration of the video in seconds,
    which the caller is expected to determine beforehand.
    """
    output = {"variables": {}}
    output["variableFilters"] = {}
    for setting in settings:
        feature = setting["feature"]
        ob = {feature: {}}
        ob[feature]["muted"] = True
        ob[feature]["streams"] = {}
        ob[feature]["streams"][feature + ": stream 1"] = {"muted": setting["muted"] == 1, "bpm": "150", "bpt": "1500",
                                                          "instrument": str(setting["instrument"]),
                                                          "dataTo": setting["controls"], "settings": {},
                                                          "thresholds": {}}
        ob[feature]["streams"][feature + ": stream 1"]["settings"] = {"controls": setting["controls"],
                                                                      "scale": setting["scale"],
                                                                      "enforceTonic": False, "midiRangeMin": 20,
                                                                      "midiRangeMax": 83}
        tmp = {"on": False, "filterType": "outer", "max": 131616321, "min": 0, "filterOption": "filter",
               "filterValue": ""}
        ob[feature]["streams"][feature + ": stream 1"]["thresholds"]["horizontal"] = tmp
        temp2 = dict(tmp)
        temp2["max"] = "Sun May 13 2018 13:27:53"
        temp2["min"] = "Sun May 13 2018 12:13:28"
        ob[feature]["streams"][feature + ": stream 1"]["thresholds"]["vertical"] = temp2
        ob[feature]["streams"][feature + ": stream 1"]["y_range"] = {"max": "131616321.00", "min": "0.00"}
        output["variables"][feature] = dict(ob[feature])
        output["variableFilters"][feature] = True
    output["instruments"] = ["piano", "guitar", "cello", "flute", "vibraphone", "marimba", "strings", "drums"]
    output["source"] = "track1"
    output["bpm"] = "100"
    output["duration"] = str(length)
    file = open(path + "\\javascript-audio\\settings3.txt", "w", encoding="utf-8")
    json.dump(output, file, indent=3)
    file.close()

def process(path, spath, full):
    """Compute and record all the metrics of the video.

    path is the location of the video file.
    spath is the directory where the audio track
    will be temporarily extracted to.
    If full is False, the metrics are already calculated
    and no processing occurs.
    Returns the duration of the provided video, in seconds.
    """
    source = path
    video = video_library.VideoCapture(source)
    if not full:
        return int(video.get(video_library.CAP_PROP_FRAME_COUNT) / video.get(
            video_library.CAP_PROP_FPS))  # Duration as frame count/FPS
    # Other relevant properties:
    # width = int(video.get(video_library.CAP_PROP_FRAME_WIDTH))
    # height = int(video.get(video_library.CAP_PROP_FRAME_HEIGHT))
    # frames = int(video.get(video_library.CAP_PROP_FRAME_COUNT))
    # The computation can be timed:
    # start = time.time()
    histogram_list = histogram(video)
    # To avoid data loss, metrics can be saved individually as follows:
    # to_json([histogram_list], ["histogram"], source.replace(".mp4", "h.json"))
    video = video_library.VideoCapture(source)
    amplitude_list = amplitude(video, spath + "\\test.wav")
    video = video_library.VideoCapture(source) # This resets the video to the beginning
    brlist = brightness(video)
    video = video_library.VideoCapture(source)
    clist = contrast(video)
    jlist = joint([brlist, histogram_list, clist])
    # end = time.time()
    joint_lists = [brlist, histogram_list, amplitude_list, clist, jlist]
    to_json(joint_lists, ["brightness", "histogram", "amplitude", "contrast", "joint"], source.replace(".mp4", ".json"))
    fps = video.get(video_library.CAP_PROP_FPS)
    if fps == 0: # This may be somehow returned by the library
        fps = 25
    result = int(video.get(video_library.CAP_PROP_FRAME_COUNT) / fps)
    video_library.destroyAllWindows()
    return result

def main(w, settings, preview):
    """Convert the input video to music.

    w is tkinter's window object, needed to access various helper variables
    and also to write status messages in the UI.
    settings is the object created by the interface.process() function, e.g.
    [{"feature":"brightness","instrument":3,"scale":"c-major","controls":"notes","muted":0},
    {"feature":"contrast"...},...]
    If preview is True, the processing stops at the generated MIDI file,
    without replacing the video's original audio track with it.
    """
    filename = w.path.get()
    scriptpath = "\\".join(os.path.realpath(__file__).split("\\")[:-1])
    videopath = filename.replace("MP4", "mp4")
    w.status.set("Reading video data...")
    w.update()
    # Extracting audio for the amplitude metric
    # Related: https://superuser.com/questions/609740/extracting-wav-from-mp4-while-preserving-the-highest-possible-quality
    runstr = w.config["ffmpegpath"] + " -y -i \"" + videopath + "\" -vn -acodec pcm_s16le -ar 22050 -ac 2 \"" + scriptpath + "\\test.wav" + "\""
    os.system(runstr)
    dur = 0
    if not os.path.isfile(videopath.replace(".mp4", ".json")): # If metrics not yet computed
        dur = process(videopath, scriptpath, True)
    else:
        dur = process(videopath, scriptpath, False)
    bulk = scriptpath + "\\d2mSoftware"
    # Video duration needed for the settings file
    # is returned from the process() call as a by-product
    write_settings(bulk, settings, dur)

    # Move to the project directory and set up the first call
    os.chdir(bulk + "\\javascript-audio")
    # Run JavaScript via NodeJS, using the settings and the JSON data to create a playlist
    w.status.set("Creating MIDI playlist...")
    w.update()
    os.system("node NodeJSBatch.js settings3.txt " + videopath.replace(".mp4", ".json") + " playlist.txt")
    edit_playlist("playlist.txt")
    # "Play" the playlist, producing a MIDI file
    w.status.set("Generating MIDI file...")
    w.update()
    os.system(w.config[
        "old_pythonpath"] + " \"" + bulk + "\\middleware\\proxy\\generateMidi.py\" \"" + bulk + "\\javascript-audio\\playlist.txt\" \"" + bulk + "\\javascript-audio\\test.midi\"")
    # Move to the next application's folder
    os.chdir(w.config["vlcpath"].replace("vlc.exe", ""))
    # Convert the MIDI to MP3
    if preview:
        w.status.set("Done")
        w.update()
        os.system("vlc.exe \"" + bulk + "\\javascript-audio\\test.midi\"")
        return
    w.status.set("Converting MIDI to MP3...")
    w.update()
    os.system(
        "vlc.exe --no-repeat --no-loop \"" + bulk + "\\javascript-audio\\test.midi\" :sout=#transcode{acodec=mp3,ab=128,channels=2,samplerate=44100}:std{access=file,mux=dummy,dst='" + bulk + "\\javascript-audio\\test.mp3'} vlc://quit")
    # Move to the next application's folder
    os.chdir(scriptpath)
    # Replace the video's original soundtrack with the MP3
    w.status.set("Replacing original audio track...")
    w.update()
    os.system(w.config[
        "ffmpegpath"] + " -y -i \"" + videopath + "\" -i \"" + bulk + "\\javascript-audio\\test.mp3\" -c:v copy -map 0:v:0 -map 1:a:0 -shortest \"" + scriptpath + "\\test.mp4" + "\"")
    w.status.set("Done")
