import io
from pydub import AudioSegment
import speech_recognition as sr
import queue
import tempfile
import os
import threading
import time

class mywhisper:
    f_processing_stt = False

    def __init__(self, my_openai, energy=300, pause=0.1, rms=1500, silence_duration:float=10.0, dynamic_energy=False, save_file=False, f_debug:bool=False):
        # energy: この値が大きいと、雑音の多いところでも無音判定される
        # silence_duration: この値の秒数無音が続くと、自動で処理を止める

        self.my_openai          = my_openai
        self.pause              = pause                 #個の秒数だけ無音が続くと、そこまでの音声をSTTに渡す
        self.energy             = energy                #Recognizerないでの無音判定閾値
        self.dynamic_energy     = dynamic_energy        #energyの閾値を動的に変えるかどうか
        self.save_file          = save_file
        self.temp_dir           = tempfile.mkdtemp() if save_file else None
        self.recognizer         = sr.Recognizer()
        self.microphone         = sr.Microphone(sample_rate=16000)
        self.audio_queue        = queue.Queue()
        self.result_queue       = queue.Queue()
        self.stop_event         = threading.Event()
        self.last_audio_time    = time.time()           #音声が入ったときに更新掛けるが、念のためここでもセット
        self.silence_duration   = silence_duration      #個の秒数だけ無音が続くと、STTを停止する
        self.threads            = []                    #スレッドが入るリスト
        self.is_listening       = False                 #リスン状態を示すフラグ
        self.rms_threshold      = rms                   #音声入力中かの判定に使う（マイクに話しているかどうかの閾値）
        self.f_debug            = f_debug

    #------------------------------------------------------------#
    #--- マイクの音声を拾う関数群 --------------------------------#
    #------------------------------------------------------------#
    def start_recording(self):
        self.recognizer.energy_threshold = self.energy
        self.recognizer.pause_threshold = self.pause
        self.recognizer.dynamic_energy_threshold = self.dynamic_energy
        self.recognizer.non_speaking_duration = 0.1
        self.is_listening = True

        print("Say something!")
        self.stop_listening = self.recognizer.listen_in_background(self.microphone, self.recording_callback)

        # スレッドを作成して音声レベルのチェックを開始
        time.sleep(0.5) #これがないと、「準備前に別スレッドが走り出す」となってプログラムが落ちる
        self.thread_monitor_rms_level = threading.Thread(target=self.monitor_rms_level)
        self.thread_monitor_rms_level.start()

    def recording_callback(self, recognizer, audio):
        try:
            self.f_processing_stt = True
            self.last_audio_time = time.time()

            data = io.BytesIO(audio.get_wav_data())
            audio_clip = AudioSegment.from_file(data)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            audio_clip.export(temp_file.name, format="wav")
            audio_data = temp_file.name
            self.audio_queue.put_nowait(audio_data)
            if self.f_debug :
                print("procecced recording_callback") 

        except Exception as e:
            print(f"Error in recording_callback: {e}")

    def monitor_rms_level(self):
        #self.recognizerを使うと競合でエラーになるので、新たにマイクオブジェクトを立てる
        local_recognizer = sr.Recognizer()
        local_microphone = sr.Microphone()

        with local_microphone as source:
            local_recognizer.adjust_for_ambient_noise(source, duration=1)

        while self.is_listening:
            with local_microphone as source:
                audio = local_recognizer.record(source, duration=0.1)
                wav_data = audio.get_wav_data()
                audio_segment = AudioSegment(data=wav_data, sample_width=2, frame_rate=16000, channels=1)
                current_level = audio_segment.rms

                if current_level > self.rms_threshold :
                    self.f_processing_stt = True
                    self.last_audio_time = time.time()

                if self.f_debug :
                    print(f"Current audio level: {current_level}, energy: {self.rms_threshold}, f_talking: {self.f_processing_stt}")
            time.sleep(0.1)


    #------------------------------------------------------------#
    #--- STT(Speech to Text) ------------------------------------#
    #------------------------------------------------------------#
    def run_speech_to_text(self):
        while not self.stop_event.is_set() : #リスン終了後も回す必要あり and self.is_listening :
            try:
                # 無音検出処理
                if time.time() - self.last_audio_time > self.silence_duration:
                    print(f"No speech detected for {self.silence_duration} seconds, stopping...")
                    self.result_queue.put_nowait(f"system_msg:stop by silence in {self.silence_duration} sec.")
                    self.stop_event.set() #self.stop()を使うと、自分自身が閉じられるような形になり、エラーがでる（stopのjoinの部分で）
                    self.stop_listening(wait_for_stop=True)
                    # self.stop()
                    break

                audio_data = self.audio_queue.get(timeout=0.5) #空白データの場合、ここで止まる。1秒経ったらexceptに飛ぶ

                self.last_audio_time = time.time() #念のためここでも更新
                self.f_processing_stt = True
                audio_file = open(audio_data, "rb")
                result = self.my_openai.transcribe_audio(audio_file)
                predicted_text = result.text
                self.result_queue.put_nowait(predicted_text)
                if self.save_file:
                    os.remove(audio_data)
                self.f_processing_stt = False
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in run_speech_to_text: {e}")
                break

    def is_processing_stt(self) -> bool :
        return self.f_processing_stt
    
    def start_stt(self):
        self.last_audio_time = time.time()

        t1 = threading.Thread(target=self.start_recording)
        t2 = threading.Thread(target=self.run_speech_to_text)
        self.threads.extend([t1, t2])
        t1.start()
        t2.start()
        return self.result_queue

    def stop_stt(self):
        self.is_listening = False #音量チェックはすぐに止めてOK

        #STT処理中なら、待つ
        while self.is_processing_stt() :
            if self.f_debug :
                print("waiting stt stop")
            time.sleep(0.1)

        self.stop_event.set()
        self.stop_listening(wait_for_stop=True)
        for t in self.threads:
            t.join()

    def cleanup(self):
        self.audio_queue.queue.clear()
        self.result_queue.queue.clear()
        self.threads = []









# # pip install git+https://github.com/lupin-oomura/myopenai.git
# import queue
# import myopenai
# from dotenv import load_dotenv
# load_dotenv()

# def main():
#     mo = myopenai()

#     #リアルタイム文字起こし
#     transcriber = mywhisper(mo, energy=300, pause=0.1, silence_duration=5, dynamic_energy=False, save_file=False)
#     result_queue = transcriber.start_stt()

#     print("Recording... Press Ctrl+C to stop.")
#     txt_all = ""
#     try:
#         while not transcriber.stop_event.is_set():
#             try:
#                 say = result_queue.get(timeout=0.5)
#                 print(f"You said: {say}")
#                 txt_all += say

#                 if "処理を終了してください" in say:
#                     print("stopped by talk command")
#                     break

#                 if transcriber.stop_event.is_set() :
#                     print("stopped by silence")
#             except queue.Empty:
#                 continue

#     except KeyboardInterrupt:
#         print("keyboard interrupt")

#     transcriber.stop_stt()


#     #キューの残り物を抽出
#     try:
#         say = result_queue.get(timeout=0.5)
#         print(f"You said: {say}")
#         txt_all += say
#     except queue.Empty:
#         pass # キューが空の場合は何もしない

#     #メモリクリーンアップ
#     transcriber.cleanup()
#     print("Stopped by user")

#     print(f"predicted txt = {txt_all}")

    
# if __name__ == "__main__":
#     main()




