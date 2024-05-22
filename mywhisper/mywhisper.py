import io
from pydub import AudioSegment
import speech_recognition as sr
import queue
import tempfile
import os
import threading

class mywhisper:
    def __init__(self, my_openai, energy=300, pause=0.1, dynamic_energy=False, save_file=False):
        self.my_openai = my_openai
        self.energy = energy
        self.pause = pause
        self.dynamic_energy = dynamic_energy
        self.save_file = save_file
        self.temp_dir = tempfile.mkdtemp() if save_file else None
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(sample_rate=16000)

    def record_audio_callback(self, recognizer, audio):
        try:
            data = io.BytesIO(audio.get_wav_data())
            audio_clip = AudioSegment.from_file(data)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            audio_clip.export(temp_file.name, format="wav")
            audio_data = temp_file.name
            self.audio_queue.put_nowait(audio_data)
        except Exception as e:
            print(f"Error in record_audio_callback: {e}")

    def record_audio(self):
        self.recognizer.energy_threshold = self.energy
        self.recognizer.pause_threshold = self.pause
        self.recognizer.dynamic_energy_threshold = self.dynamic_energy
        self.recognizer.non_speaking_duration = 0.1

        print("Say something!")
        self.stop_listening = self.recognizer.listen_in_background(self.microphone, self.record_audio_callback)

    def transcribe_forever(self):
        while not self.stop_event.is_set():
            try:
                audio_data = self.audio_queue.get(timeout=1)
                audio_file = open(audio_data, "rb")
                result = self.my_openai.transcribe_audio(audio_file)
                predicted_text = result.text
                self.result_queue.put_nowait(predicted_text)
                if self.save_file:
                    os.remove(audio_data)
            except queue.Empty:
                continue

    def start_transcribing(self):
        threading.Thread(target=self.record_audio).start()
        threading.Thread(target=self.transcribe_forever).start()
        return self.result_queue
