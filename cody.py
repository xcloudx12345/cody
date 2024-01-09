from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI,GoogleGenerativeAIEmbeddings 
from langchain.vectorstores import FAISS
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tempfile
import json
import time
import threading
import os
import speech_recognition as sr
from gtts import gTTS
import pygame
from google_text_to_speech import google_translate_tts
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

### USER OPTIONS ###
### MAX TOKENS PER CALL: MAX TOKENS TO USE FOR CALL
MAX_TOKENS_PER_CALL = 3000 # MAX TOKENS TO USE FOR CALL
IGNORE_THESE = ['.venv', '.env', 'static', 'dashboard/static', 'audio', 'license.md', '.github', '__pycache__','.git',"requirements.txt"]
r = sr.Recognizer()

llm_text=ChatGoogleGenerativeAI(
	model="gemini-pro",
	temperature=0.9,
	top_p=0.9,
    top_k=1,
	convert_system_message_to_human = True)

class FileChangeHandler(FileSystemEventHandler):
	def __init__(self, ignore_list=[]):
		super().__init__()
		self._busy_files = {}
		self.cooldown = 5.0  # Cooldown in seconds
		self.ignore_list = IGNORE_THESE  # Ignore list
		self.data = {}
		self.knowledge_base = {}
		self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001",task_type="retrieval_query")
	def should_ignore(self, filename):
		current_time = time.time()

		# Check if the file is in the ignore list
		for item in self.ignore_list:
			if item in filename:
				return True

		# Check if the file is in the busy files and within the cooldown period
		if filename in self._busy_files:
			if current_time - self._busy_files[filename] < self.cooldown:
				return True

		# Update the busy files dictionary
		self._busy_files[filename] = current_time
		return False

	def on_modified(self, event):
		if ".mp3" not in event.src_path:
			if not self.should_ignore(event.src_path):
				print(f'\n\U0001F4BE The file {event.src_path} has changed!')
				self.update_file_content()

	def update_file_content(self):
		print("\n\U0001F4C1 Collecting files...")
		all_files_data = {}
		# Check if ".env" is in ignore list, if not prompt warning "Are you sure you want to include your .env in your api call to OpenAI?"
		if ".env" not in self.ignore_list:
			response = input("😨 You removed .env from ignore list. This may expose .env variables to OpenAI. Confirm? (1 for Yes, 2 for exit):")
			if response != "1":
				print("\n😅 Phew. Close one... Operation aborted. Please add '.env' to your ignore list and try again.")
				exit()
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
								all_files_data[file_path] = json_data  # Store JSON data in the dictionary
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
		audio_stream = create_audio("Files updated. Ready for questions")
		play_audio(audio_stream)

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
	os.unlink(file_path)  # Delete the temporary file
	print("Deleted temp audio file in: " + file_path)

def create_audio(text):
	"""
	Create an audio file from text and return the path to a temporary file
	"""
	temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
	print(f"\nCreated temp audio file in : {temp_file.name}")
	try:
		speech = gTTS(text=text, lang='en', slow=False)
		speech.save(temp_file.name)
	except Exception as e:
		print(f"\nError in creating audio: {e}")

	return temp_file.name

def count_tokens(text):
	# Phân tách chuỗi văn bản thành các token dựa trên khoảng trắng
	tokens = text.split()
	# Đếm và trả về số lượng token
	return len(tokens)	
def generate_response(prompt, speak_response:bool = False):

	try:
		response_text = llm_text.invoke(prompt)
		print("\n\U0001F4B0 Tokens used:", count_tokens(response_text.content))
		print('\U0001F916', response_text.content)
		if speak_response:
			audio_stream = create_audio(response_text.content)
			play_audio(audio_stream)
	except Exception as e:
		print(f"\U000026A0 Error in generating response: {e}")

def monitor_input(handler:FileChangeHandler, terminal_input=True):
	while True:
		try:
			if terminal_input:
				text = input("\U00002753 Please type your question (or 'exit' to quit): ")
			else:
				with sr.Microphone() as source:
					print("\nListening...")
					audio_data = r.listen(source)
					text = r.recognize_google(audio_data)

			if text.lower() == 'exit':
				print("\n\U0001F44B Exiting the program...")
				os._exit(0)
			else:
				print(f"You said: {text}")
				question = text
				print("\n\U0001F9E0 You asked: " + question)
				docs = handler.knowledge_base.similarity_search(question)
				response = f"You are an expert programmer who is aware of this much of the code base:{str(docs)}. \n"
				response += "Please answer this: " + question + "..." # Add the rest of your instructions here
				generate_response(response)
		except sr.UnknownValueError:
			print("\nCould not understand audio")
		except sr.RequestError as e:
			print("\nCould not request results; {0}".format(e))
		except Exception as e:
			print(f"An error occurred: {e}")

def start_cody():
	#ignore_list=IGNORE_THESE
	handler = FileChangeHandler(ignore_list=IGNORE_THESE)

	# Collect files before starting the observer
	handler.update_file_content()  # Directly call the update_file_content method

	# Prompt user for interaction method
	interaction_method = input("\nHow should I talk to you? Enter 1 for Terminal or 2 for Speech I/O: ")

	terminal_input = interaction_method == '1'
	
	# Start a new thread to monitor input
	input_thread = threading.Thread(target=monitor_input, args=(handler, terminal_input))
	input_thread.start()

	# Initialize the observer
	observer = Observer()
	observer.schedule(handler, path='.', recursive=True)
	observer.start()

	# Continue to observe for file changes
	try:
		while True:
			time.sleep(5)
	except KeyboardInterrupt:
		observer.stop()

	observer.join()

if __name__ == "__main__":
	start_cody()