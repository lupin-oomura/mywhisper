import io
import os
import time
from pydub import AudioSegment, silence
import speech_recognition as sr
import queue
import tempfile
import threading

import base64
import tempfile

import myopenai







class mywhisper :
    f_listening = False #音声キューをThreadingでウォッチしているときはTrue
    ac          = None  #myaudiocontrolクラス
    session_id  = None 
    stop_event = None #停止イベント
    predicted_text = ""
    queue_result = None 
    is_processing_stt = False #stt処理中かどうか
    stt_thread = None 
    f_debug    = False
    mo         = None #myopenai

    def __init__(self, session_id, f_debug:bool=False) :
        self.session_id = session_id
        self.ac = self.myaudiocontrol(f_debug=f_debug)
        self.stop_event = threading.Event()
        self.queue_result = queue.Queue()
        self.f_debug = f_debug #デバッグでプリントしまくりモード
        self.mo = myopenai.myopenai()



    def start_stt(self) :
        self.stt_thread = threading.Thread(target=self.__run_speech_to_text)
        self.stt_thread.start()

    def stop_stt(self) :
        self.stop_event.set()
        if self.f_debug :
            print(f"停止サイン送りました。")
        self.stt_thread.join() #終わりを待つ

        #最後のひねり出し
        while not self.ac.queue_talks.empty() :
            talk = self.ac.queue_talks.get()
            self.process_stt(talk)

        if self.f_debug :
            print(f"終了しました。")

    def __run_speech_to_text(self):
        while not self.stop_event.is_set() : 
            try:
                talk = self.ac.queue_talks.get(timeout=0.5)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in run_speech_to_text: {e}")
                break
            self.process_stt(talk)

    def process_stt(self, talk) :
        if self.f_debug :
            print(f"認識開始！")
        self.is_processing_stt  = True

        if self.is_mugon(talk) :
            if self.f_debug :
                print("無言なので処理スキップ")
            return None
            
        # 一時ファイルを作成して、そこにデータを書き込む
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(talk)
            temp_file.flush()  # データをディスクに確実に書き込む
            temp_file_name = temp_file.name
        xxx = open(temp_file_name, "rb")
        result = self.mo.transcribe_audio(xxx)
        xxx.close()
        predicted_text = result.text
        os.remove(temp_file_name)

        if self.f_debug :
            print(f"result = [{predicted_text}]")
        self.queue_result.put(predicted_text)
        self.is_processing_stt  = False
        if self.f_debug :
            print(f"認識終了")

    def is_mugon(self, wav_data) :
        audio = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
        if self.ac.is_pause( audio, self.ac.pause_threshold, int(len(audio)*0.8) ) :
            return True 
        else  :
            return False




    class myaudiocontrol :
        pause_threshold = None #ポーズ判定の閾値。要調整

        session_id = None 
        webm_audio_all = None 
        audio_all = None
        audio_talk = None #無音が続くまで追加される
        queue_talks = queue.Queue()  #文章単位（無音まで）で追加されるキュー
        current_index = None #webm_audio_allに対して、どこまでaudio化したかを保持（差分を得るため）
        len_pause_threshold = None #ポーズ判定の長さ
        chunk_size_for_ispause = None
        len_silence = 0 #無音がどれだけ続いているか
        f_debug = False
        last_audio_time = None #最後に音声が入った時間
        f_talked = False #１回でもトークキューに値が入ったら、立つ

        def __init__(self, pause_threshold:float=-40.0, len_pause_threshold:int=500, chunk_size_for_ispause:int=250, f_debug:bool=False) :
            self.current_index = 0
            self.len_pause_threshold = len_pause_threshold
            self.pause_threshold = pause_threshold
            self.queue_talks = queue.Queue() 
            self.chunk_size_for_ispause = chunk_size_for_ispause
            self.len_silence = 0
            self.f_debug = f_debug
            self.last_audio_time = time.time()

        def add_webmchunk(self, chunk_data) :
            webm_audio = base64.b64decode(chunk_data) #webから投げられたWEBmデータ。そのまま保存しても再生できない

            #全体をまとめておく(一度全体をまとめておかないと、音声データとして認識されない)
            self.webm_audio_all = b''.join([self.webm_audio_all, webm_audio]) if self.webm_audio_all else webm_audio
            self.audio_all = AudioSegment.from_file(io.BytesIO(self.webm_audio_all), format="webm")

            #前回からの追加分（＝今回追加分）をトークに追加
            audio_new = self.extract_audio_segment_bypart(self.audio_all)
            self.audio_talk = self.audio_talk + audio_new if self.audio_talk else audio_new

            #無音チェック・・・今回追加分(audio_new)に無音があったら、そこまでの文章をl_talksに追加
            if self.is_pause(audio_new, self.pause_threshold, self.len_pause_threshold) : #無音があったら 
                if not self.add_talk() :
                    self.len_silence += len(audio_new)
            else :
                self.len_silence = 0
                self.last_audio_time = time.time()


        def add_talk(self) :
            f_added = False 

            if not self.audio_talk :
                return False

            #そこまでのaudio_talkを無音で切り分け
            chunks = silence.split_on_silence(
                        self.audio_talk,
                        min_silence_len=self.len_pause_threshold,  # 無音と判断する最小の長さ（ミリ秒）
                        silence_thresh=self.pause_threshold,  # 無音と判断するしきい値
                        keep_silence=500  # 無音の部分を少し残す
            )
            if len(chunks) == 0 : #audio_talkがずっと無音（audio_newじゃなく）
                if self.f_debug :
                    print("ずっと無音")
                self.audio_talk = None #Noneに無音のaudioが追加されているケースは、ここでNoneにする
            else :
                if self.f_debug :
                    print("登録")
                self.last_audio_time = time.time()
                f_added = True
                chunk_pre_muon  = sum(chunks[:-1], AudioSegment.silent(duration=0)) if len(chunks) > 1 else chunks[0]
                #wav形式で保管
                wav_io = io.BytesIO()
                chunk_pre_muon.export(wav_io, format="wav")
                wav_io.seek(0)
                wav_audio = wav_io.getvalue()
                self.queue_talks.put(wav_audio)
                self.f_talked = True
                self.audio_talk = chunks[-1] if len(chunks) > 1 else None
                self.len_silence = 0
                if self.f_debug :
                    print(f"len talks : {self.queue_talks.qsize()}")

            return f_added

        def is_pause(self, audio, pause_threshold, len_pause_threshold)->bool:
            chunk_size = self.chunk_size_for_ispause
            chunks = [audio[i:i + chunk_size] for i in range(0, len(audio), chunk_size)]

            maxcount = count = 0 #無音ミリ秒数
            for chunk in chunks:
                dBFS = chunk.dBFS
                if dBFS > pause_threshold :
                    count = 0
                else :
                    count += 1
                    maxcount = max(maxcount, count)

            f_pause = True if maxcount*chunk_size >= len_pause_threshold else False
            return f_pause

        def is_silence(self, len_silence_threshold:int) :
            if (time.time() - self.last_audio_time ) * 1000 > len_silence_threshold :
                return True
            else :
                return False

        def get_len_silence(self) : 
            self.last_audio_time = time.time()

            return self.len_silence

        # pydubを使用して特定の秒数範囲を抽出する関数
        def extract_audio_segment_bypart(self, audio):
            l = len(audio)
            extracted_audio = audio[self.current_index:l]
            self.current_index = l
            return extracted_audio

        def save_wav(self) :
            count = 0

            while not self.queue_talks.empty() :
                wav = self.queue_talks.get()
                count += 1
                fn = f"wavdata{count}.wav"
                if os.path.exists(fn):
                    os.remove(fn)
                with open(fn, "wb") as f :
                    f.write(wav)
                if self.f_debug :
                    print(f"wavfuke: {count}")


























class mywhisper_mic:
    f_processing_stt = False
    predicted_text = ""

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
        self.predicted_text     = ""

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
                self.predicted_text += result.text
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

    def stop_stt(self) -> str:
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

        return self.get_predicted_text()

    def cleanup(self):
        self.audio_queue.queue.clear()
        self.result_queue.queue.clear()
        self.threads = []

    def get_predicted_text(self) :
        return self.predicted_text








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




