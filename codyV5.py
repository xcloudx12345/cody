from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
import time
import threading
import openai
import os
import speech_recognition as sr
from gtts import gTTS
import pygame

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
r = sr.Recognizer()

class FileChangeHandler(FileSystemEventHandler):
	def __init__(self, ignore_list=[]):
		super().__init__()
		self._busy_files = {}
		self.cooldown = 5.0  # Cooldown in seconds
		self.ignore_list = ignore_list  # Ignore list
		self.data = {}
		self.knowledge_base = {}
		self.embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

	def should_ignore(self, filename):
		current_time = time.time()
		if filename in self._busy_files:
			if current_time - self._busy_files[filename] < self.cooldown:
				return True
		self._busy_files[filename] = current_time
		return False

	def on_modified(self, event):
		if "response.mp3" not in event.src_path:
			if not self.should_ignore(event.src_path):
				print(f'\n \U0001F4BE The file {event.src_path} has changed!')
				self.update_file_content()

	def update_file_content(self):
		print("\U0001F4C1 Collecting files...")
		all_files_data = {}
		for root, dirs, files in os.walk('.'):
			# Remove directories in the ignore list
			dirs[:] = [d for d in dirs if d not in self.ignore_list]
			for filename in files:
				if filename not in self.ignore_list:
					file_path = os.path.join(root, filename)
					try:
						with open(file_path, 'r') as file:
							if filename.endswith('.json'):
								json_data = json.load(file)
							else:
								lines = file.readlines()
								line_data = {}
								for i, line in enumerate(lines):
									line_data[f"line {i + 1}"] = line.strip()
								all_files_data[file_path] = line_data
					except Exception as e:
						continue
						#print(f'\U000026A0 Error reading file {file_path}: {str(e)}')
	
		# Create the final dictionary with the desired format
		final_data = {"files": all_files_data}
		combined_text = json.dumps(final_data)
	
		# Split combined text into chunks
		text_splitter = CharacterTextSplitter(
			separator=",",
			chunk_size=1000,
			chunk_overlap=200,
			length_function=len,
		)
		chunks = text_splitter.split_text(combined_text)
		# print(combined_text)
		# Create or update the knowledge base
		self.knowledge_base = FAISS.from_texts(chunks, self.embeddings)
		
		print("\U00002705 All set!")
		create_audio("Files updated. Ready for questions", "audio/response.mp3")
		play_audio("audio/response.mp3")

def play_audio(file_path):
	"""
	Play audio from a file
	"""
	pygame.mixer.init()
	pygame.mixer.music.load(file_path)
	pygame.mixer.music.play()

	while pygame.mixer.music.get_busy():
		continue

	pygame.mixer.music.unload()

def create_audio(text, filename):
	"""
	Create an audio file from text
	"""
	try: 
		speech = gTTS(text=text, lang='en', slow=False)
		speech.save(filename)
	except Exception as e:
		print(f"Error in creating audio: {e}")
	
def generate_response(prompt):
	openai.api_key = OPENAI_API_KEY
	# # For debugging if you want to view the full data being passed
	# print("\U00002753 Received question: " + str(prompt))
	try:
		completion = openai.ChatCompletion.create(
		model="gpt-3.5-turbo", 
		messages=[{"role": "user", "content": prompt}]
		)
		print("\U0001F4B0 Tokens used:", completion.usage.total_tokens)
		# print total tokens used al time
		print('\U0001F916', completion.choices[0].message.content)
		create_audio(completion.choices[0].message.content, "audio/response.mp3")
		play_audio("audio/response.mp3")
	except Exception as e:
		print(f"\U000026A0 Error in generating response: {e}")

def collect_files(handler):
	# print("\U0001F4C1 Collecting files...")
	handler.update_file_content()
	# print("\U00002705 Initial file collection done.")

def monitor_input(handler):
	
	while True:
		try:
			with sr.Microphone() as source:
				print("Listening...")
				audio_data = r.listen(source)
				text = r.recognize_google(audio_data)
				

				if text == "exit":
					print("\U0001F44B Exiting the program...")
					os._exit(0)
				elif text:
					print(f"You said: {text}")
					question = text
					print("\U0001F9E0 You asked: " + question)
					docs = handler.knowledge_base.similarity_search(question)
					response = f"You are an expert programmer who is aware of this much of the code base:{str(docs)}. \n"
					response += "Please answer this: " + question + " Keep your answer under 20 words if possible. Speak in bullet points if you can to help with conciseness. Your main priority is to answer their questions using the info provided including line numbers if possible. Also note that when you give answers please include the file path if it makes sense. If the question is not relevant or not a question simply respond with 'Skipping'. Do not include any special text like _'s or ''s as this will be read by text to speech. Only include text in the response without non character letters. Even function names with _ in them should be replaced with a space so it is more readable audibly."
					ai_response = generate_response(response)
					text = ""
		except sr.UnknownValueError:
			print("Could not understand audio")
		except sr.RequestError as e:
			print("Could not request results; {0}".format(e))


def start_cody(ignore_list=[]):
	handler = FileChangeHandler(ignore_list)

	# Collect files before starting the observer
	collect_files(handler)

	# Start a new thread to monitor user input
	input_thread = threading.Thread(target=monitor_input, args=(handler,))
	input_thread.start()

	# Initialize the observer
	observer = Observer()
	observer.schedule(handler, path='.', recursive=True)
	observer.start()

	# Continue to observe for file changes. Adding time.sleep to reduce CPU usage as well as prevent 'duplicate' file change events (false flags)
	try:
		while True:
			time.sleep(5)
	except KeyboardInterrupt:
		observer.stop()

	observer.join()

if __name__ == "__main__":  # Set this to False to ignore .env file
	ignore_list = ['static', 'dashboard/static', 'audio', 'license.md', '.github', '__pycache__']
	start_cody(ignore_list)