#!/usr/bin/env python3

import speech_recognition as sr
import time
# obtain path to "english.wav" in the same folder as this script
from os import path
AUDIO_FILE = path.join(path.dirname(path.realpath(__file__)), "audio_vn.wav")
# AUDIO_FILE = path.join(path.dirname(path.realpath(__file__)), "french.aiff")
# AUDIO_FILE = path.join(path.dirname(path.realpath(__file__)), "chinese.flac")

# use the audio file as the audio source
r = sr.Recognizer()
with sr.AudioFile(AUDIO_FILE) as source:
    audio = r.record(source)  # read the entire audio file

# recognize speech using Sphinx
try:
    start_time = time.time()
    #print("Vosk thinks you said " + r.recognize_vosk(audio))
    #print("Whisper thinks you said " + r.recognize_whisper(audio,language="vietnamese",model="base"))
    print("Wit thinks you said:" + r.recognize_wit(audio,key="QJEW3EUB4M3AMT6NP2J4I6LVZURU2K5N"))
    #print respone time
    end_time = time.time()
    print("Response time: " + str(end_time - start_time) + " s")
    #print("Sphinx thinks you said " + r.recognize_sphinx(audio))
except sr.UnknownValueError:
    print("Vosk could not understand audio")
    print("Sphinx could not understand audio")
except sr.RequestError as e:
    print("Vosk request error; {0}".format(e))
    print("Sphinx error; {0}".format(e))

