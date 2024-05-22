import io
from pydub import AudioSegment
import speech_recognition as sr
import queue
import tempfile
import os
import threading
import time

class mywhisper:
    def __init__(self, my_openai, energy=300, pause=0.1, silence_duration:float=10.0, dynamic_energy=False, save_file=False):
        # energy: この値が大きいと、雑音の多いところでも無音判定される
        # silence_duration: この値の秒数無音が続くと、自動で処理を止める

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
        self.last_audio_time = time.time()
        self.silence_duration = silence_duration  # 無音検出のしきい値（秒）
        self.threads = []

    def record_audio_callback(self, recognizer, audio):
        try:
            self.last_audio_time = time.time()
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
                # 無音検出処理
                if time.time() - self.last_audio_time > self.silence_duration:
                    print(f"No speech detected for {self.silence_duration} seconds, stopping...")
                    self.result_queue.put_nowait(f"system_msg:stop by silence in {self.silence_duration} sec.")
                    self.stop_event.set() #self.stop()を使うと、自分自身が閉じられるような形になり、エラーがでる（stopのjoinの部分で）
                    self.stop_listening(wait_for_stop=True)
                    # self.stop()
                    break

                audio_data = self.audio_queue.get(timeout=1)
                audio_file = open(audio_data, "rb")
                result = self.my_openai.transcribe_audio(audio_file)
                predicted_text = result.text
                self.result_queue.put_nowait(predicted_text)
                if self.save_file:
                    os.remove(audio_data)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in transcribe_forever: {e}")
                break

    def start_transcribing(self):
        self.last_audio_time = time.time()

        t1 = threading.Thread(target=self.record_audio)
        t2 = threading.Thread(target=self.transcribe_forever)
        self.threads.extend([t1, t2])
        t1.start()
        t2.start()
        return self.result_queue

    def stop(self):
        self.stop_event.set()
        self.stop_listening(wait_for_stop=True)
        for t in self.threads:
            t.join()