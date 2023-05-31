import os 
import json

import argparse
import keyboard
import openai
import pyaudio
import speech_recognition as sr 
import wave

from elevenlabs import voices, generate, play, set_api_key
from loguru import logger

# ==================================|
# Setup required services to start: |
# ==================================|
def setup(file):
	logger.debug("Loading values from config file...")

	load_from_config(file)

	openai.api_key = OPENAI_API_KEY
	set_api_key(ELEVENLABS_API_KEY)

	globals()['RECOGNIZER'] = sr.Recognizer()

	logger.debug("Setup completed successfully!")

# =====================================|
# Load values from static config file: |
# =====================================|
def load_from_config(file):
	with open(file) as f:
		config = json.load(f)

		# Assign out config values to constants:
		globals()['DETECTION_KEY'] = config['detection_key']

		globals()['OPENAI_API_KEY'] = config['platforms']['chatgpt']['api_key']
		globals()['CHATGPT_MODEL'] = config['platforms']['chatgpt']['model']
		globals()['CHATGPT_TEMPERATURE'] = config['platforms']['chatgpt']['temperature']
		globals()['CHATGPT_MAX_TOKENS'] = config['platforms']['chatgpt']['max_tokens']
		globals()['CHATGPT_CONTEXT'] = config['platforms']['chatgpt']['context']

		globals()['ELEVENLABS_API_KEY'] = config['platforms']['elevenlabs']['api_key']
		globals()['ELEVENLABS_AI_MODEL'] = config['platforms']['elevenlabs']['ai_model']
		globals()['ELEVENLABS_VOICE_NAME'] = config['platforms']['elevenlabs']['voice_name']

# ========================================|
# Record audio while key_pressed via mic: |
# ========================================|
def record_audio():
	CHUNK = 1024
	FORMAT = pyaudio.paInt16
	CHANNELS = 1
	RATE = 44100
	MAX_SECONDS = 120
	WAVE_OUTPUT_FILENAME = "output.wav"

	p = pyaudio.PyAudio()

	stream = p.open(format=FORMAT, channels=CHANNELS,
		rate=RATE, input=True, frames_per_buffer=CHUNK)

	logger.info("Recording input from microphone to buffer...")

	frames = []

	for i in range(0, int(RATE / CHUNK * MAX_SECONDS)):
		data = stream.read(CHUNK)
		frames.append(data)

		if (keyboard.is_pressed(DETECTION_KEY)):
			break

	logger.info("Finished recording input from microphone to buffer!")

	stream.stop_stream()
	stream.close()
	p.terminate()

	logger.info("Writing recording to file...")

	wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
	wf.setnchannels(CHANNELS)
	wf.setsampwidth(p.get_sample_size(FORMAT))
	wf.setframerate(RATE)
	wf.writeframes(b''.join(frames))
	wf.close()

	logger.info("Finished recording to file!")

	return WAVE_OUTPUT_FILENAME

# ==============================================|
# Recognize speech from file & process to text: |
# ==============================================|
def transcribe_audio(path):
	logger.info("Parsing audio file for processing...")

	with sr.AudioFile(path) as source:
		audio_listened = RECOGNIZER.record(source)

		logger.info("Transcribing detected audio...")
		text = RECOGNIZER.recognize_google(audio_listened)

	logger.debug("Detected text: {}".format(text))

	return text

# ===================================|
# Send data to ChatGPT for response: |
# ===================================|
def openai_process_response(input_text):
	logger.info("Sending input to ChatGPT with context...")

	response = openai.ChatCompletion.create(
		model = CHATGPT_MODEL,
		temperature = CHATGPT_TEMPERATURE,
		max_tokens = CHATGPT_MAX_TOKENS,
		messages = [
			{ "role": "system", "content": CHATGPT_CONTEXT },
			{ "role": "user", "content": input_text }
		]
	)

	logger.info("ChatGPT: {}".format(response['choices'][0]['message']['content']))

	return(response['choices'][0]['message']['content'])

# ========================================|
# Use Elevenlabs to generate voiced text: |
# ========================================|
def generate_voice(selected_voice, output_text):
	logger.info("Sending voice generation request to Elevenlabs...")

	voice = voices()

	audio = generate(
		text=output_text,
		voice=selected_voice,
		model=ELEVENLABS_AI_MODEL
	)

	return audio

# ===============================================|
# Playback voiced text from file once completed: |
# ===============================================|
def init_playback(audio):
	logger.info("Playing back audio from Elevenlabs...")

	play(audio)


if "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument('-f', '--file',
		help='JSON config filename',
		type=argparse.FileType('r')
	)
	args = parser.parse_args()
	
	if (args.file):
		setup(args.file.name)

		logger.debug("Beginning to poll for initial input!")

		while(True):
			if keyboard.is_pressed(DETECTION_KEY):
				logger.debug("Keypress detected! Initiating loop...")

				filename = record_audio()
				input_text = transcribe_audio("{}/{}".format(os.getcwd(), filename))

				output_text = openai_process_response(input_text)
				audio = generate_voice(ELEVENLABS_VOICE_NAME, output_text)
				init_playback(audio)

				logger.debug("Resuming polling...")
	else:
		logger.error("No config file provided, please try again.")